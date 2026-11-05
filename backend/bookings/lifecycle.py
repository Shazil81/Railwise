"""Verified provider observations, durable refund outbox and callback recovery.

Lock order: journey, booking, payment attempt, refund. Webhook receipts only
wrap processing; no other path acquires a receipt lock.
"""
from datetime import datetime, timedelta, timezone as datetime_timezone
import hashlib
import hmac
import json
import re
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError, PermissionDenied
from .models import Booking, Journey, PaymentAttempt, Refund, WebhookEvent
from . import payments
from .notifications import queue_booking_email, queue_refund_email

RANK = {'CREATED': 0, 'AUTHORIZED': 1, 'FAILED': 2, 'CAPTURED': 3, 'REFUNDED': 4, 'REVIEW': 5}


def queue_refund(attempt, reason):
    refund, _ = Refund.objects.get_or_create(attempt=attempt,
        defaults={'amount_paise': attempt.amount_paise, 'reason': reason})
    queue_refund_email(refund)
    return refund


def queue_booking_refunds(booking, reason='Booking cancelled'):
    # Also covers confirmed rows created before payment-attempt tracking existed.
    if booking.razorpay_payment_id:
        PaymentAttempt.objects.get_or_create(payment_id=booking.razorpay_payment_id,
            defaults={'booking': booking, 'order_id': booking.razorpay_order_id or '',
                'amount_paise': payments.paise(booking), 'state': 'CAPTURED'})
    for attempt in booking.payment_attempts.filter(state='CAPTURED'):
        queue_refund(attempt, reason)


@transaction.atomic
def ingest_payment(entity):
    """Only call with a verified webhook or authenticated Razorpay API response."""
    if not isinstance(entity, dict) or not re.fullmatch(r'pay_[A-Za-z0-9_]+', str(entity.get('id', ''))):
        raise ValidationError('Invalid payment entity.')
    booking = Booking.objects.filter(razorpay_order_id=entity.get('order_id'), group_parent__isnull=True).first()
    if not booking:
        return None
    from .services import expire_journey, group_members
    Journey.objects.select_for_update().get(pk=booking.journey_id)
    expire_journey(booking.journey_id)
    booking.refresh_from_db()
    amount = entity.get('amount')
    if type(amount) is not int or amount <= 0 or entity.get('currency') != 'INR':
        raise ValidationError('Invalid payment amount or currency.')
    attempt, _ = PaymentAttempt.objects.get_or_create(payment_id=entity['id'],
        defaults={'booking': booking, 'order_id': booking.razorpay_order_id,
            'amount_paise': amount, 'currency': 'INR'})
    attempt = PaymentAttempt.objects.select_for_update().get(pk=attempt.pk)
    if attempt.booking_id != booking.id or attempt.order_id != booking.razorpay_order_id or attempt.amount_paise != amount:
        raise ValidationError('Payment does not match its recorded order.')
    state = str(entity.get('status', '')).upper()
    if state not in RANK or state == 'REVIEW':
        raise ValidationError('Unsupported payment state.')
    if state == 'CAPTURED' and entity.get('captured') is not True:
        raise ValidationError('Payment has not been captured.')
    if amount != payments.paise(booking):
        attempt.state = 'REVIEW'
        attempt.failure_message = 'Payment amount mismatch; administrator review required.'
        attempt.save(update_fields=['state', 'failure_message', 'updated_at'])
        return booking
    # Delayed failed/authorized messages must never undo a capture/refund.
    if RANK[state] < RANK[attempt.state]:
        return booking
    method = entity.get('method')
    if method in {'upi', 'card', 'netbanking', 'wallet', 'emi', 'bank_transfer', 'paylater'}:
        attempt.method = method
    provider_time = entity.get('created_at')
    if type(provider_time) is int and provider_time > 0 and not attempt.provider_created_at:
        try:
            attempt.provider_created_at = datetime.fromtimestamp(provider_time, datetime_timezone.utc)
        except (ValueError, OverflowError, OSError):
            pass
    if state == 'CAPTURED' and not attempt.captured_at:
        attempt.captured_at = timezone.now()
    attempt.state = state
    attempt.failure_message = 'Payment failed. You can retry while your seat hold is active.' if state == 'FAILED' else ''
    attempt.save(update_fields=['state', 'failure_message', 'updated_at', 'method', 'provider_created_at', 'captured_at'])
    if state == 'CAPTURED':
        if entity.get('amount_refunded', 0):
            attempt.state = 'REVIEW'
            attempt.failure_message = 'A refund already exists; reconcile before further action.'
            attempt.save(update_fields=['state', 'failure_message', 'updated_at'])
        elif booking.status == 'CONFIRMED' and booking.razorpay_payment_id == attempt.payment_id:
            pass
        elif booking.status == 'PENDING' and not booking.razorpay_payment_id:
            try:
                payments.require_checkout_ready(booking)
            except ValidationError:
                queue_refund(attempt, 'Payment received after seat hold or checkout validity ended')
            else:
                group_members(booking).update(status='CONFIRMED', expires_at=None)
                booking.status, booking.expires_at = 'CONFIRMED', None
                booking.razorpay_payment_id = attempt.payment_id
                booking.save(update_fields=['status', 'expires_at', 'razorpay_payment_id'])
                queue_booking_email(booking, 'CONFIRMED')
        else:
            queue_refund(attempt, 'Late, cancelled or duplicate booking payment')
    elif state == 'REFUNDED':
        # A payment.refunded observation is aggregate; fetch individual refunds
        # during recovery instead of fabricating a provider refund reference.
        if booking.status == 'CONFIRMED':
            group_members(booking).update(status='CANCELLED', expires_at=None)
            from .services import _promote_locked
            _promote_locked(booking.journey)
            booking.refresh_from_db()
            queue_booking_email(booking, 'CANCELLED')
    return booking


