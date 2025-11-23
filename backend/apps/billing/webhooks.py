"""
Webhook handlers для обработки уведомлений от YooKassa.
"""

from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.db import transaction
from django.utils import timezone
from django.conf import settings
import logging
import json
import ipaddress

from apps.common.audit import SecurityAuditLogger

from .models import Payment, Subscription, SubscriptionPlan, Refund
from .services import YooKassaService
from .throttles import WebhookThrottle

logger = logging.getLogger(__name__)

# YooKassa official IP addresses for webhook notifications
YOOKASSA_IP_RANGES = [
    '185.71.76.0/27',
    '185.71.77.0/27',
    '77.75.153.0/25',
    '77.75.154.128/25',
    '2a02:5180::/32',
]


def is_ip_allowed(client_ip):
    """
    Check if client IP is in YooKassa whitelist.

    Args:
        client_ip: IP address string

    Returns:
        bool: True if IP is allowed, False otherwise
    """
    # Allow localhost/127.0.0.1 for development
    if getattr(settings, 'DEBUG', False) and client_ip in ['127.0.0.1', 'localhost', '::1']:
        return True

    try:
        client_addr = ipaddress.ip_address(client_ip)

        for ip_range in YOOKASSA_IP_RANGES:
            network = ipaddress.ip_network(ip_range, strict=False)
            if client_addr in network:
                return True

        return False
    except ValueError:
        logger.error(f"Invalid IP address format: {client_ip}")
        return False


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([WebhookThrottle])
def yookassa_webhook(request):
    """
    POST /api/v1/billing/webhooks/yookassa
    Обработка webhook уведомлений от YooKassa.

    Обрабатываемые события:
    - payment.waiting_for_capture - Платёж ожидает подтверждения
    - payment.succeeded - Платёж успешно завершён
    - payment.canceled - Платёж отменён
    - refund.succeeded - Возврат успешно выполнен

    Безопасность:
    - Rate limiting: 100 requests/hour per IP (защита от DoS)
    - Проверка IP адреса отправителя (YooKassa whitelist)
    - Валидация структуры webhook через YooKassa SDK
    """
    try:
        # Verify IP address from YooKassa
        client_ip = request.META.get('REMOTE_ADDR')

        # Check IP whitelist (disabled in DEBUG mode for localhost)
        if not is_ip_allowed(client_ip):
            logger.warning(f"Webhook from unauthorized IP: {client_ip}")
            return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

        logger.info(f"Webhook received from authorized IP: {client_ip}")

        # Парсим уведомление
        notification = YooKassaService.parse_webhook_notification(request.data)

        notification_type = notification.event
        notification_object = notification.object

        logger.info(f"YooKassa webhook received: {notification_type}, payment_id: {notification_object.id}")

        if notification_type == 'payment.waiting_for_capture':
            handle_payment_waiting_for_capture(notification_object)

        elif notification_type == 'payment.succeeded':
            handle_payment_succeeded(notification_object)

        elif notification_type == 'payment.canceled':
            handle_payment_canceled(notification_object)

        elif notification_type == 'refund.succeeded':
            handle_refund_succeeded(notification_object)

        else:
            logger.warning(f"Unknown notification type: {notification_type}")

        return Response({'status': 'ok'}, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"YooKassa webhook error: {str(e)}", exc_info=True)
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


def handle_payment_waiting_for_capture(payment_object):
    """
    Обработка события payment.waiting_for_capture.
    Платёж ожидает подтверждения (capture).
    """
    try:
        payment = Payment.objects.get(yookassa_payment_id=payment_object.id)
        payment.status = 'WAITING_FOR_CAPTURE'
        payment.save()

        logger.info(f"Payment {payment.id} is waiting for capture")

    except Payment.DoesNotExist:
        logger.error(f"Payment not found for YooKassa ID: {payment_object.id}")


