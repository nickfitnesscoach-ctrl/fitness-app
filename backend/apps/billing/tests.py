"""
Тесты для billing приложения.
"""

from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status as http_status
from datetime import timedelta

from .models import SubscriptionPlan, Subscription, Payment
from .services import create_monthly_subscription_payment, activate_or_extend_subscription, get_effective_plan_for_user
from .usage import DailyUsage


class SubscriptionPlanTestCase(TestCase):
    """Тесты для модели SubscriptionPlan."""

    def setUp(self):
        """Создаем тестовые планы."""
        self.free_plan = SubscriptionPlan.objects.create(
            name='FREE',
            display_name='Бесплатный',
            price=Decimal('0.00'),
            duration_days=0,
            max_photos_per_day=3,
            is_active=True
        )

        self.monthly_plan = SubscriptionPlan.objects.create(
            name='MONTHLY',
            display_name='Pro Месячный',
            price=Decimal('199.00'),
            duration_days=30,
            max_photos_per_day=-1,
            is_active=True
        )

    def test_plan_creation(self):
        """Тест создания планов."""
        self.assertEqual(SubscriptionPlan.objects.count(), 2)
        self.assertEqual(self.free_plan.name, 'FREE')
        self.assertEqual(self.monthly_plan.price, Decimal('199.00'))


class CreateMonthlyPaymentTestCase(TestCase):
    """Тесты для создания платежей через API."""

    def setUp(self):
        """Настройка тестовых данных."""
        self.client = APIClient()

        # Создаем пользователя
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        # Создаем планы
        self.free_plan = SubscriptionPlan.objects.create(
            name='FREE',
            display_name='Бесплатный',
            price=Decimal('0.00'),
            duration_days=0,
            is_active=True
        )

        self.monthly_plan = SubscriptionPlan.objects.create(
            name='MONTHLY',
            display_name='Pro Месячный',
            price=Decimal('199.00'),
            duration_days=30,
            is_active=True
        )

        # Создаем бесплатную подписку для пользователя
        self.subscription = Subscription.objects.create(
            user=self.user,
            plan=self.free_plan,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=365),
            is_active=True
        )

    @patch('apps.billing.yookassa_client.YooKassaClient.create_payment')
    def test_create_plus_payment_api(self, mock_create_payment):
        """Тест создания платежа через API endpoint."""
        # Мокаем ответ от YooKassa
        mock_create_payment.return_value = {
            'id': 'test-payment-id-123',
            'status': 'pending',
            'amount': {'value': '199.00', 'currency': 'RUB'},
            'confirmation': {
                'type': 'redirect',
                'confirmation_url': 'https://yookassa.ru/payments/test-payment-id-123'
            },
            'metadata': {}
        }

        # Авторизуемся
        self.client.force_authenticate(user=self.user)

        # Отправляем запрос
        url = reverse('billing:create-plus-payment')
        response = self.client.post(url, {}, format='json')

        # Проверяем ответ
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertIn('payment_id', response.data)
        self.assertIn('yookassa_payment_id', response.data)
        self.assertIn('confirmation_url', response.data)
        self.assertEqual(response.data['yookassa_payment_id'], 'test-payment-id-123')

        # Проверяем, что платеж создан в БД
        payment = Payment.objects.get(yookassa_payment_id='test-payment-id-123')
        self.assertEqual(payment.status, 'PENDING')
        self.assertEqual(payment.user, self.user)
        self.assertEqual(payment.plan, self.monthly_plan)
        self.assertEqual(payment.amount, Decimal('199.00'))

    def test_create_plus_payment_without_auth(self):
        """Тест создания платежа без авторизации."""
        url = reverse('billing:create-plus-payment')
        response = self.client.post(url, {}, format='json')

        # Должны получить 401 Unauthorized
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)


