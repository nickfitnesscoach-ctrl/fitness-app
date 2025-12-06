"""
Event handlers for YooKassa webhooks.
"""

import logging
from decimal import Decimal
from functools import wraps

from django.db import transaction
from django.utils import timezone
from django.conf import settings

from apps.common.audit import SecurityAuditLogger
from apps.billing.models import Payment, Subscription, Refund, WebhookLog

logger = logging.getLogger(__name__)


def with_webhook_logging(event_type: str):
    """
    Decorator for webhook handlers that adds logging and idempotency check.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(payment_object, webhook_log: WebhookLog = None):
            payment_id = getattr(payment_object, 'id', None)
            
            # Create webhook log if not provided
            if webhook_log is None:
                webhook_log = WebhookLog.objects.create(
                    event_type=event_type,
                    event_id=str(payment_id) if payment_id else 'unknown',
                    payment_id=str(payment_id) if payment_id else None,
                    status='PROCESSING'
                )
            else:
                webhook_log.status = 'PROCESSING'
                webhook_log.attempts += 1
                webhook_log.save()
            
            try:
                result = func(payment_object)
                webhook_log.status = 'SUCCESS'
                webhook_log.processed_at = timezone.now()
                webhook_log.save()
                return result
            except Payment.DoesNotExist:
                webhook_log.status = 'FAILED'
                webhook_log.error_message = f"Payment not found: {payment_id}"
                webhook_log.save()
                raise
            except Exception as e:
                webhook_log.status = 'FAILED'
                webhook_log.error_message = str(e)[:1000]
                webhook_log.save()
                raise
        
        return wrapper
    return decorator


def check_idempotency(payment: Payment, event_type: str) -> bool:
    """
    Check if webhook was already processed (idempotency).
    
    Returns:
        True if already processed (should skip)
        False if not processed yet (should process)
    """
    if payment.webhook_processed_at is not None:
        logger.info(
            f"Webhook {event_type} for payment {payment.id} already processed at {payment.webhook_processed_at}"
        )
        return True
    return False


def mark_webhook_processed(payment: Payment):
    """Mark payment as processed by webhook."""
    payment.webhook_processed_at = timezone.now()
    payment.save(update_fields=['webhook_processed_at'])


def handle_payment_waiting_for_capture(payment_object):
    """
    Handle payment.waiting_for_capture event.
    Payment is waiting for capture confirmation.
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
    Handle payment.succeeded event.
    Activate or extend subscription.
    """
    try:
        with transaction.atomic():
            payment = Payment.objects.select_for_update().get(
                yookassa_payment_id=payment_object.id
            )

            # Idempotency check - skip if already processed
            if check_idempotency(payment, 'payment.succeeded'):
                return

            # Legacy check (keep for backward compatibility)
            if payment.status == 'SUCCEEDED':
                logger.info(f"Payment {payment.id} already processed")
                return

            # Get payment_method_id for recurring payments
            payment_method_id = None
            if payment_object.payment_method:
                payment_method_id = payment_object.payment_method.id

            payment.mark_as_succeeded(payment_method_id=payment_method_id)

            subscription = payment.subscription
            plan = payment.plan

            # Check if this is a card binding payment (no plan)
            is_card_binding = payment.plan is None and payment.amount == Decimal('1.00')

            if is_card_binding:
                _handle_card_binding(payment, payment_object, payment_method_id)
                return

            if not subscription or not plan:
                logger.error(f"Payment {payment.id} has no subscription or plan")
                return

            # SECURITY: Prevent FREE plan activation through payment
            if plan.code == 'FREE' or plan.price <= 0:
                _log_free_plan_attempt(payment, plan)
                return

            _activate_subscription(payment, plan, payment_method_id, payment_object)

    except Payment.DoesNotExist:
        logger.error(f"Payment not found for YooKassa ID: {payment_object.id}")
    except Exception as e:
        logger.error(f"Error handling payment succeeded: {str(e)}", exc_info=True)


def _handle_card_binding(payment, payment_object, payment_method_id):
    """Handle card binding payment (1 RUB for saving payment method)."""
    logger.info(f"Processing card binding payment {payment.id}")

    if payment_method_id and payment.save_payment_method:
        subscription = Subscription.objects.get(user=payment.user)
        subscription.yookassa_payment_method_id = payment_method_id

        # Extract card info
        if payment_object.payment_method and hasattr(payment_object.payment_method, 'card'):
            card_info = payment_object.payment_method.card
            if card_info:
                if hasattr(card_info, 'last4'):
                    subscription.card_mask = f"•••• {card_info.last4}"
                if hasattr(card_info, 'card_type'):
                    subscription.card_brand = card_info.card_type.upper()

        subscription.save()
        logger.info(f"Card binding succeeded for payment {payment.id}")

    SecurityAuditLogger.log_payment_success(
        user=payment.user,
        payment_id=str(payment.id),
        amount=float(payment.amount),
        plan='card_binding'
    )
    
    # Mark as processed for idempotency
    mark_webhook_processed(payment)


def _log_free_plan_attempt(payment, plan):
    """Log security event for FREE plan payment attempt."""
    logger.error(
        f"Attempted to activate FREE plan through payment {payment.id}. "
        f"Plan: {plan.code}, Price: {plan.price}. This should not happen!"
    )
    payment.error_message = "Cannot activate FREE plan through payment"
    payment.save()

    SecurityAuditLogger.log_security_event(
        user=payment.user,
        event_type='FREE_PLAN_PAYMENT_ATTEMPT',
        severity='high',
        details={
            'payment_id': str(payment.id),
            'plan_code': plan.code,
            'amount': float(payment.amount)
        }
    )


def _activate_subscription(payment, plan, payment_method_id, payment_object):
    """Activate or extend subscription after successful payment."""
    from apps.billing.services import activate_or_extend_subscription, invalidate_user_plan_cache

    duration_days = plan.duration_days if plan.duration_days > 0 else settings.BILLING_PLUS_DURATION_DAYS

    # Convert TEST_LIVE to MONTHLY
    target_plan_code = plan.code
    if plan.code == 'TEST_LIVE':
        target_plan_code = 'MONTHLY'
        logger.info(f"Converting TEST_LIVE payment to MONTHLY subscription for user {payment.user.id}")

    activate_or_extend_subscription(
        user=payment.user,
        plan_code=target_plan_code,
        duration_days=duration_days
    )

    # Save payment_method_id for recurring
    if payment_method_id and payment.save_payment_method:
        subscription = Subscription.objects.get(user=payment.user)
        subscription.yookassa_payment_method_id = payment_method_id
        subscription.auto_renew = True

        # Extract card info
        if payment_object.payment_method and hasattr(payment_object.payment_method, 'card'):
            card_info = payment_object.payment_method.card
            if card_info:
                if hasattr(card_info, 'last4'):
                    subscription.card_mask = f"•••• {card_info.last4}"
                if hasattr(card_info, 'card_type'):
                    subscription.card_brand = card_info.card_type.upper()

        subscription.save()

    logger.info(f"Payment {payment.id} succeeded. Subscription updated for plan {plan.code}")

    SecurityAuditLogger.log_payment_success(
        user=payment.user,
        payment_id=str(payment.id),
        amount=float(payment.amount),
        plan=plan.code
    )
    
    # Mark as processed for idempotency
    mark_webhook_processed(payment)


def handle_payment_canceled(payment_object):
    """
    Handle payment.canceled event.
    Payment was canceled by user or expired.
    """
    try:
        payment = Payment.objects.get(yookassa_payment_id=payment_object.id)
        payment.mark_as_canceled()

        cancellation_details = payment_object.cancellation_details
        if cancellation_details:
            payment.error_message = f"{cancellation_details.party}: {cancellation_details.reason}"
            payment.save()

        logger.info(f"Payment {payment.id} canceled")

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
    Handle refund.succeeded event.
    Refund was successfully processed.
    """
    try:
        payment = Payment.objects.get(yookassa_payment_id=refund_object.payment_id)

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

        payment.mark_as_refunded()

        if payment.subscription:
            logger.info(f"Refund for subscription {payment.subscription.id} processed")

        logger.info(f"Refund {refund.id} for payment {payment.id} succeeded")

    except Payment.DoesNotExist:
        logger.error(f"Payment not found for refund payment_id: {refund_object.payment_id}")
    except Exception as e:
        logger.error(f"Error handling refund succeeded: {str(e)}", exc_info=True)
