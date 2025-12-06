"""
Тесты для системы дневных лимитов фото.
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
from .services import get_effective_plan_for_user
from .usage import DailyUsage


class DailyUsageTestCase(TestCase):
    """Тесты для модели DailyUsage и учета использования."""

    def setUp(self):
        """Настройка тестовых данных."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_get_today_creates_new_record(self):
        """Тест создания новой записи на сегодня."""
        usage = DailyUsage.objects.get_today(self.user)

        self.assertEqual(usage.user, self.user)
        self.assertEqual(usage.date, timezone.now().date())
        self.assertEqual(usage.photo_ai_requests, 0)

    def test_get_today_returns_existing_record(self):
        """Тест получения существующей записи на сегодня."""
        # Создаем запись
        existing_usage = DailyUsage.objects.create(
            user=self.user,
            date=timezone.now().date(),
            photo_ai_requests=5
        )

        # Получаем через менеджер
        usage = DailyUsage.objects.get_today(self.user)

        self.assertEqual(usage.id, existing_usage.id)
        self.assertEqual(usage.photo_ai_requests, 5)

    def test_increment_photo_requests(self):
        """Тест инкремента счетчика фото."""
        # Первый инкремент - создает запись
        usage1 = DailyUsage.objects.increment_photo_requests(self.user)
        self.assertEqual(usage1.photo_ai_requests, 1)

        # Второй инкремент - обновляет существующую
        usage2 = DailyUsage.objects.increment_photo_requests(self.user)
        self.assertEqual(usage2.photo_ai_requests, 2)
        self.assertEqual(usage2.id, usage1.id)

    def test_is_today_property(self):
        """Тест свойства is_today."""
        today_usage = DailyUsage.objects.create(
            user=self.user,
            date=timezone.now().date(),
            photo_ai_requests=1
        )
        self.assertTrue(today_usage.is_today)

        yesterday_usage = DailyUsage.objects.create(
            user=self.user,
            date=timezone.now().date() - timedelta(days=1),
            photo_ai_requests=1
        )
        self.assertFalse(yesterday_usage.is_today)


class GetEffectivePlanTestCase(TestCase):
    """Тесты для сервиса get_effective_plan_for_user."""

    def setUp(self):
        """Настройка тестовых данных."""
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
            daily_photo_limit=3,
            is_active=True
        )

        self.monthly_plan = SubscriptionPlan.objects.create(
            name='MONTHLY',
            display_name='Pro Месячный',
            price=Decimal('299.00'),
            duration_days=30,
            daily_photo_limit=None,  # Безлимит
            is_active=True
        )

    def test_returns_free_when_no_subscription(self):
        """Тест возврата FREE плана при отсутствии подписки."""
        plan = get_effective_plan_for_user(self.user)
        self.assertEqual(plan.code, 'FREE')

    def test_returns_active_subscription_plan(self):
        """Тест возврата плана активной подписки."""
        Subscription.objects.create(
            user=self.user,
            plan=self.monthly_plan,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            is_active=True
        )

        plan = get_effective_plan_for_user(self.user)
        self.assertEqual(plan.code, 'MONTHLY')

    def test_returns_free_when_subscription_expired(self):
        """Тест возврата FREE плана при истекшей подписке."""
        Subscription.objects.create(
            user=self.user,
            plan=self.monthly_plan,
            start_date=timezone.now() - timedelta(days=60),
            end_date=timezone.now() - timedelta(days=30),  # Истекла
            is_active=True
        )

        plan = get_effective_plan_for_user(self.user)
        self.assertEqual(plan.code, 'FREE')


