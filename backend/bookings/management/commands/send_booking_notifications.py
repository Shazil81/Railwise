from django.core.management.base import BaseCommand
from bookings.notifications import dispatch_booking_emails


class Command(BaseCommand):
    help = 'Process queued booking emails once (console locally, SMTP when configured).'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=100)

    def handle(self, *args, **options):
        limit=options['limit']
        if not 1 <= limit <= 1000:
            from django.core.management.base import CommandError
            raise CommandError('Limit must be between 1 and 1000.')
        self.stdout.write(str(dispatch_booking_emails(limit)))