@transaction.atomic
def apply_refund(entity):
    if not isinstance(entity, dict) or not re.fullmatch(r'rfnd_[A-Za-z0-9_]+', str(entity.get('id', ''))):
        raise ValidationError('Invalid refund entity.')
    attempt = PaymentAttempt.objects.filter(payment_id=entity.get('payment_id')).select_related('booking').first()
    if not attempt:
        return None
    Journey.objects.select_for_update().get(pk=attempt.booking.journey_id)
    attempt = PaymentAttempt.objects.select_for_update().get(pk=attempt.pk)
    amount = entity.get('amount')
    state = str(entity.get('status', '')).upper()
    if state not in ['PENDING', 'PROCESSED', 'FAILED'] or type(amount) is not int or amount <= 0 or entity.get('currency') != 'INR':
        raise ValidationError('Invalid refund details.')
    refund, _ = Refund.objects.get_or_create(attempt=attempt,
        defaults={'amount_paise': attempt.amount_paise, 'reason': 'Provider refund observed'})
    refund = Refund.objects.select_for_update().get(pk=refund.pk)
    if amount != refund.amount_paise or (refund.provider_id and refund.provider_id != entity['id']):
        if refund.state != 'PROCESSED':
            refund.state = 'REVIEW'
            refund.message = 'Partial or multiple provider refunds require administrator review.'
            refund.save(update_fields=['state', 'message', 'updated_at'])
            queue_refund_email(refund)
        return refund
    if refund.state == 'PROCESSED':
        return refund
    # A stale pending message cannot erase a terminal failure; API recovery can
    # still advance it to processed once the provider resolves the refund.
    if refund.state == 'FAILED' and state == 'PENDING':
        return refund
    refund.provider_id = entity['id']
    refund.state = 'PROCESSING' if state == 'PENDING' else state
    refund.message = 'Provider reported a failed refund. Administrator action required.' if state == 'FAILED' else ''
    refund.next_check_at = timezone.now() + timedelta(minutes=2)
    if state == 'PROCESSED' and not refund.processed_at:
        refund.processed_at = timezone.now()
    refund.save(update_fields=['provider_id', 'state', 'message', 'next_check_at', 'updated_at', 'processed_at'])
    if state == 'PROCESSED':
        attempt.state = 'REFUNDED'
        attempt.save(update_fields=['state', 'updated_at'])
        booking = attempt.booking
        if booking.status == 'CONFIRMED' and booking.razorpay_payment_id == attempt.payment_id:
            from .services import group_members, _promote_locked
            group_members(booking).update(status='CANCELLED', expires_at=None)
            _promote_locked(booking.journey)
            booking.refresh_from_db()
            queue_booking_email(booking, 'CANCELLED')
    queue_refund_email(refund)
    return refund


def recover_booking(booking_id, user=None, force=False):
    """Poll only the stored order; never trust a client-supplied payment ID."""
    with transaction.atomic():
        query = Booking.objects.filter(pk=booking_id, group_parent__isnull=True)
        if user is not None:
            query = query.filter(user=user)
        booking = query.first()
        if not booking:
            raise ValidationError('Booking not found.')
        Journey.objects.select_for_update().get(pk=booking.journey_id)
        booking = Booking.objects.select_for_update().get(pk=booking.id)
        if not booking.razorpay_order_id:
            return booking
        cutoff = timezone.now() - timedelta(seconds=settings.PAYMENT_RECOVERY_INTERVAL_SECONDS)
        if not force and booking.payment_checked_at and booking.payment_checked_at > cutoff:
            return booking
        booking.payment_checked_at = timezone.now()
        booking.save(update_fields=['payment_checked_at'])
        order_id = booking.razorpay_order_id
    client = payments.payment_client()
    response = payments.gateway_call(client.order.payments, order_id)
    if not isinstance(response, dict) or not isinstance(response.get('items'), list):
        raise payments.PaymentUnavailable()
    for item in response['items']:
        if not isinstance(item, dict):
            raise payments.PaymentUnavailable()
        if item.get('order_id') != order_id:
            raise ValidationError('Payment order mismatch.')
        ingest_payment(item)
    # Pull existing refunds for captures, including refunds initiated in dashboard.
    for attempt in booking.payment_attempts.filter(state__in=['CAPTURED', 'REFUNDED']):
        response = payments.gateway_call(client.payment.fetch_multiple_refund, attempt.payment_id)
        if not isinstance(response, dict) or not isinstance(response.get('items'), list):
            raise payments.PaymentUnavailable()
        for item in response['items']:
            if not isinstance(item, dict):
                raise payments.PaymentUnavailable()
            apply_refund(item)
    booking.refresh_from_db()
    return booking