class PhotoLimitEnforcementTestCase(TestCase):
    """Тесты для проверки лимитов фото в AI endpoint."""

    def setUp(self):
        """Настройка тестовых данных."""
        self.client = APIClient()

        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        # FREE план с лимитом 3 фото
        self.free_plan = SubscriptionPlan.objects.create(
            name='FREE',
            display_name='Бесплатный',
            price=Decimal('0.00'),
            duration_days=0,
            daily_photo_limit=3,
            is_active=True
        )

        # PRO план без лимита
        self.pro_plan = SubscriptionPlan.objects.create(
            name='MONTHLY',
            display_name='Pro Месячный',
            price=Decimal('299.00'),
            duration_days=30,
            daily_photo_limit=None,  # Безлимит
            is_active=True
        )

        # Создаем FREE подписку
        self.subscription = Subscription.objects.create(
            user=self.user,
            plan=self.free_plan,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=365),
            is_active=True
        )

    @patch('apps.ai.services.AIRecognitionService.recognize_food')
    def test_free_user_can_use_within_limit(self, mock_recognize):
        """FREE пользователь может делать запросы в пределах лимита."""
        mock_recognize.return_value = {
            'recognized_items': [
                {
                    'name': 'Яблоко',
                    'portion_grams': 100,
                    'calories': 52,
                    'protein': 0.3,
                    'fat': 0.2,
                    'carbs': 14
                }
            ]
        }

        self.client.force_authenticate(user=self.user)
        url = reverse('ai:recognize')

        # Делаем 3 запроса (в пределах лимита)
        for i in range(3):
            response = self.client.post(url, {
                'image': 'data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQ'
            }, format='json')

            self.assertEqual(response.status_code, http_status.HTTP_200_OK)

        # Проверяем счетчик
        usage = DailyUsage.objects.get_today(self.user)
        self.assertEqual(usage.photo_ai_requests, 3)

    @patch('apps.ai.services.AIRecognitionService.recognize_food')
    def test_free_user_blocked_at_limit(self, mock_recognize):
        """FREE пользователь блокируется при превышении лимита."""
        # Устанавливаем счетчик на лимит
        DailyUsage.objects.create(
            user=self.user,
            date=timezone.now().date(),
            photo_ai_requests=3
        )

        self.client.force_authenticate(user=self.user)
        url = reverse('ai:recognize')

        # 4-й запрос должен быть заблокирован
        response = self.client.post(url, {
            'image': 'data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQ'
        }, format='json')

        self.assertEqual(response.status_code, http_status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(response.data['error'], 'DAILY_LIMIT_REACHED')
        self.assertIn('Превышен дневной лимит', response.data['detail'])

        # Проверяем, что счетчик не увеличился
        usage = DailyUsage.objects.get_today(self.user)
        self.assertEqual(usage.photo_ai_requests, 3)

    @patch('apps.ai.services.AIRecognitionService.recognize_food')
    def test_pro_user_unlimited_requests(self, mock_recognize):
        """PRO пользователь может делать неограниченные запросы."""
        mock_recognize.return_value = {
            'recognized_items': [
                {
                    'name': 'Яблоко',
                    'portion_grams': 100,
                    'calories': 52,
                    'protein': 0.3,
                    'fat': 0.2,
                    'carbs': 14
                }
            ]
        }

        # Обновляем подписку на PRO
        self.subscription.plan = self.pro_plan
        self.subscription.save()

        self.client.force_authenticate(user=self.user)
        url = reverse('ai:recognize')

        # Делаем 10 запросов (больше FREE лимита)
        for i in range(10):
            response = self.client.post(url, {
                'image': 'data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQ'
            }, format='json')

            self.assertEqual(response.status_code, http_status.HTTP_200_OK)

        # Проверяем счетчик
        usage = DailyUsage.objects.get_today(self.user)
        self.assertEqual(usage.photo_ai_requests, 10)


class GetSubscriptionStatusWithLimitsTestCase(TestCase):
    """Тесты для /billing/me/ с информацией о лимитах."""

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
            daily_photo_limit=3,
            is_active=True
        )

        self.subscription = Subscription.objects.create(
            user=self.user,
            plan=self.free_plan,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=365),
            is_active=True
        )

    def test_subscription_status_includes_limit_info(self):
        """Тест наличия информации о лимитах в ответе."""
        self.client.force_authenticate(user=self.user)

        url = reverse('billing:subscription-status')
        response = self.client.get(url)

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['plan_code'], 'FREE')
        self.assertEqual(response.data['daily_photo_limit'], 3)
        self.assertEqual(response.data['used_today'], 0)
        self.assertEqual(response.data['remaining_today'], 3)

    def test_subscription_status_with_usage(self):
        """Тест корректного отображения использования."""
        # Создаем использование
        DailyUsage.objects.create(
            user=self.user,
            date=timezone.now().date(),
            photo_ai_requests=2
        )

        self.client.force_authenticate(user=self.user)

        url = reverse('billing:subscription-status')
        response = self.client.get(url)

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['used_today'], 2)
        self.assertEqual(response.data['remaining_today'], 1)

    def test_subscription_status_unlimited_plan(self):
        """Тест отображения безлимитного плана."""
        # Создаем PRO план
        pro_plan = SubscriptionPlan.objects.create(
            name='MONTHLY',
            display_name='Pro Месячный',
            price=Decimal('299.00'),
            duration_days=30,
            daily_photo_limit=None,  # Безлимит
            is_active=True
        )

        # Обновляем подписку
        self.subscription.plan = pro_plan
        self.subscription.save()

        self.client.force_authenticate(user=self.user)

        url = reverse('billing:subscription-status')
        response = self.client.get(url)

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIsNone(response.data['daily_photo_limit'])
        self.assertIsNone(response.data['remaining_today'])


