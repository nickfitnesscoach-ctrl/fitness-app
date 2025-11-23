"""
Management command to cleanup expired subscriptions.

Usage:
    python manage.py cleanup_expired_subscriptions

Can be added to cron/scheduler:
    0 2 * * * cd /path/to/project && python manage.py cleanup_expired_subscriptions
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from apps.billing.models import Subscription, SubscriptionPlan


class Command(BaseCommand):
    help = 'Deactivate expired subscriptions and downgrade to FREE plan'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually doing it',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        now = timezone.now()

        # Find expired paid subscriptions
        expired_subscriptions = Subscription.objects.filter(
            is_active=True,
            end_date__lt=now
        ).exclude(plan__name='FREE').select_related('user', 'plan')

        count = expired_subscriptions.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS('No expired subscriptions found'))
            return

        self.stdout.write(f'Found {count} expired subscription(s)')

        # Get FREE plan
        try:
            free_plan = SubscriptionPlan.objects.get(name='FREE')
        except SubscriptionPlan.DoesNotExist:
            self.stdout.write(self.style.ERROR('FREE plan not found. Cannot downgrade.'))
            return

        processed = 0
        errors = 0

        for subscription in expired_subscriptions:
            try:
                if dry_run:
                    self.stdout.write(
                        f'[DRY RUN] Would downgrade: {subscription.user.email} '
                        f'from {subscription.plan.display_name} (expired {subscription.end_date})'
                    )
                else:
                    with transaction.atomic():
                        # Downgrade to FREE plan
                        subscription.plan = free_plan
                        subscription.start_date = now
                        subscription.end_date = settings.FREE_SUBSCRIPTION_END_DATE
                        subscription.auto_renew = False
                        subscription.is_active = True
                        subscription.save()

                        self.stdout.write(
                            self.style.SUCCESS(
                                f'Downgraded: {subscription.user.email} '
                                f'to FREE plan'
                            )
                        )

                processed += 1

            except Exception as e:
                errors += 1
                self.stdout.write(
                    self.style.ERROR(
                        f'Error processing {subscription.user.email}: {str(e)}'
                    )
                )

        # Summary
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'\nDRY RUN: Would process {count} subscription(s)'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\nProcessed: {processed} subscription(s), Errors: {errors}'
                )
            )
