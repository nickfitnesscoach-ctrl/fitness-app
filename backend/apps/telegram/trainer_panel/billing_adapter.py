"""
Billing adapter for Trainer Panel.

This module provides functions to retrieve subscription and revenue data
from the billing app without creating tight coupling.

SSOT: apps/billing/models.py
"""

from datetime import timedelta
from decimal import Decimal
from typing import Dict, List, Optional, TypedDict

from django.contrib.auth.models import User
from django.db.models import Sum
from django.utils import timezone

from apps.billing.models import Payment, Subscription


class SubscriptionInfo(TypedDict):
    """Subscription information for a single user."""
    plan_type: str  # 'free' | 'monthly' | 'yearly'
    is_paid: bool
    status: str  # 'active' | 'expired' | 'canceled' | 'unknown'
    paid_until: Optional[str]  # ISO format or None


class RevenueMetrics(TypedDict):
    """Revenue metrics for the trainer panel."""
    total: Decimal
    mtd: Decimal  # Month-to-date
    last_30d: Decimal
    currency: str


class SubscribersCounts(TypedDict):
    """Counts of subscribers by plan type."""
    free: int
    monthly: int
    yearly: int
    paid_total: int


def _normalize_plan_code(code: str) -> str:
    """
    Normalize plan code to frontend format.

    Backend codes: FREE, PRO_MONTHLY, PRO_YEARLY, MONTHLY (legacy), YEARLY (legacy)
    Frontend expects: 'free', 'monthly', 'yearly'
    """
    code_upper = code.upper()

    if code_upper == 'FREE':
        return 'free'
    elif code_upper in ('PRO_MONTHLY', 'MONTHLY'):
        return 'monthly'
    elif code_upper in ('PRO_YEARLY', 'YEARLY'):
        return 'yearly'
    else:
        # Fallback for unknown codes
        return 'free'


def _get_subscription_status(subscription: Subscription) -> str:
    """
    Determine subscription status.

    Returns: 'active' | 'expired' | 'canceled' | 'unknown'
    """
    if not subscription.is_active:
        return 'canceled'

    now = timezone.now()
    if subscription.end_date <= now:
        return 'expired'

    return 'active'


def get_user_subscription_info(user: User) -> SubscriptionInfo:
    """
    Get subscription information for a single user.

    Args:
        user: Django User instance

    Returns:
        SubscriptionInfo dict with plan_type, is_paid, status, paid_until
    """
    try:
        subscription = user.subscription
        plan_code = subscription.plan.code
        plan_type = _normalize_plan_code(plan_code)

        # User is paid if subscription is active and not expired
        now = timezone.now()
        is_active_and_not_expired = subscription.is_active and subscription.end_date > now
        is_paid = is_active_and_not_expired and plan_type != 'free'

        status = _get_subscription_status(subscription)

        # paid_until is None for free users, ISO string for others
        paid_until = None
        if plan_type != 'free':
            paid_until = subscription.end_date.isoformat()

        return SubscriptionInfo(
            plan_type=plan_type,
            is_paid=is_paid,
            status=status,
            paid_until=paid_until
        )
    except Subscription.DoesNotExist:
        # No subscription = free user
        return SubscriptionInfo(
            plan_type='free',
            is_paid=False,
            status='unknown',
            paid_until=None
        )


def get_subscriptions_for_users(user_ids: List[int]) -> Dict[int, SubscriptionInfo]:
    """
    Batch fetch subscription info for multiple users.

    This prevents N+1 queries when fetching data for lists of users.

    Args:
        user_ids: List of User IDs

    Returns:
        Dict mapping user_id -> SubscriptionInfo
    """
    # Fetch all subscriptions with plans in one query
    subscriptions = Subscription.objects.filter(
        user_id__in=user_ids
    ).select_related('plan')

    # Build mapping
    result = {}
    now = timezone.now()

    for sub in subscriptions:
        plan_type = _normalize_plan_code(sub.plan.code)
        is_active_and_not_expired = sub.is_active and sub.end_date > now
        is_paid = is_active_and_not_expired and plan_type != 'free'
        status = _get_subscription_status(sub)

        paid_until = None
        if plan_type != 'free':
            paid_until = sub.end_date.isoformat()

        result[sub.user_id] = SubscriptionInfo(
            plan_type=plan_type,
            is_paid=is_paid,
            status=status,
            paid_until=paid_until
        )

    # Fill in missing users with free/unknown
    for user_id in user_ids:
        if user_id not in result:
            result[user_id] = SubscriptionInfo(
                plan_type='free',
                is_paid=False,
                status='unknown',
                paid_until=None
            )

    return result


def get_subscribers_metrics() -> SubscribersCounts:
    """
    Get counts of subscribers by plan type.

    Returns:
        Dict with counts: free, monthly, yearly, paid_total
    """
    now = timezone.now()

    # Get all active subscriptions
    subscriptions = Subscription.objects.filter(
        is_active=True,
        end_date__gt=now
    ).select_related('plan')

    counts = SubscribersCounts(
        free=0,
        monthly=0,
        yearly=0,
        paid_total=0
    )

    for sub in subscriptions:
        plan_type = _normalize_plan_code(sub.plan.code)

        if plan_type == 'free':
            counts['free'] += 1
        elif plan_type == 'monthly':
            counts['monthly'] += 1
            counts['paid_total'] += 1
        elif plan_type == 'yearly':
            counts['yearly'] += 1
            counts['paid_total'] += 1

    # Also count users with no subscription or expired subscription as free
    total_users = User.objects.count()
    total_with_active_sub = sum([counts['free'], counts['monthly'], counts['yearly']])
    counts['free'] += (total_users - total_with_active_sub)

    return counts


def get_revenue_metrics() -> RevenueMetrics:
    """
    Calculate revenue metrics based on successful payments.

    Only counts payments with status='SUCCEEDED'.

    Returns:
        Dict with total, mtd (month-to-date), last_30d, currency
    """
    now = timezone.now()

    # Calculate date boundaries
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    thirty_days_ago = now - timedelta(days=30)

    # Base queryset: only succeeded payments
    succeeded_payments = Payment.objects.filter(status='SUCCEEDED')

    # Total revenue (all time)
    total_revenue = succeeded_payments.aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')

    # Month-to-date revenue
    mtd_revenue = succeeded_payments.filter(
        paid_at__gte=month_start
    ).aggregate(
        mtd=Sum('amount')
    )['mtd'] or Decimal('0.00')

    # Last 30 days revenue
    last_30d_revenue = succeeded_payments.filter(
        paid_at__gte=thirty_days_ago
    ).aggregate(
        last_30d=Sum('amount')
    )['last_30d'] or Decimal('0.00')

    return RevenueMetrics(
        total=total_revenue,
        mtd=mtd_revenue,
        last_30d=last_30d_revenue,
        currency='RUB'
    )
