"""
Сервис для работы с YooKassa API.

SECURITY: YooKassa credentials are configured per-instance to avoid
global state and potential leakage through logs.
"""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from yookassa import Configuration, Payment as YooKassaPayment
from yookassa.domain.notification import WebhookNotificationFactory
from decimal import Decimal
import uuid
import logging

logger = logging.getLogger(__name__)


class YooKassaService:
    """
    Сервис для работы с YooKassa API.

    SECURITY: Credentials are validated on initialization and configured
    per-request to avoid global state pollution.
    """

    def __init__(self):
        """
        Initialize YooKassa service with credential validation.

        SECURITY: Validates that credentials are properly configured
        before allowing any operations.
        """
        self.shop_id = settings.YOOKASSA_SHOP_ID
        self.secret_key = settings.YOOKASSA_SECRET_KEY

        # Validate credentials exist
        if not self.shop_id or not self.secret_key:
            raise ImproperlyConfigured(
                "YooKassa credentials not configured. "
                "Set YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY environment variables."
            )

        # Validate shop_id format (should be numeric)
        if not str(self.shop_id).isdigit():
            raise ImproperlyConfigured(
                f"Invalid YOOKASSA_SHOP_ID format: {self.shop_id}. "
                "Shop ID should be numeric."
            )

        # Validate secret_key format (should start with test_ or live_)
        if not (self.secret_key.startswith('test_') or self.secret_key.startswith('live_')):
            raise ImproperlyConfigured(
                "Invalid YOOKASSA_SECRET_KEY format. "
                "Secret key must start with 'test_' or 'live_'."
            )

        # Check for placeholder values
        if self.secret_key.startswith('test_your') or self.secret_key.startswith('live_your'):
            raise ImproperlyConfigured(
                "YOOKASSA_SECRET_KEY appears to be a placeholder value. "
                "Replace it with your actual YooKassa secret key."
            )

        # Configure YooKassa for this instance
        self._configure()

        logger.info(
            f"YooKassa service initialized. Shop ID: {self.shop_id}, "
            f"Environment: {'TEST' if self.secret_key.startswith('test_') else 'PRODUCTION'}"
        )

    def _configure(self):
        """
        Configure YooKassa SDK with credentials.

        SECURITY: This is called per-instance to avoid global state.
        """
        Configuration.account_id = self.shop_id
        Configuration.secret_key = self.secret_key

    def create_payment(
        self,
        amount: Decimal,
        description: str,
        return_url: str,
        save_payment_method: bool = True,
        metadata: dict = None
    ) -> dict:
        """
        Создаёт платёж в YooKassa.

        Args:
            amount: Сумма платежа
            description: Описание платежа
            return_url: URL для возврата после оплаты
            save_payment_method: Сохранить способ оплаты для рекуррентных платежей
            metadata: Дополнительные метаданные

        Returns:
            dict: Данные платежа от YooKassa
        """
        try:
            idempotence_key = str(uuid.uuid4())

            payment_data = {
                "amount": {
                    "value": str(amount),
                    "currency": "RUB"
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": return_url
                },
                "capture": True,  # Автоматическое списание
                "description": description,
                "metadata": metadata or {},
            }

            # Добавляем сохранение способа оплаты для рекуррентных платежей
            if save_payment_method:
                payment_data["save_payment_method"] = True

            payment = YooKassaPayment.create(payment_data, idempotence_key)

            return {
                'id': payment.id,
                'status': payment.status,
                'amount': payment.amount.value,
                'currency': payment.amount.currency,
                'confirmation_url': payment.confirmation.confirmation_url,
                'payment_method_id': getattr(payment.payment_method, 'id', None) if payment.payment_method else None,
            }

        except Exception as e:
            logger.error(f"YooKassa payment creation error: {str(e)}")
            raise

    def create_recurring_payment(
        self,
        amount: Decimal,
        description: str,
        payment_method_id: str,
        metadata: dict = None
    ) -> dict:
        """
        Создаёт рекуррентный платёж с сохранённым способом оплаты.

        Args:
            amount: Сумма платежа
            description: Описание платежа
            payment_method_id: ID сохранённого способа оплаты
            metadata: Дополнительные метаданные

        Returns:
            dict: Данные платежа от YooKassa
        """
        try:
            idempotence_key = str(uuid.uuid4())

            payment_data = {
                "amount": {
                    "value": str(amount),
                    "currency": "RUB"
                },
                "capture": True,
                "payment_method_id": payment_method_id,
                "description": description,
                "metadata": metadata or {},
            }

            payment = YooKassaPayment.create(payment_data, idempotence_key)

            return {
                'id': payment.id,
                'status': payment.status,
                'amount': payment.amount.value,
                'currency': payment.amount.currency,
                'payment_method_id': payment_method_id,
            }

        except Exception as e:
            logger.error(f"YooKassa recurring payment creation error: {str(e)}")
            raise

    def get_payment_info(self, payment_id: str) -> dict:
        """
        Получает информацию о платеже.

        Args:
            payment_id: ID платежа в YooKassa

        Returns:
            dict: Информация о платеже
        """
        try:
            payment = YooKassaPayment.find_one(payment_id)

            return {
                'id': payment.id,
                'status': payment.status,
                'amount': payment.amount.value,
                'currency': payment.amount.currency,
                'payment_method_id': getattr(payment.payment_method, 'id', None) if payment.payment_method else None,
                'paid': payment.paid,
                'created_at': payment.created_at,
            }

        except Exception as e:
            logger.error(f"YooKassa get payment info error: {str(e)}")
            raise

    def cancel_payment(self, payment_id: str) -> dict:
        """
        Отменяет платёж.

        Args:
            payment_id: ID платежа в YooKassa

        Returns:
            dict: Информация об отменённом платеже
        """
        try:
            idempotence_key = str(uuid.uuid4())
            payment = YooKassaPayment.cancel(payment_id, idempotence_key)

            return {
                'id': payment.id,
                'status': payment.status,
            }

        except Exception as e:
            logger.error(f"YooKassa cancel payment error: {str(e)}")
            raise

    @staticmethod
    def parse_webhook_notification(request_body: dict, request_headers: dict = None):
        """
        Парсит webhook уведомление от YooKassa.

        Args:
            request_body: Тело запроса (JSON)
            request_headers: Заголовки запроса (опционально)

        Returns:
            WebhookNotification: Объект уведомления
        """
        try:
            notification = WebhookNotificationFactory().create(request_body)
            return notification

        except Exception as e:
            logger.error(f"YooKassa webhook parsing error: {str(e)}")
            raise


