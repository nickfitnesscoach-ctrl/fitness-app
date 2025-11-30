"""
Django management command for cleaning up old meal data based on subscription plan.

This command removes meals and associated food items that exceed the history retention
period defined in each user's subscription plan:
- FREE plan: 7 days history
- PRO plans: 180 days history

Usage:
    python manage.py cleanup_old_meals [--dry-run]

Options:
    --dry-run: Show what would be deleted without actually deleting
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Count, Q
from datetime import timedelta
import logging

from apps.nutrition.models import Meal, FoodItem
from apps.billing.models import Subscription

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Cleanup old meals and food items based on user subscription plan history limits'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        today = timezone.now().date()

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No data will be deleted'))

        total_meals_deleted = 0
        total_items_deleted = 0
        total_photos_deleted = 0

        # Get all active subscriptions
        subscriptions = Subscription.objects.select_related('user', 'plan').filter(is_active=True)

        self.stdout.write(f'Processing {subscriptions.count()} active subscriptions...\n')

        for subscription in subscriptions:
            user = subscription.user
            plan = subscription.plan
            history_days = plan.history_days

            # Skip if unlimited history (-1)
            if history_days == -1:
                continue

            # Calculate cutoff date
            cutoff_date = today - timedelta(days=history_days)

            # Find old meals for this user
            old_meals = Meal.objects.filter(
                user=user,
                date__lt=cutoff_date
            ).prefetch_related('items')

            meals_count = old_meals.count()

            if meals_count == 0:
                continue

            # Count items and photos before deletion
            items_count = sum(meal.items.count() for meal in old_meals)
            photos_count = sum(
                1 for meal in old_meals
                if meal.photo
            ) + sum(
                1 for meal in old_meals
                for item in meal.items.all()
                if item.photo
            )

            self.stdout.write(
                f'User: {user.username} (Plan: {plan.display_name}, History: {history_days} days)\n'
                f'  Cutoff date: {cutoff_date}\n'
                f'  Meals to delete: {meals_count}\n'
                f'  Food items to delete: {items_count}\n'
                f'  Photos to delete: {photos_count}\n'
            )

            if not dry_run:
                # Delete photos from storage first
                for meal in old_meals:
                    # Delete meal photo
                    if meal.photo:
                        try:
                            meal.photo.delete(save=False)
                        except Exception as e:
                            logger.error(f'Error deleting meal photo {meal.id}: {e}')

                    # Delete food item photos
                    for item in meal.items.all():
                        if item.photo:
                            try:
                                item.photo.delete(save=False)
                            except Exception as e:
                                logger.error(f'Error deleting food item photo {item.id}: {e}')

                # Delete meals (cascade will delete food items)
                deleted_count = old_meals.delete()[0]

                total_meals_deleted += meals_count
                total_items_deleted += items_count
                total_photos_deleted += photos_count

                self.stdout.write(
                    self.style.SUCCESS(f'  ✓ Deleted {deleted_count} records\n')
                )
            else:
                total_meals_deleted += meals_count
                total_items_deleted += items_count
                total_photos_deleted += photos_count

        # Summary
        self.stdout.write('\n' + '='*60)
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN SUMMARY (no data was deleted):'))
        else:
            self.stdout.write(self.style.SUCCESS('CLEANUP SUMMARY:'))

        self.stdout.write(f'  Total meals: {total_meals_deleted}')
        self.stdout.write(f'  Total food items: {total_items_deleted}')
        self.stdout.write(f'  Total photos: {total_photos_deleted}')
        self.stdout.write('='*60 + '\n')

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    'Run without --dry-run to actually delete the data'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('Cleanup completed successfully!')
            )