@transaction.atomic
def process_refund(refund_id):
    refund = Refund.objects.select_related('attempt__booking').get(pk=refund_id)
    Journey.objects.select_for_update().get(pk=refund.attempt.booking.journey_id)
    refund = Refund.objects.select_for_update().select_related('attempt').get(pk=refund_id)
    if refund.state in ['PROCESSED', 'REVIEW'] or refund.next_check_at > timezone.now():
        return refund
    client = payments.payment_client()
    # provider_id means a request exists: poll it, never issue another refund.
    # Unknown responses retry the identical payload and durable idempotency key.
    if refund.state == 'FAILED' and not refund.provider_id:
        return refund
    refund.attempts += 1
    refund.next_check_at = timezone.now() + timedelta(seconds=min(3600, 30 * (2 ** min(refund.attempts, 7))))
    try:
        if refund.provider_id:
            result = payments.gateway_call(client.refund.fetch, refund.provider_id)
        else:
            existing = payments.gateway_call(client.payment.fetch_multiple_refund, refund.attempt.payment_id)
            if not isinstance(existing, dict) or not isinstance(existing.get('items'), list):
                raise payments.PaymentUnavailable()
            # Discover a refund whose create response was lost (or one initiated
            # in the provider dashboard) before issuing any further request.
            if existing['items']:
                for entity in existing['items']:
                    applied = apply_refund(entity)
                    if applied and applied.pk == refund.pk:
                        applied.attempts = refund.attempts
                        applied.next_check_at = refund.next_check_at
                        applied.save(update_fields=['attempts', 'next_check_at'])
                        return applied
                raise payments.PaymentUnavailable()
            result = payments.gateway_call(client.payment.refund, refund.attempt.payment_id,
                data={'amount': refund.amount_paise, 'speed': 'normal', 'receipt': f'refund_{refund.pk}'},
                headers={'X-Refund-Idempotency': str(refund.idempotency_key)})
        applied = apply_refund(result)
        if not applied or applied.pk != refund.pk:
            raise payments.PaymentUnavailable()
        applied.attempts = refund.attempts
        applied.next_check_at = refund.next_check_at
        applied.save(update_fields=['attempts', 'next_check_at'])
        return applied
    except (payments.PaymentUnavailable, ValidationError):
        refund.state = 'UNKNOWN' if not refund.provider_id else 'PROCESSING'
        refund.message = 'Provider response unavailable. The same refund request will be reconciled safely.'
        refund.save(update_fields=['state', 'message', 'attempts', 'next_check_at', 'updated_at'])
        queue_refund_email(refund)
        return refund


def handle_webhook(raw_body, signature, event_id):
    secrets = [settings.RAZORPAY_WEBHOOK_SECRET, settings.RAZORPAY_WEBHOOK_PREVIOUS_SECRET]
    secrets = [secret for secret in secrets if secret]
    if not secrets:
        raise payments.PaymentUnavailable('Webhook signing secret is not configured.')
    if not isinstance(signature, str) or not re.fullmatch(r'[a-fA-F0-9]{64}', signature):
        raise PermissionDenied('Invalid webhook signature.')
    if not any(hmac.compare_digest(hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest(), signature.lower()) for secret in secrets):
        raise PermissionDenied('Invalid webhook signature.')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', event_id or ''):
        raise ValidationError('Invalid webhook event ID.')
    try:
        data = json.loads(raw_body)
    except (ValueError, UnicodeDecodeError):
        raise ValidationError('Invalid JSON body.') from None
    if not isinstance(data, dict) or not isinstance(data.get('event'), str):
        raise ValidationError('Invalid webhook event.')
    kind = data['event']
    if len(kind) > 80:
        raise ValidationError('Invalid event type.')
    digest = hashlib.sha256(raw_body).hexdigest()
    with transaction.atomic():
        receipt, _ = WebhookEvent.objects.get_or_create(event_id=event_id,
            defaults={'kind': kind, 'body_hash': digest})
        receipt = WebhookEvent.objects.select_for_update().get(pk=receipt.pk)
        if receipt.body_hash != digest:
            raise ValidationError('Event ID was already used with a different body.')
        if receipt.processed_at:
            return 'DUPLICATE'
        payload = data.get('payload', {})
        try:
            if kind in ['payment.authorized', 'payment.captured', 'payment.failed', 'payment.refunded', 'order.paid']:
                result = ingest_payment(payload['payment']['entity'])
            elif kind in ['refund.created', 'refund.processed', 'refund.failed']:
                result = apply_refund(payload['refund']['entity'])
            else:
                result = None
        except (KeyError, TypeError):
            raise ValidationError('Missing webhook entity.') from None
        receipt.outcome = 'APPLIED' if result else 'IGNORED'
        receipt.processed_at = timezone.now()
        receipt.save(update_fields=['outcome', 'processed_at'])
        return receipt.outcome
