"""Transactionally queued emails, sent only to the booking owner's verified mailbox."""
from .berths import LABELS
from datetime import timedelta
from decimal import Decimal
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMessage
from django.db import transaction
from django.utils import timezone
from .models import AccountEmail, BookingEmail, Refund


def verified_recipient(user):
    state = AccountEmail.objects.filter(user_id=user.pk).first()
    return user.email if user.is_active and state and state.verified_email and state.verified_email.casefold() == user.email.casefold() else ''


@transaction.atomic
def queue_booking_email(booking, kind, refund=None):
    if booking.group_parent_id:
        return
    from .services import group_members
    reference = f'RW-{booking.pk:08d}'
    event = f'booking:{booking.pk}:{kind}' if not refund else f'refund:{refund.pk}:{refund.state}'
    labels = {'PROMOTED':'Waitlist seat held - payment required','CONFIRMED':'Booking confirmed','CANCELLED':'Booking cancelled',
        'REFUND_REQUESTED':'Refund queued','REFUND_PROCESSING':'Refund processing',
        'REFUND_PROCESSED':'Refund completed','REFUND_FAILED':'Refund needs attention',
        'REFUND_UNKNOWN':'Refund awaiting verification','REFUND_REVIEW':'Refund needs review'}
    label = labels[kind]
    pending_states=['QUEUED','RETRY','WAITING_VERIFICATION']
    if kind == 'CANCELLED':
        BookingEmail.objects.filter(booking=booking,kind='CONFIRMED',state__in=pending_states).update(state='SKIPPED')
    if refund:
        BookingEmail.objects.filter(event_key__startswith=f'refund:{refund.pk}:',state__in=pending_states).exclude(kind=kind).update(state='SKIPPED')
    members = list(group_members(booking).select_related('seat'))
    stops = {s.sequence:s.station for s in booking.journey.train.stops.select_related('station')}
    origin, destination = stops.get(booking.from_seq), stops.get(booking.to_seq)
    lines = [f'{label} - {reference}', 'PORTFOLIO DEMO - NOT VALID FOR TRAVEL.',
        f'Train: {booking.journey.train.name} ({booking.journey.train.number})',
        f'Journey date: {booking.boarding_date}',
        f'Route: {origin.name if origin else booking.from_seq} to {destination.name if destination else booking.to_seq}',
        f'Passengers: {len(members)}']
    for index, member in enumerate(members,1):
        berth=LABELS.get(member.seat.allocated_berth,'Seat') if member.seat else 'Not allocated'
        lines.append(f'{index}. {member.passenger_name or "Passenger details not provided"} | Coach/seat: {member.seat or "Not allocated"} | Berth: {berth}')
    lines += [f'Booking total: INR {sum(m.amount for m in members):.2f}']
    if refund:
        lines += [f'Refund reference: {refund.pk}', f'Refund status: {refund.state}',
            f'Refund amount: INR {Decimal(refund.amount_paise)/100:.2f}',
            f'Provider refund ID: {refund.provider_id or "Not assigned yet"}']
        if refund.state == 'PROCESSED':
            lines.append('The provider reports this refund processed. Bank credit timing is determined by your payment provider/bank.')
        else:
            lines.append('This status does not mean money has reached your bank. Check the latest status in Railwise.')
    if kind == 'CANCELLED':
        lines.append('This booking no longer holds any seats. Any refund is tracked separately; cancellation does not confirm bank credit.')
    if kind == 'PROMOTED':
        lines.append(f'A seat is temporarily held until {booking.expires_at}. Complete passenger details, fare review and payment before expiry. This is not a confirmed ticket.')
        if booking.seat and booking.seat.travel_class != booking.travel_class:
            lines.append(f'Opt-in upgrade: {booking.travel_class} to {booking.seat.travel_class}. Your original fare is unchanged.')
    if kind == 'CONFIRMED':
        lines.append(f'Payment reference: {booking.razorpay_payment_id or "See booking"}')
    lines += [f'Update recorded: {timezone.now().isoformat()}',
        'This email is a snapshot. Sign in to Railwise for current booking, ticket and refund details.',
        settings.FRONTEND_URL.rstrip('/')+'/', 'No railway PNR or valid travel ticket is issued by this demo.']
    recipient = verified_recipient(booking.user)
    return BookingEmail.objects.get_or_create(event_key=event, defaults={
        'booking':booking,'kind':kind,'recipient':recipient,'subject':f'Railwise - {label} - {reference}',
        'body':'\n'.join(lines), 'state':'QUEUED' if recipient else 'WAITING_VERIFICATION'})[0]