class WebhookPaymentSucceededTestCase(TestCase):
    """Тесты для webhook обработчика payment.succeeded."""

    def setUp(self):
        """Настройка тестовых данных."""
        self.client = APIClient()

        # Создаем пользователя
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        # Создаем планы
        self.free_plan = SubscriptionPlan.objects.create(
            name='FREE',
            display_name='Бесплатный',
            price=Decimal('0.00'),
            duration_days=0,
            is_active=True
        )

        self.monthly_plan = SubscriptionPlan.objects.create(
            name='MONTHLY',
            display_name='Pro Месячный',
            price=Decimal('199.00'),
            duration_days=30,
            is_active=True
        )

        # Создаем подписку
        self.subscription = Subscription.objects.create(
            user=self.user,
            plan=self.free_plan,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=365),
            is_active=True
        )

        # Создаем платеж
        self.payment = Payment.objects.create(
            user=self.user,
            subscription=self.subscription,
            plan=self.monthly_plan,
            amount=Decimal('199.00'),
            currency='RUB',
            status='PENDING',
            yookassa_payment_id='test-payment-id-webhook',
            provider='YOOKASSA'
        )

    @patch('apps.billing.webhooks.YooKassaService.parse_webhook_notification')
    def test_webhook_payment_succeeded_creates_subscription(self, mock_parse):
        """Тест обработки webhook payment.succeeded."""
        # Мокаем webhook notification
        mock_notification = MagicMock()
        mock_notification.event = 'payment.succeeded'
        mock_notification.object.id = 'test-payment-id-webhook'
        mock_notification.object.payment_method = None
        mock_parse.return_value = mock_notification

        # Отправляем webhook
        url = reverse('billing:yookassa-webhook')
        webhook_data = {
            'type': 'notification',
            'event': 'payment.succeeded',
            'object': {
                'id': 'test-payment-id-webhook',
                'status': 'succeeded',
                'amount': {'value': '199.00', 'currency': 'RUB'}
            }
        }

        response = self.client.post(url, webhook_data, format='json')

        # Проверяем ответ
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

        # Проверяем, что платеж обновлен
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'SUCCEEDED')
        self.assertIsNotNone(self.payment.paid_at)

        # Проверяем, что подписка обновлена
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.plan, self.monthly_plan)
        self.assertTrue(self.subscription.is_active)


class GetSubscriptionStatusTestCase(TestCase):
    """Тесты для endpoint /billing/me/."""

    def setUp(self):
        """Настройка тестовых данных."""
        self.client = APIClient()

        # Создаем пользователя
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        # Создаем план
        self.monthly_plan = SubscriptionPlan.objects.create(
            name='MONTHLY',
            display_name='Pro Месячный',
            price=Decimal('199.00'),
            duration_days=30,
            is_active=True
        )

        # Создаем подписку
        self.subscription = Subscription.objects.create(
            user=self.user,
            plan=self.monthly_plan,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            is_active=True
        )

    def test_get_subscription_status(self):
        """Тест получения статуса подписки."""
        self.client.force_authenticate(user=self.user)

        url = reverse('billing:subscription-status')
        response = self.client.get(url)

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['plan_code'], 'MONTHLY')
        self.assertEqual(response.data['plan_name'], 'Pro Месячный')
        self.assertTrue(response.data['is_active'])
        self.assertIsNotNone(response.data['expires_at'])

    def test_get_subscription_status_without_auth(self):
        """Тест получения статуса без авторизации."""
        url = reverse('billing:subscription-status')
        response = self.client.get(url)

        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)