class CreateUniversalPaymentTestCase(TestCase):
    """Тесты для универсального endpoint /billing/create-payment/."""

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

        self.yearly_plan = SubscriptionPlan.objects.create(
            name='YEARLY',
            display_name='Pro Годовой',
            price=Decimal('2490.00'),
            duration_days=365,
            is_active=True
        )

        # Создаем бесплатную подписку
        self.subscription = Subscription.objects.create(
            user=self.user,
            plan=self.free_plan,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=365),
            is_active=True
        )

    @patch('apps.billing.yookassa_client.YooKassaClient.create_payment')
    def test_create_monthly_payment(self, mock_create_payment):
        """Тест создания платежа для месячного плана."""
        mock_create_payment.return_value = {
            'id': 'test-monthly-payment',
            'status': 'pending',
            'amount': {'value': '299.00', 'currency': 'RUB'},
            'confirmation': {
                'type': 'redirect',
                'confirmation_url': 'https://yookassa.ru/payments/test'
            },
            'metadata': {}
        }

        self.client.force_authenticate(user=self.user)

        url = reverse('billing:create-payment')
        response = self.client.post(url, {'plan_code': 'MONTHLY'}, format='json')

        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertIn('payment_id', response.data)
        self.assertIn('confirmation_url', response.data)

    @patch('apps.billing.yookassa_client.YooKassaClient.create_payment')
    def test_create_yearly_payment(self, mock_create_payment):
        """Тест создания платежа для годового плана."""
        mock_create_payment.return_value = {
            'id': 'test-yearly-payment',
            'status': 'pending',
            'amount': {'value': '2490.00', 'currency': 'RUB'},
            'confirmation': {
                'type': 'redirect',
                'confirmation_url': 'https://yookassa.ru/payments/test'
            },
            'metadata': {}
        }

        self.client.force_authenticate(user=self.user)

        url = reverse('billing:create-payment')
        response = self.client.post(url, {'plan_code': 'YEARLY'}, format='json')

        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)

    def test_create_payment_rejects_free_plan(self):
        """Тест отклонения создания платежа для FREE плана."""
        self.client.force_authenticate(user=self.user)

        url = reverse('billing:create-payment')
        response = self.client.post(url, {'plan_code': 'FREE'}, format='json')

        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_create_payment_missing_plan_code(self):
        """Тест ошибки при отсутствии plan_code."""
        self.client.force_authenticate(user=self.user)

        url = reverse('billing:create-payment')
        response = self.client.post(url, {}, format='json')

        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error']['code'], 'MISSING_PLAN_CODE')


class WebhookFreePlanPreventionTestCase(TestCase):
    """Тесты для проверки запрета активации FREE через webhook."""

    def setUp(self):
        """Настройка тестовых данных."""
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

        self.subscription = Subscription.objects.create(
            user=self.user,
            plan=self.free_plan,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=365),
            is_active=True
        )

    @patch('apps.billing.webhooks.YooKassaService.parse_webhook_notification')
    def test_webhook_prevents_free_plan_activation(self, mock_parse):
        """Webhook должен предотвращать активацию FREE плана через платеж."""
        # Создаем платеж для FREE плана (что не должно происходить)
        payment = Payment.objects.create(
            user=self.user,
            subscription=self.subscription,
            plan=self.free_plan,
            amount=Decimal('0.00'),
            currency='RUB',
            status='PENDING',
            yookassa_payment_id='test-free-payment',
            provider='YOOKASSA'
        )

        # Мокаем webhook notification
        mock_notification = MagicMock()
        mock_notification.event = 'payment.succeeded'
        mock_notification.object.id = 'test-free-payment'
        mock_notification.object.payment_method = None
        mock_parse.return_value = mock_notification

        from apps.billing.webhooks import handle_payment_succeeded
        handle_payment_succeeded(mock_notification.object)

        # Проверяем, что платеж помечен как успешный, но подписка не изменилась
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'SUCCEEDED')
        self.assertIn('Cannot activate FREE plan', payment.error_message)

        # Подписка должна остаться FREE
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.plan, self.free_plan)