def queue_refund_email(refund):
    return queue_booking_email(refund.attempt.booking, 'REFUND_'+refund.state, refund)


@transaction.atomic
def deliver_booking_email(notification_id):
    # User first, then outbox row: verification and delivery use the same order.
    candidate = BookingEmail.objects.filter(pk=notification_id).values('booking__user_id').first()
    if not candidate:
        return 'MISSING'
    user = get_user_model().objects.select_for_update().get(pk=candidate['booking__user_id'])
    item = BookingEmail.objects.select_for_update(skip_locked=True).select_related('booking').filter(pk=notification_id).first()
    if not item:
        return 'BUSY'
    if item.state in ['SENT','FAILED','SKIPPED'] or item.next_attempt_at > timezone.now():
        return item.state
    recipient = verified_recipient(user)
    if not recipient:
        item.state='WAITING_VERIFICATION'
        item.save(update_fields=['state'])
        return item.state
    superseded = item.kind == 'CONFIRMED' and item.booking.status != 'CONFIRMED'
    if item.kind == 'PROMOTED':
        superseded = item.booking.status != 'PENDING' or not item.booking.expires_at or item.booking.expires_at <= timezone.now()
    if item.kind.startswith('REFUND_'):
        refund_id = int(item.event_key.split(':')[1])
        superseded = not Refund.objects.filter(pk=refund_id,state=item.kind.removeprefix('REFUND_')).exists()
    if superseded:
        item.state='SKIPPED'
        item.save(update_fields=['state'])
        return item.state
    # Never redirect an existing notification to a different mailbox after an email change.
    if item.recipient and item.recipient.casefold() != recipient.casefold():
        item.state='SKIPPED'
        item.last_error='Account email changed; view the update in Railwise.'
        item.save(update_fields=['state','last_error'])
        return item.state
    item.recipient=recipient
    item.attempts+=1
    try:
        count=EmailMessage(item.subject,item.body,settings.DEFAULT_FROM_EMAIL,[recipient],
            headers={'Message-ID':f'<railwise-booking-email-{item.pk}@notifications.railwise.invalid>'}).send(fail_silently=False)
        if count != 1:
            raise RuntimeError('Email backend did not accept the message')
    except Exception:
        item.state='FAILED' if item.attempts >= settings.BOOKING_EMAIL_MAX_ATTEMPTS else 'RETRY'
        item.next_attempt_at=timezone.now()+timedelta(seconds=min(3600,60*2**min(item.attempts-1,6)))
        item.last_error='Email backend unavailable. Delivery will retry or needs administrator attention.'
    else:
        item.state='SENT'
        item.sent_at=timezone.now()
        item.delivery_channel = 'smtp' if settings.EMAIL_BACKEND.endswith('.smtp.EmailBackend') else 'local'
        item.last_error=''
    item.save(update_fields=['recipient','attempts','state','next_attempt_at','last_error','sent_at','delivery_channel'])
    return item.state


def dispatch_booking_emails(limit=100):
    ids=list(BookingEmail.objects.filter(state__in=['QUEUED','RETRY'],
        next_attempt_at__lte=timezone.now()).order_by('next_attempt_at','id').values_list('id',flat=True)[:limit])
    result={}
    for notification_id in ids:
        state=deliver_booking_email(notification_id)
        result[state]=result.get(state,0)+1
    return result
