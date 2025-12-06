"""
Webhook views for YooKassa notifications.
"""

import logging

from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.views.decorators.csrf import csrf_exempt

from apps.billing.services import YooKassaService
from apps.billing.throttles import WebhookThrottle
from apps.billing.models import WebhookLog

from .utils import is_ip_allowed, get_client_ip
from .handlers import (
    handle_payment_waiting_for_capture,
    handle_payment_succeeded,
    handle_payment_canceled,
    handle_refund_succeeded,
)

logger = logging.getLogger(__name__)


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([WebhookThrottle])
def yookassa_webhook(request):
    """
    POST /api/v1/billing/webhooks/yookassa
    
    Handle YooKassa webhook notifications.

    Events:
    - payment.waiting_for_capture - Payment awaiting capture
    - payment.succeeded - Payment successful
    - payment.canceled - Payment canceled
    - refund.succeeded - Refund successful

    Security:
    - Rate limiting: 100 requests/hour per IP
    - IP whitelist verification (YooKassa IPs)
    - Webhook validation via YooKassa SDK
    """
    try:
        client_ip = get_client_ip(request)

        if not is_ip_allowed(client_ip):
            logger.warning(f"Webhook from unauthorized IP: {client_ip}")
            return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

        logger.info(f"Webhook received from authorized IP: {client_ip}")

        notification = YooKassaService.parse_webhook_notification(request.data)
        notification_type = notification.event
        notification_object = notification.object

        logger.info(f"YooKassa webhook: {notification_type}, payment_id: {notification_object.id}")
        
        # Log webhook for monitoring and retry
        webhook_log = WebhookLog.objects.create(
            event_type=notification_type,
            event_id=str(notification_object.id),
            payment_id=str(notification_object.id),
            raw_payload=request.data,
            client_ip=client_ip,
            status='RECEIVED'
        )

        try:
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
                webhook_log.status = 'FAILED'
                webhook_log.error_message = f"Unknown notification type: {notification_type}"
                webhook_log.save()
                return Response({'status': 'ok'}, status=status.HTTP_200_OK)
            
            # Mark webhook as successfully processed
            from django.utils import timezone
            webhook_log.status = 'SUCCESS'
            webhook_log.processed_at = timezone.now()
            webhook_log.save()
            
        except Exception as handler_error:
            # Log handler error but return 200 to prevent YooKassa retries for permanent failures
            webhook_log.status = 'FAILED'
            webhook_log.error_message = str(handler_error)[:1000]
            webhook_log.attempts += 1
            webhook_log.save()
            logger.error(f"Webhook handler error: {handler_error}", exc_info=True)

        return Response({'status': 'ok'}, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"YooKassa webhook error: {str(e)}", exc_info=True)
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