def handle_payment_succeeded(payment_object):
    """
    Обработка события payment.succeeded.
    Платёж успешно завершён - активируем/продлеваем подписку.
    """
    try:
        with transaction.atomic():
            # Находим платёж
            payment = Payment.objects.select_for_update().get(
                yookassa_payment_id=payment_object.id
            )

            # Проверяем, что платёж ещё не обработан
            if payment.status == 'SUCCEEDED':
                logger.info(f"Payment {payment.id} already processed")
                return

            # Получаем payment_method_id для рекуррентных платежей
            payment_method_id = None
            if payment_object.payment_method:
                payment_method_id = payment_object.payment_method.id

            # Обновляем статус платежа
            payment.mark_as_succeeded(payment_method_id=payment_method_id)

            # Получаем подписку и план
            subscription = payment.subscription
            plan = payment.plan

            if not subscription or not plan:
                logger.error(f"Payment {payment.id} has no subscription or plan")
                return

            # Продлеваем подписку
            subscription.extend_subscription(days=plan.duration_days)

            # Сохраняем payment_method_id для автопродления
            if payment_method_id and payment.save_payment_method:
                subscription.yookassa_payment_method_id = payment_method_id
                subscription.auto_renew = True  # Автоматически включаем автопродление
                subscription.save()

            # Обновляем план подписки, если это первая оплата или смена плана
            if subscription.plan != plan:
                subscription.plan = plan
                subscription.save()

            logger.info(f"Payment {payment.id} succeeded. Subscription extended until {subscription.end_date}")

            # SECURITY: Log successful payment
            SecurityAuditLogger.log_payment_success(
                user=payment.user,
                payment_id=str(payment.id),
                amount=float(payment.amount),
                plan=plan.name
            )

    except Payment.DoesNotExist:
        logger.error(f"Payment not found for YooKassa ID: {payment_object.id}")
    except Exception as e:
        logger.error(f"Error handling payment succeeded: {str(e)}", exc_info=True)


def handle_payment_canceled(payment_object):
    """
    Обработка события payment.canceled.
    Платёж отменён пользователем или истёк срок оплаты.
    """
    try:
        payment = Payment.objects.get(yookassa_payment_id=payment_object.id)

        # Обновляем статус
        payment.mark_as_canceled()

        # Получаем причину отмены
        cancellation_details = payment_object.cancellation_details
        if cancellation_details:
            payment.error_message = f"{cancellation_details.party}: {cancellation_details.reason}"
            payment.save()

        logger.info(f"Payment {payment.id} canceled")

        # SECURITY: Log failed payment
        reason = payment.error_message if payment.error_message else 'canceled'
        SecurityAuditLogger.log_payment_failure(
            user=payment.user,
            payment_id=str(payment.id),
            amount=float(payment.amount),
            reason=reason
        )

    except Payment.DoesNotExist:
        logger.error(f"Payment not found for YooKassa ID: {payment_object.id}")


def handle_refund_succeeded(refund_object):
    """
    Обработка события refund.succeeded.
    Возврат средств успешно выполнен.
    """
    try:
        # Находим платёж по payment_id
        payment = Payment.objects.get(yookassa_payment_id=refund_object.payment_id)

        # Создаём или обновляем возврат
        refund, created = Refund.objects.get_or_create(
            yookassa_refund_id=refund_object.id,
            defaults={
                'payment': payment,
                'amount': refund_object.amount.value,
                'status': 'SUCCEEDED',
                'completed_at': timezone.now(),
            }
        )

        if not created:
            refund.status = 'SUCCEEDED'
            refund.completed_at = timezone.now()
            refund.save()

        # Обновляем статус платежа
        payment.mark_as_refunded()

        # Опционально: деактивируем подписку при возврате
        if payment.subscription:
            subscription = payment.subscription
            # Можно добавить логику деактивации подписки
            logger.info(f"Refund for subscription {subscription.id} processed")

        logger.info(f"Refund {refund.id} for payment {payment.id} succeeded")

    except Payment.DoesNotExist:
        logger.error(f"Payment not found for refund payment_id: {refund_object.payment_id}")
    except Exception as e:
        logger.error(f"Error handling refund succeeded: {str(e)}", exc_info=True)
