"""
Management command to clean up expired email verification tokens.
Run periodically via cron or scheduled task.

Usage:
    python manage.py cleanup_verification_tokens
    python manage.py cleanup_verification_tokens --dry-run
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.users.models import EmailVerificationToken


class Command(BaseCommand):
    help = 'Clean up expired email verification tokens'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Delete tokens expired more than N days ago (default: 7)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        days = options['days']

        # Calculate cutoff date
        cutoff_date = timezone.now() - timezone.timedelta(days=days)

        # Find expired tokens
        expired_tokens = EmailVerificationToken.objects.filter(
            expires_at__lt=cutoff_date
        )

        count = expired_tokens.count()

        if count == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f'No expired tokens found (older than {days} days)'
                )
            )
            return

        # Show details
        self.stdout.write(
            self.style.WARNING(
                f'Found {count} expired tokens (older than {days} days):'
            )
        )

        # Group by status
        used_count = expired_tokens.filter(is_used=True).count()
        unused_count = expired_tokens.filter(is_used=False).count()

        self.stdout.write(f'  - Used tokens: {used_count}')
        self.stdout.write(f'  - Unused tokens: {unused_count}')

        # Show sample of tokens to be deleted
        if count <= 10:
            for token in expired_tokens:
                self.stdout.write(
                    f'  - Token: {token.token[:16]}... '
                    f'User: {token.user.email} '
                    f'Expired: {token.expires_at} '
                    f'Used: {token.is_used}'
                )

        # Delete or dry run
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'\n[DRY RUN] Would delete {count} tokens. '
                    'Run without --dry-run to actually delete.'
                )
            )
        else:
            expired_tokens.delete()
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✓ Successfully deleted {count} expired tokens'
                )
            )

        # Show statistics
        remaining = EmailVerificationToken.objects.count()
        active = EmailVerificationToken.objects.filter(
            expires_at__gt=timezone.now(),
            is_used=False
        ).count()

        self.stdout.write('\nCurrent statistics:')
        self.stdout.write(f'  - Total tokens in database: {remaining}')
        self.stdout.write(f'  - Active (valid) tokens: {active}')
