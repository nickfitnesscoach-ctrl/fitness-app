"""
Tests for Trainer Panel subscription features.
"""

from datetime import timedelta
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth.models import User

from apps.billing.models import SubscriptionPlan, Subscription, Payment
from apps.telegram.models import TelegramUser
from apps.telegram.trainer_panel.billing_adapter import (
    get_user_subscription_info,
    get_subscriptions_for_users,
    get_subscribers_metrics,
    get_revenue_metrics,
)


class BillingAdapterTestCase(TestCase):
    """Test billing adapter functions."""

    def setUp(self):
        """Set up test data."""
        # Get or create subscription plans
        self.free_plan, _ = SubscriptionPlan.objects.get_or_create(
            code='FREE',
            defaults={
                'display_name': 'Free Plan',
                'price': 0,
                'duration_days': 0
            }
        )
        self.monthly_plan, _ = SubscriptionPlan.objects.get_or_create(
            code='PRO_MONTHLY',
            defaults={
                'display_name': 'Pro Monthly',
                'price': 999,
                'duration_days': 30
            }
        )
        self.yearly_plan, _ = SubscriptionPlan.objects.get_or_create(
            code='PRO_YEARLY',
            defaults={
                'display_name': 'Pro Yearly',
                'price': 9990,
                'duration_days': 365
            }
        )

        # Create users
        self.user_free = User.objects.create_user('user_free', 'free@test.com', 'password')
        self.user_monthly = User.objects.create_user('user_monthly', 'monthly@test.com', 'password')
        self.user_yearly = User.objects.create_user('user_yearly', 'yearly@test.com', 'password')
        self.user_expired = User.objects.create_user('user_expired', 'expired@test.com', 'password')

        # Update subscriptions (they're auto-created by signal)
        now = timezone.now()

        # Free user - leave as is (already has FREE plan from signal)

        # Monthly user (active) - update to monthly plan
        monthly_sub = self.user_monthly.subscription
        monthly_sub.plan = self.monthly_plan
        monthly_sub.end_date = now + timedelta(days=30)
        monthly_sub.save()

        # Yearly user (active) - update to yearly plan
        yearly_sub = self.user_yearly.subscription
        yearly_sub.plan = self.yearly_plan
        yearly_sub.end_date = now + timedelta(days=365)
        yearly_sub.save()

        # Expired user - update to expired monthly plan
        expired_sub = self.user_expired.subscription
        expired_sub.plan = self.monthly_plan
        expired_sub.start_date = now - timedelta(days=60)
        expired_sub.end_date = now - timedelta(days=30)
        expired_sub.save()

    def test_get_user_subscription_info_free(self):
        """Test subscription info for free user."""
        info = get_user_subscription_info(self.user_free)

        self.assertEqual(info['plan_type'], 'free')
        self.assertFalse(info['is_paid'])
        self.assertEqual(info['status'], 'active')
        self.assertIsNone(info['paid_until'])

    def test_get_user_subscription_info_monthly_active(self):
        """Test subscription info for active monthly user."""
        info = get_user_subscription_info(self.user_monthly)

        self.assertEqual(info['plan_type'], 'monthly')
        self.assertTrue(info['is_paid'])
        self.assertEqual(info['status'], 'active')
        self.assertIsNotNone(info['paid_until'])

    def test_get_user_subscription_info_yearly_active(self):
        """Test subscription info for active yearly user."""
        info = get_user_subscription_info(self.user_yearly)

        self.assertEqual(info['plan_type'], 'yearly')
        self.assertTrue(info['is_paid'])
        self.assertEqual(info['status'], 'active')
        self.assertIsNotNone(info['paid_until'])

    def test_get_user_subscription_info_expired(self):
        """Test subscription info for expired user."""
        info = get_user_subscription_info(self.user_expired)

        self.assertEqual(info['plan_type'], 'monthly')
        self.assertFalse(info['is_paid'])
        self.assertEqual(info['status'], 'expired')
        self.assertIsNotNone(info['paid_until'])

    def test_get_user_subscription_info_no_subscription(self):
        """Test subscription info for user with auto-created FREE subscription."""
        user_no_sub = User.objects.create_user('no_sub', 'nosub@test.com', 'password')
        info = get_user_subscription_info(user_no_sub)

        # User gets FREE subscription automatically via signal
        self.assertEqual(info['plan_type'], 'free')
        self.assertFalse(info['is_paid'])
        self.assertEqual(info['status'], 'active')  # FREE subscription is active
        self.assertIsNone(info['paid_until'])

    def test_get_subscriptions_for_users_batch(self):
        """Test batch fetching subscriptions for multiple users."""
        user_ids = [
            self.user_free.id,
            self.user_monthly.id,
            self.user_yearly.id,
            self.user_expired.id
        ]

        subscriptions_map = get_subscriptions_for_users(user_ids)

        # Check all users are in the map
        self.assertEqual(len(subscriptions_map), 4)

        # Check free user
        self.assertEqual(subscriptions_map[self.user_free.id]['plan_type'], 'free')
        self.assertFalse(subscriptions_map[self.user_free.id]['is_paid'])

        # Check monthly user
        self.assertEqual(subscriptions_map[self.user_monthly.id]['plan_type'], 'monthly')
        self.assertTrue(subscriptions_map[self.user_monthly.id]['is_paid'])

        # Check yearly user
        self.assertEqual(subscriptions_map[self.user_yearly.id]['plan_type'], 'yearly')
        self.assertTrue(subscriptions_map[self.user_yearly.id]['is_paid'])

        # Check expired user
        self.assertEqual(subscriptions_map[self.user_expired.id]['plan_type'], 'monthly')
        self.assertFalse(subscriptions_map[self.user_expired.id]['is_paid'])

    def test_get_subscribers_metrics(self):
        """Test subscribers count metrics."""
        metrics = get_subscribers_metrics()

        # We have 1 monthly active, 1 yearly active
        # Free count includes expired and users without subscription
        self.assertEqual(metrics['monthly'], 1)
        self.assertEqual(metrics['yearly'], 1)
        self.assertEqual(metrics['paid_total'], 2)

    def test_get_revenue_metrics_no_payments(self):
        """Test revenue metrics with no payments."""
        revenue = get_revenue_metrics()

        self.assertEqual(revenue['total'], Decimal('0.00'))
        self.assertEqual(revenue['mtd'], Decimal('0.00'))
        self.assertEqual(revenue['last_30d'], Decimal('0.00'))
        self.assertEqual(revenue['currency'], 'RUB')

    def test_get_revenue_metrics_with_payments(self):
        """Test revenue metrics with successful payments."""
        now = timezone.now()

        # Create payments
        # Payment 1: successful, this month
        Payment.objects.create(
            user=self.user_monthly,
            subscription=self.user_monthly.subscription,
            plan=self.monthly_plan,
            amount=Decimal('999.00'),
            status='SUCCEEDED',
            paid_at=now
        )

        # Payment 2: successful, last month
        Payment.objects.create(
            user=self.user_yearly,
            subscription=self.user_yearly.subscription,
            plan=self.yearly_plan,
            amount=Decimal('9990.00'),
            status='SUCCEEDED',
            paid_at=now - timedelta(days=20)
        )

        # Payment 3: failed (should not count)
        Payment.objects.create(
            user=self.user_expired,
            subscription=self.user_expired.subscription,
            plan=self.monthly_plan,
            amount=Decimal('999.00'),
            status='FAILED',
            paid_at=now
        )

        # Payment 4: successful, 60 days ago (not in last_30d, but in total)
        Payment.objects.create(
            user=self.user_monthly,
            subscription=self.user_monthly.subscription,
            plan=self.monthly_plan,
            amount=Decimal('999.00'),
            status='SUCCEEDED',
            paid_at=now - timedelta(days=60)
        )

        revenue = get_revenue_metrics()

        # Total: 999 + 9990 + 999 = 11988
        self.assertEqual(revenue['total'], Decimal('11988.00'))

        # MTD depends on whether payments are in current month
        # At minimum, payment 1 (999) should be counted
        self.assertGreaterEqual(revenue['mtd'], Decimal('999.00'))

        # Last 30d: 999 (payment 1) + 9990 (payment 2) = 10989
        self.assertEqual(revenue['last_30d'], Decimal('10989.00'))

        self.assertEqual(revenue['currency'], 'RUB')

    def test_legacy_plan_codes(self):
        """Test that legacy plan codes (MONTHLY, YEARLY) are normalized correctly."""
        # Create legacy plans
        legacy_monthly, _ = SubscriptionPlan.objects.get_or_create(
            code='MONTHLY',
            defaults={
                'display_name': 'Legacy Monthly',
                'price': 999,
                'duration_days': 30
            }
        )

        user_legacy = User.objects.create_user('legacy', 'legacy@test.com', 'password')
        now = timezone.now()

        # Update the auto-created subscription
        legacy_sub = user_legacy.subscription
        legacy_sub.plan = legacy_monthly
        legacy_sub.end_date = now + timedelta(days=30)
        legacy_sub.save()

        info = get_user_subscription_info(user_legacy)
        self.assertEqual(info['plan_type'], 'monthly')
