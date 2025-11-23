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