# ============================================================
# Сервисы для создания платежей (без SDK)
# ============================================================

def create_subscription_payment(user, plan_code: str, return_url: str = None, save_payment_method: bool = True):
    """
    Универсальный сервис для создания платежа подписки.

    Args:
        user: Объект пользователя Django
        plan_code: Код плана (MONTHLY, YEARLY, и т.д.)
        return_url: URL для возврата после оплаты (опционально)
        save_payment_method: Сохранять ли способ оплаты для рекуррентных платежей (по умолчанию True)

    Returns:
        Tuple (Payment, confirmation_url)

    Raises:
        ValueError: Если план не найден или невалиден
        Exception: При ошибке создания платежа
    """
    from django.db import transaction
    from django.utils import timezone
    from datetime import timedelta
    from .models import SubscriptionPlan, Payment, Subscription
    from .yookassa_client import YooKassaClient, PaymentCreateError
    from django.conf import settings

    # Находим план
    try:
        plan = SubscriptionPlan.objects.get(name=plan_code, is_active=True)
    except SubscriptionPlan.DoesNotExist:
        raise ValueError(f"Plan {plan_code} not found or not active")

    # Проверяем, что это платный план
    if plan.price <= 0:
        raise ValueError(f"Cannot create payment for FREE plan")

    # Определяем return_url
    if not return_url:
        return_url = settings.YOOKASSA_RETURN_URL

    # Создаем запись платежа в БД
    with transaction.atomic():
        # Получаем текущую подписку пользователя (или создаем если нет)
        subscription, _ = Subscription.objects.select_for_update().get_or_create(
            user=user,
            defaults={
                'plan': SubscriptionPlan.objects.get(name='FREE'),
                'start_date': timezone.now(),
                'end_date': timezone.now() + timedelta(days=365 * 10),
                'is_active': True
            }
        )

        # Создаем Payment с статусом PENDING
        payment = Payment.objects.create(
            user=user,
            subscription=subscription,
            plan=plan,
            amount=plan.price,
            currency='RUB',
            status='PENDING',
            provider='YOOKASSA',
            description=f'Подписка {plan.display_name}',
            save_payment_method=save_payment_method,
        )

        # Генерируем idempotence_key
        idempotence_key = str(uuid.uuid4())

        try:
            # Создаем платеж через наш клиент (без SDK)
            yookassa_client = YooKassaClient()
            response = yookassa_client.create_payment(
                user=user,
                plan=plan,
                idempotence_key=idempotence_key,
                return_url=return_url,
                save_payment_method=save_payment_method
            )

            # Сохраняем данные от YooKassa
            payment.yookassa_payment_id = response['id']
            payment.metadata = {
                'idempotence_key': idempotence_key,
                'raw_request': {
                    'plan_code': plan.name,
                    'amount': str(plan.price),
                    'return_url': return_url,
                },
                'raw_response': response,
            }
            payment.save()

            # Извлекаем confirmation_url
            confirmation_url = response['confirmation']['confirmation_url']

            logger.info(
                f"Payment {payment.id} created for user {user.username}. "
                f"Plan: {plan_code}, YooKassa ID: {payment.yookassa_payment_id}"
            )

            return payment, confirmation_url

        except PaymentCreateError as e:
            # Помечаем платеж как неудачный
            payment.status = 'FAILED'
            payment.error_message = str(e)
            payment.save()
            raise

        except Exception as e:
            # Любая другая ошибка
            payment.status = 'FAILED'
            payment.error_message = f"Unexpected error: {str(e)}"
            payment.save()
            logger.error(f"Error creating payment: {str(e)}", exc_info=True)
            raise


