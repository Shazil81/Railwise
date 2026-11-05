from celery import shared_task
from django.utils import timezone
from .models import Booking
from .services import expire_journey


@shared_task
def send_booking_notifications():
    from .notifications import dispatch_booking_emails
    # The notification-only Windows worker also maintains local holds; no gateway calls.
    sweep_expired_holds()
    return dispatch_booking_emails()

@shared_task
def expire_unpaid_booking(booking_id):
    b = Booking.objects.filter(pk=booking_id).first()
    return expire_journey(b.journey_id) if b else 0

@shared_task
def sweep_expired_holds():
    from django.db.models import Q
    ids = list(Booking.objects.filter(Q(status=Booking.Status.PENDING, expires_at__lte=timezone.now()) |
        Q(status=Booking.Status.WL)).values_list('journey_id', flat=True).distinct())
    return sum(expire_journey(jid) for jid in ids)


@shared_task
def recover_payments_and_refunds():
    """Durable database queues: a lost task is picked up by the next sweep."""
    from datetime import timedelta
    from django.db.models import Q, F
    from rest_framework.exceptions import APIException
    from .models import Refund
    from .lifecycle import recover_booking, process_refund
    now = timezone.now()
    roots = Booking.objects.filter(group_parent__isnull=True, razorpay_order_id__isnull=False,
        created_at__gte=now-timedelta(days=7)).filter(
            Q(status__in=['PENDING', 'EXPIRED', 'CANCELLED']) |
            Q(payment_attempts__state__in=['CREATED', 'AUTHORIZED'])).distinct().order_by(
                F('payment_checked_at').asc(nulls_first=True), 'id')
    booking_ids = list(roots.values_list('id', flat=True)[:100])
    for booking_id in booking_ids:
        try:
            recover_booking(booking_id)
        except APIException:
            continue
    ids = list(Refund.objects.exclude(state__in=['PROCESSED', 'REVIEW']).filter(
        next_check_at__lte=now).order_by('next_check_at').values_list('id', flat=True)[:100])
    for refund_id in ids:
        try:
            process_refund(refund_id)
        except APIException:
            continue
    return {'bookings_checked': len(booking_ids), 'refunds_checked': len(ids)}