class ActivateOrExtendSubscriptionTestCase(TestCase):
    """Тесты для сервиса activate_or_extend_subscription."""

    def setUp(self):
        """Настройка тестовых данных."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        self.monthly_plan = SubscriptionPlan.objects.create(
            name='MONTHLY',
            display_name='Pro Месячный',
            price=Decimal('199.00'),
            duration_days=30,
            is_active=True
        )

        self.free_plan = SubscriptionPlan.objects.create(
            name='FREE',
            display_name='Бесплатный',
            price=Decimal('0.00'),
            duration_days=0,
            is_active=True
        )

    def test_activate_new_subscription(self):
        """Тест активации новой подписки."""
        # Создаем бесплатную подписку
        subscription = Subscription.objects.create(
            user=self.user,
            plan=self.free_plan,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=365),
            is_active=True
        )

        # Активируем месячную подписку
        updated_subscription = activate_or_extend_subscription(
            user=self.user,
            plan_code='MONTHLY',
            duration_days=30
        )

        self.assertEqual(updated_subscription.plan, self.monthly_plan)
        self.assertTrue(updated_subscription.is_active)

    def test_extend_active_subscription(self):
        """Тест продления активной подписки."""
        now = timezone.now()
        end_date = now + timedelta(days=10)

        subscription = Subscription.objects.create(
            user=self.user,
            plan=self.monthly_plan,
            start_date=now,
            end_date=end_date,
            is_active=True
        )

        # Продлеваем подписку
        updated_subscription = activate_or_extend_subscription(
            user=self.user,
            plan_code='MONTHLY',
            duration_days=30
        )

        # Проверяем, что дата окончания увеличилась
        expected_end_date = end_date + timedelta(days=30)
        self.assertAlmostEqual(
            updated_subscription.end_date.timestamp(),
            expected_end_date.timestamp(),
            delta=1
        )


# ============================================================
# NEW TESTS: Settings screen endpoints
# ============================================================

class SubscriptionDetailsTestCase(TestCase):
    """Тесты для GET /api/v1/billing/subscription/"""

    def setUp(self):
        """Настройка тестовых данных."""
        self.client = APIClient()

        # Создаем пользователя
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        # Создаем планы
        self.free_plan = SubscriptionPlan.objects.create(
            name='FREE',
            display_name='Бесплатный',
            price=Decimal('0.00'),
            duration_days=0,
            is_active=True
        )

        self.monthly_plan = SubscriptionPlan.objects.create(
            name='MONTHLY',
            display_name='Pro Месячный',
            price=Decimal('299.00'),
            duration_days=30,
            is_active=True
        )

    def test_get_subscription_free_user(self):
        """Тест для пользователя с бесплатным планом без подписки."""
        self.client.force_authenticate(user=self.user)

        url = reverse('billing:subscription-details')
        response = self.client.get(url)

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['plan'], 'free')
        self.assertEqual(response.data['plan_display'], 'Free')
        self.assertIsNone(response.data['expires_at'])
        self.assertTrue(response.data['is_active'])
        self.assertFalse(response.data['autorenew_available'])
        self.assertFalse(response.data['autorenew_enabled'])
        self.assertFalse(response.data['payment_method']['is_attached'])
        self.assertIsNone(response.data['payment_method']['card_mask'])
        self.assertIsNone(response.data['payment_method']['card_brand'])

    def test_get_subscription_free_user_with_subscription(self):
        """Тест для пользователя с бесплатной подпиской."""
        # Создаем бесплатную подписку
        Subscription.objects.create(
            user=self.user,
            plan=self.free_plan,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=365),
            is_active=True
        )

        self.client.force_authenticate(user=self.user)

        url = reverse('billing:subscription-details')
        response = self.client.get(url)

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['plan'], 'free')
        self.assertEqual(response.data['plan_display'], 'Free')
        self.assertIsNone(response.data['expires_at'])

    def test_get_subscription_pro_without_card(self):
        """Тест для пользователя с PRO без привязанной карты."""
        # Создаем PRO подписку без payment_method
        end_date = timezone.now() + timedelta(days=30)
        Subscription.objects.create(
            user=self.user,
            plan=self.monthly_plan,
            start_date=timezone.now(),
            end_date=end_date,
            is_active=True,
            auto_renew=False
        )

        self.client.force_authenticate(user=self.user)

        url = reverse('billing:subscription-details')
        response = self.client.get(url)

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['plan'], 'pro')
        self.assertEqual(response.data['plan_display'], 'PRO')
        self.assertIsNotNone(response.data['expires_at'])
        self.assertTrue(response.data['is_active'])
        self.assertFalse(response.data['autorenew_available'])  # Нет карты
        self.assertFalse(response.data['autorenew_enabled'])
        self.assertFalse(response.data['payment_method']['is_attached'])

    def test_get_subscription_pro_with_card(self):
        """Тест для пользователя с PRO и привязанной картой."""
        # Создаем PRO подписку с payment_method
        end_date = timezone.now() + timedelta(days=30)
        Subscription.objects.create(
            user=self.user,
            plan=self.monthly_plan,
            start_date=timezone.now(),
            end_date=end_date,
            is_active=True,
            auto_renew=True,
            yookassa_payment_method_id='pm_test_123',
            card_mask='•••• 1234',
            card_brand='Visa'
        )

        self.client.force_authenticate(user=self.user)

        url = reverse('billing:subscription-details')
        response = self.client.get(url)

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['plan'], 'pro')
        self.assertTrue(response.data['is_active'])
        self.assertTrue(response.data['autorenew_available'])  # Есть карта
        self.assertTrue(response.data['autorenew_enabled'])
        self.assertTrue(response.data['payment_method']['is_attached'])
        self.assertEqual(response.data['payment_method']['card_mask'], '•••• 1234')
        self.assertEqual(response.data['payment_method']['card_brand'], 'Visa')

    def test_get_subscription_without_auth(self):
        """Тест без авторизации."""
        url = reverse('billing:subscription-details')
        response = self.client.get(url)

        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)


class AutoRenewToggleTestCase(TestCase):
    """Тесты для POST /api/v1/billing/subscription/autorenew/"""

    def setUp(self):
        """Настройка тестовых данных."""
        self.client = APIClient()

        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        self.free_plan = SubscriptionPlan.objects.create(
            name='FREE',
            display_name='Бесплатный',
            price=Decimal('0.00'),
            duration_days=0,
            is_active=True
        )

        self.monthly_plan = SubscriptionPlan.objects.create(
            name='MONTHLY',
            display_name='Pro Месячный',
            price=Decimal('299.00'),
            duration_days=30,
            is_active=True
        )

    def test_toggle_autorenew_enable_without_card(self):
        """Попытка включить автопродление без привязанной карты."""
        # Создаем PRO подписку без payment_method
        Subscription.objects.create(
            user=self.user,
            plan=self.monthly_plan,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            is_active=True,
            auto_renew=False
        )

        self.client.force_authenticate(user=self.user)

        url = reverse('billing:set-auto-renew')
        response = self.client.post(url, {'enabled': True}, format='json')

        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error']['code'], 'payment_method_required')

    def test_toggle_autorenew_enable_with_card(self):
        """Включение автопродления с привязанной картой."""
        # Создаем PRO подписку с payment_method
        Subscription.objects.create(
            user=self.user,
            plan=self.monthly_plan,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            is_active=True,
            auto_renew=False,
            yookassa_payment_method_id='pm_test_123',
            card_mask='•••• 1234',
            card_brand='Visa'
        )

        self.client.force_authenticate(user=self.user)

        url = reverse('billing:set-auto-renew')
        response = self.client.post(url, {'enabled': True}, format='json')

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertTrue(response.data['autorenew_enabled'])

        # Проверяем, что флаг обновился в БД
        subscription = Subscription.objects.get(user=self.user)
        self.assertTrue(subscription.auto_renew)

    def test_toggle_autorenew_disable(self):
        """Отключение автопродления."""
        # Создаем PRO подписку с включенным автопродлением
        Subscription.objects.create(
            user=self.user,
            plan=self.monthly_plan,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            is_active=True,
            auto_renew=True,
            yookassa_payment_method_id='pm_test_123',
            card_mask='•••• 1234',
            card_brand='Visa'
        )

        self.client.force_authenticate(user=self.user)

        url = reverse('billing:set-auto-renew')
        response = self.client.post(url, {'enabled': False}, format='json')

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertFalse(response.data['autorenew_enabled'])

        # Проверяем, что флаг обновился в БД
        subscription = Subscription.objects.get(user=self.user)
        self.assertFalse(subscription.auto_renew)

    def test_toggle_autorenew_free_plan(self):
        """Попытка включить автопродление на бесплатном плане."""
        Subscription.objects.create(
            user=self.user,
            plan=self.free_plan,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=365),
            is_active=True
        )

        self.client.force_authenticate(user=self.user)

        url = reverse('billing:set-auto-renew')
        response = self.client.post(url, {'enabled': True}, format='json')

        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error']['code'], 'NOT_AVAILABLE_FOR_FREE')


class PaymentMethodDetailsTestCase(TestCase):
    """Тесты для GET /api/v1/billing/payment-method/"""

    def setUp(self):
        """Настройка тестовых данных."""
        self.client = APIClient()

        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        self.monthly_plan = SubscriptionPlan.objects.create(
            name='MONTHLY',
            display_name='Pro Месячный',
            price=Decimal('299.00'),
            duration_days=30,
            is_active=True
        )

    def test_get_payment_method_without_card(self):
        """Получение данных о способе оплаты без привязанной карты."""
        Subscription.objects.create(
            user=self.user,
            plan=self.monthly_plan,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            is_active=True
        )

        self.client.force_authenticate(user=self.user)

        url = reverse('billing:payment-method-details')
        response = self.client.get(url)

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertFalse(response.data['is_attached'])
        self.assertIsNone(response.data['card_mask'])
        self.assertIsNone(response.data['card_brand'])

    def test_get_payment_method_with_card(self):
        """Получение данных о привязанной карте."""
        Subscription.objects.create(
            user=self.user,
            plan=self.monthly_plan,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            is_active=True,
            yookassa_payment_method_id='pm_test_123',
            card_mask='•••• 5678',
            card_brand='MasterCard'
        )

        self.client.force_authenticate(user=self.user)

        url = reverse('billing:payment-method-details')
        response = self.client.get(url)

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertTrue(response.data['is_attached'])
        self.assertEqual(response.data['card_mask'], '•••• 5678')
        self.assertEqual(response.data['card_brand'], 'MasterCard')


class PaymentsHistoryTestCase(TestCase):
    """Тесты для GET /api/v1/billing/payments/"""

    def setUp(self):
        """Настройка тестовых данных."""
        self.client = APIClient()

        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        self.monthly_plan = SubscriptionPlan.objects.create(
            name='MONTHLY',
            display_name='Pro Месячный',
            price=Decimal('299.00'),
            duration_days=30,
            is_active=True
        )

        self.subscription = Subscription.objects.create(
            user=self.user,
            plan=self.monthly_plan,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            is_active=True
        )

    def test_get_payments_empty(self):
        """Получение истории платежей без платежей."""
        self.client.force_authenticate(user=self.user)

        url = reverse('billing:payments-history')
        response = self.client.get(url)

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 0)

    def test_get_payments_with_data(self):
        """Получение истории с несколькими платежами."""
        # Создаем несколько платежей
        payment1 = Payment.objects.create(
            user=self.user,
            subscription=self.subscription,
            plan=self.monthly_plan,
            amount=Decimal('299.00'),
            currency='RUB',
            status='SUCCEEDED',
            description='Подписка Pro Месячный',
            paid_at=timezone.now()
        )

        payment2 = Payment.objects.create(
            user=self.user,
            subscription=self.subscription,
            plan=self.monthly_plan,
            amount=Decimal('299.00'),
            currency='RUB',
            status='PENDING',
            description='Подписка Pro Месячный'
        )

        self.client.force_authenticate(user=self.user)

        url = reverse('billing:payments-history')
        response = self.client.get(url)

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)

        # Проверяем порядок (новые первыми)
        self.assertEqual(response.data['results'][0]['status'], 'pending')
        self.assertEqual(response.data['results'][1]['status'], 'succeeded')

    def test_get_payments_limit(self):
        """Тест параметра limit."""
        # Создаем 15 платежей
        for i in range(15):
            Payment.objects.create(
                user=self.user,
                subscription=self.subscription,
                plan=self.monthly_plan,
                amount=Decimal('299.00'),
                currency='RUB',
                status='SUCCEEDED',
                description=f'Платеж {i}'
            )

        self.client.force_authenticate(user=self.user)

        # Запрашиваем только 5
        url = reverse('billing:payments-history')
        response = self.client.get(url, {'limit': 5})

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 5)

    def test_get_payments_only_own(self):
        """Проверка, что возвращаются только платежи текущего пользователя."""
        # Создаем другого пользователя
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )

        other_subscription = Subscription.objects.create(
            user=other_user,
            plan=self.monthly_plan,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            is_active=True
        )

        # Создаем платежи для обоих пользователей
        Payment.objects.create(
            user=self.user,
            subscription=self.subscription,
            plan=self.monthly_plan,
            amount=Decimal('299.00'),
            currency='RUB',
            status='SUCCEEDED',
            description='My payment'
        )

        Payment.objects.create(
            user=other_user,
            subscription=other_subscription,
            plan=self.monthly_plan,
            amount=Decimal('299.00'),
            currency='RUB',
            status='SUCCEEDED',
            description='Other payment'
        )

        self.client.force_authenticate(user=self.user)

        url = reverse('billing:payments-history')
        response = self.client.get(url)

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['description'], 'My payment')

