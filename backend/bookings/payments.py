"""Razorpay trust boundary. No booking can be confirmed without gateway evidence."""
from decimal import Decimal
import hashlib
import hmac
import razorpay
import requests
from django.conf import settings
from django.db import transaction, IntegrityError
from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError
from .models import Booking, Journey

class PaymentUnavailable(APIException):
    status_code = 503
    default_detail = 'Payment service is unavailable. Please retry shortly.'

class TimeoutSession(requests.Session):
    def request(self, *args, **kwargs):
        kwargs.setdefault('timeout', 10)
        return super().request(*args, **kwargs)

def payment_client():
    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        raise PaymentUnavailable('Payments are not configured. Contact the project administrator.')
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET), session=TimeoutSession())

def paise(booking):
    from .services import group_members
    value = sum(m.amount for m in group_members(booking)) * Decimal('100')
    if value <= 0 or value != value.to_integral_value():
        raise ValidationError('Invalid booking fare.')
    return int(value)

def gateway_call(method, *args, **kwargs):
    try:
        return method(*args, **kwargs)
    except (razorpay.errors.BadRequestError, razorpay.errors.GatewayError,
            razorpay.errors.ServerError, requests.RequestException):
        raise PaymentUnavailable() from None

def require_payable(booking):
    from .rules import require_booking_open
    require_booking_open(booking.journey, booking.from_seq, booking.travel_class, booking.quota)
    if booking.status != Booking.Status.PENDING or not booking.expires_at or booking.expires_at <= timezone.now():
        raise ValidationError('This hold is no longer payable. Refresh your bookings.')

def require_checkout_ready(booking, reviewed=True):
    from .services import group_members
    from .serializers import PassengerDetailsSerializer
    members = list(group_members(booking))
    if any(not member.seat_id for member in members):
        raise ValidationError('Every passenger must have an allocated seat before payment.')
    for member in members:
        require_payable(member)
    serializer = PassengerDetailsSerializer(data={
        'passengers': [{'booking_id': m.id, 'name': m.passenger_name,
            'age': m.passenger_age, 'gender': m.passenger_gender} for m in members],
        'contact_email': booking.contact_email, 'contact_phone': booking.contact_phone,
    })
    serializer.is_valid(raise_exception=True)
    if reviewed and not booking.reviewed_at:
        raise ValidationError('Review the fare and passenger details before payment.')

@transaction.atomic
def create_order(booking_id, user):
    jid = Booking.objects.get(pk=booking_id, user=user).journey_id
    Journey.objects.select_for_update().get(pk=jid)
    booking = Booking.objects.select_for_update(of=('self',)).select_related('journey__train', 'seat').get(pk=booking_id, user=user)
    require_checkout_ready(booking)
    if booking.payment_attempts.filter(state__in=['AUTHORIZED', 'CAPTURED', 'REFUNDED', 'REVIEW']).exists():
        raise ValidationError('A payment is pending verification. Check payment status before retrying.')
    client = payment_client()
    amount = paise(booking)
    if booking.razorpay_order_id:
        order = gateway_call(client.order.fetch, booking.razorpay_order_id)
    else:
        order = gateway_call(client.order.create, data={
            'amount': amount, 'currency': 'INR', 'receipt': f'booking_{booking.id}',
            'notes': {'booking_id': str(booking.id)},
        })
    if (not isinstance(order, dict) or not isinstance(order.get('id'), str) or not order['id'].startswith('order_')
            or order.get('amount') != amount or order.get('currency') != 'INR'
            or (booking.razorpay_order_id and order['id'] != booking.razorpay_order_id)):
        raise PaymentUnavailable('Payment order details do not match the booking.')
    # A slow gateway response must not reopen an expired/cancelled hold.
    require_payable(booking)
    if not booking.razorpay_order_id:
        booking.razorpay_order_id = order['id']
        booking.save(update_fields=['razorpay_order_id'])
    return booking, order

def confirm_payment(booking_id, user, *, payment_id, order_id, signature):
    from .services import expire_journey
    jid = Booking.objects.get(pk=booking_id, user=user).journey_id
    expire_journey(jid)
    try:
        with transaction.atomic():
            Journey.objects.select_for_update().get(pk=jid)
            b = Booking.objects.select_for_update().get(pk=booking_id, user=user)
            if not b.razorpay_order_id or order_id != b.razorpay_order_id:
                raise ValidationError('Payment order does not match this booking.')
            payment_client_instance = payment_client()
            expected = hmac.new(settings.RAZORPAY_KEY_SECRET.encode(),
                f'{b.razorpay_order_id}|{payment_id}'.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, signature):
                raise ValidationError('Payment signature is invalid.')
            if b.status == Booking.Status.CONFIRMED:
                if b.razorpay_payment_id == payment_id:
                    return b  # same verified callback is safe to retry
                raise ValidationError('Booking was confirmed by a different payment.')
            require_checkout_ready(b)
            if Booking.objects.filter(razorpay_payment_id=payment_id).exclude(pk=b.id).exists():
                raise ValidationError('Payment has already been used.')
            payment = gateway_call(payment_client_instance.payment.fetch, payment_id)
            if (not isinstance(payment, dict) or payment.get('id') != payment_id or payment.get('order_id') != b.razorpay_order_id
                    or payment.get('amount') != paise(b) or payment.get('currency') != 'INR'
                    or payment.get('status') != 'captured' or payment.get('captured') is not True
                    or payment.get('amount_refunded', 0) != 0):
                raise ValidationError('Payment is not a captured, matching, unrefunded payment.')
            require_payable(b)
            from .lifecycle import ingest_payment
            b = ingest_payment(payment)
            b.razorpay_signature = signature
            b.save(update_fields=['razorpay_signature'])
            return b
    except IntegrityError:
        raise ValidationError('Payment or order has already been assigned.') from None