def create_monthly_subscription_payment(user, return_url: str = None):
    """
    [DEPRECATED] Создает платеж для месячной подписки.
    Используйте create_subscription_payment(user, 'MONTHLY', return_url) вместо этого.

    Args:
        user: Объект пользователя Django
        return_url: URL для возврата после оплаты (опционально)

    Returns:
        Tuple (Payment, confirmation_url)
    """
    return create_subscription_payment(user, 'MONTHLY', return_url)


def activate_or_extend_subscription(user, plan_code: str, duration_days: int):
    """
    Активирует или продлевает подписку пользователя.

    Args:
        user: Объект пользователя
        plan_code: Код плана (FREE, MONTHLY, YEARLY)
        duration_days: Количество дней продления

    Returns:
        Subscription: Обновленная подписка
    """
    from django.db import transaction
    from django.utils import timezone
    from datetime import timedelta
    from .models import SubscriptionPlan, Subscription

    with transaction.atomic():
        # Находим план
        try:
            plan = SubscriptionPlan.objects.get(name=plan_code, is_active=True)
        except SubscriptionPlan.DoesNotExist:
            raise ValueError(f"Plan {plan_code} not found or not active")

        # Получаем или создаем подписку
        subscription, created = Subscription.objects.select_for_update().get_or_create(
            user=user,
            defaults={
                'plan': plan,
                'start_date': timezone.now(),
                'end_date': timezone.now() + timedelta(days=duration_days),
                'is_active': True,
            }
        )

        if not created:
            # Подписка существует - продлеваем
            now = timezone.now()

            if subscription.is_expired():
                # Подписка истекла - начинаем с текущего момента
                subscription.start_date = now
                subscription.end_date = now + timedelta(days=duration_days)
            else:
                # Подписка активна - добавляем к текущей дате окончания
                subscription.end_date += timedelta(days=duration_days)

            # Обновляем план, если он изменился
            if subscription.plan != plan:
                subscription.plan = plan

            subscription.is_active = True
            subscription.save()

        logger.info(
            f"Subscription for user {user.username} activated/extended. "
            f"Plan: {plan_code}, Expires: {subscription.end_date}"
        )

        return subscription


def get_effective_plan_for_user(user):
    """
    Получает действующий тарифный план для пользователя.

    Логика:
    - Если есть активная подписка с неистекшим expires_at → возвращаем её план
    - Иначе возвращаем бесплатный план (FREE)

    Args:
        user: Объект пользователя

    Returns:
        SubscriptionPlan: Действующий план пользователя
    """
    from .models import SubscriptionPlan, Subscription
    from django.utils import timezone

    try:
        # Пытаемся получить подписку пользователя
        subscription = Subscription.objects.select_related('plan').get(user=user)

        # Проверяем, активна ли подписка
        if subscription.is_active and not subscription.is_expired():
            return subscription.plan

    except Subscription.DoesNotExist:
        pass

    # Если нет активной подписки или подписка истекла - возвращаем FREE
    try:
        free_plan = SubscriptionPlan.objects.get(name='FREE', is_active=True)
        return free_plan
    except SubscriptionPlan.DoesNotExist:
        # В крайнем случае, если FREE план не найден, создаем его на лету
        logger.warning("FREE plan not found, creating default")
        free_plan = SubscriptionPlan.objects.create(
            name='FREE',
            display_name='Бесплатный',
            price=0,
            duration_days=0,
            daily_photo_limit=3,
            is_active=True
        )
        return free_plan
