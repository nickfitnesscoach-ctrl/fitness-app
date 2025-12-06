"""
YooKassa API клиент без использования SDK.
Прямая работа через requests для полного контроля над запросами.
"""

import base64
import uuid
import logging
import requests
from decimal import Decimal
from typing import Dict, Optional
from django.conf import settings

logger = logging.getLogger(__name__)


class PaymentCreateError(Exception):
    """Ошибка при создании платежа в YooKassa."""
    pass


class YooKassaClient:
    """
    Клиент для работы с YooKassa API через requests (без SDK).

    Используется для создания платежей и получения информации о них.
    """

    API_URL = "https://api.yookassa.ru/v3"

    def __init__(self):
        """Инициализация клиента с проверкой credentials."""
        self.shop_id = settings.YOOKASSA_SHOP_ID
        self.api_key = settings.YOOKASSA_SECRET_KEY

        if not self.shop_id or not self.api_key:
            raise ValueError(
                "YooKassa credentials not configured. "
                "Set YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY environment variables."
            )

        # Создаем базовый заголовок авторизации
        credentials = f"{self.shop_id}:{self.api_key}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        self.auth_header = f"Basic {encoded_credentials}"

        logger.info(
            f"YooKassa client initialized. Shop ID: {self.shop_id}, "
            f"Mode: {'PRODUCTION' if self.api_key.startswith('live_') else 'TEST'}"
        )

    def _get_headers(self, idempotence_key: str) -> Dict[str, str]:
        """
        Создает заголовки для запроса к YooKassa API.

        Args:
            idempotence_key: Ключ идемпотентности

        Returns:
            Dict со всеми необходимыми заголовками
        """
        return {
            "Authorization": self.auth_header,
            "Idempotence-Key": idempotence_key,
            "Content-Type": "application/json",
        }

    def create_payment(
        self,
        user,
        plan,
        idempotence_key: str,
        return_url: str,
        save_payment_method: bool = True
    ) -> Dict:
        """
        Создает платеж в YooKassa.

        Args:
            user: Объект пользователя Django
            plan: Объект тарифного плана (SubscriptionPlan)
            idempotence_key: Ключ идемпотентности (обычно uuid4)
            return_url: URL для возврата после оплаты
            save_payment_method: Сохранить способ оплаты для рекуррентных платежей

        Returns:
            Dict с данными созданного платежа

        Raises:
            PaymentCreateError: При ошибке создания платежа
        """
        url = f"{self.API_URL}/payments"

        # Формируем тело запроса
        payment_data = {
            "amount": {
                "value": str(plan.price),
                "currency": "RUB"
            },
            "capture": True,  # Автоматическое списание
            "description": f"Подписка {plan.display_name} для {user.username}",
            "confirmation": {
                "type": "redirect",
                "return_url": return_url
            },
            "metadata": {
                "user_id": str(user.id),
                "plan_code": plan.code,
                "username": user.username
            }
        }

        # Добавляем сохранение способа оплаты для рекуррентных платежей
        if save_payment_method:
            payment_data["save_payment_method"] = True

        try:
            # Выполняем запрос
            response = requests.post(
                url,
                json=payment_data,
                headers=self._get_headers(idempotence_key),
                timeout=10
            )

            # Проверяем статус ответа
            if response.status_code not in [200, 201]:
                error_msg = f"YooKassa API error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise PaymentCreateError(error_msg)

            # Парсим ответ
            response_data = response.json()

            logger.info(
                f"Payment created successfully. ID: {response_data.get('id')}, "
                f"Status: {response_data.get('status')}"
            )

            return response_data

        except requests.RequestException as e:
            error_msg = f"Request to YooKassa failed: {str(e)}"
            logger.error(error_msg)
            raise PaymentCreateError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error creating payment: {str(e)}"
            logger.error(error_msg)
            raise PaymentCreateError(error_msg)

    def get_payment_info(self, payment_id: str) -> Dict:
        """
        Получает информацию о платеже.

        Args:
            payment_id: ID платежа в YooKassa

        Returns:
            Dict с информацией о платеже

        Raises:
            PaymentCreateError: При ошибке получения информации
        """
        url = f"{self.API_URL}/payments/{payment_id}"

        try:
            response = requests.get(
                url,
                headers=self._get_headers(str(uuid.uuid4())),
                timeout=10
            )

            if response.status_code != 200:
                error_msg = f"YooKassa API error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise PaymentCreateError(error_msg)

            return response.json()

        except requests.RequestException as e:
            error_msg = f"Request to YooKassa failed: {str(e)}"
            logger.error(error_msg)
            raise PaymentCreateError(error_msg)

    def cancel_payment(self, payment_id: str) -> Dict:
        """
        Отменяет платеж.

        Args:
            payment_id: ID платежа в YooKassa

        Returns:
            Dict с информацией об отмененном платеже

        Raises:
            PaymentCreateError: При ошибке отмены платежа
        """
        url = f"{self.API_URL}/payments/{payment_id}/cancel"

        try:
            response = requests.post(
                url,
                headers=self._get_headers(str(uuid.uuid4())),
                timeout=10
            )

            if response.status_code != 200:
                error_msg = f"YooKassa API error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise PaymentCreateError(error_msg)

            return response.json()

        except requests.RequestException as e:
            error_msg = f"Request to YooKassa failed: {str(e)}"
            logger.error(error_msg)
            raise PaymentCreateError(error_msg)
