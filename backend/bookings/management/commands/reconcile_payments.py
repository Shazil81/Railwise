from django.core.management.base import BaseCommand
from bookings.tasks import recover_payments_and_refunds

class Command(BaseCommand):
    help = 'Reconcile stored Razorpay orders and submit/poll the durable refund queue once. Uses configured provider credentials.'
    def handle(self, *args, **options):
        result = recover_payments_and_refunds()
        self.stdout.write(str(result))
