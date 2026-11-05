import hashlib
import hmac
import json
from datetime import timedelta
from unittest.mock import patch
import requests
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from . import tests as booking_tests
from .models import Booking, PaymentAttempt, Refund, WebhookEvent
from .lifecycle import ingest_payment, process_refund, recover_booking, apply_refund
from .services import cancel_booking
from .payments import PaymentUnavailable


@override_settings(RAZORPAY_KEY_ID='rzp_test_unit', RAZORPAY_KEY_SECRET='unit-test-secret',
    RAZORPAY_WEBHOOK_SECRET='webhook-only-secret', RAZORPAY_WEBHOOK_PREVIOUS_SECRET='',
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class PaymentLifecycleTests(TransactionTestCase):
    setUp = booking_tests.BookingTests.setUp
    hold = booking_tests.BookingTests.hold
    evidence = booking_tests.BookingTests.evidence
    payment_record = booking_tests.BookingTests.payment_record

    def payment(self, **overrides):
        b = self.hold()
        self.evidence(b)
        return b, self.payment_record(b, **overrides)

    def webhook(self, entity, kind='payment.captured', event_id='evt_unit', secret=b'webhook-only-secret', raw=None):
        key = 'refund' if kind.startswith('refund.') else 'payment'
        raw = raw or json.dumps({'event':kind, 'payload':{key:{'entity':entity}}}).encode()
        signature = hmac.new(secret, raw, hashlib.sha256).hexdigest()
        client = APIClient()
        return client.post('/api/webhooks/razorpay/', raw, content_type='application/json',
            HTTP_X_RAZORPAY_SIGNATURE=signature, HTTP_X_RAZORPAY_EVENT_ID=event_id)

    def refund_entity(self, **overrides):
        entity={'id':'rfnd_unit','payment_id':'pay_unit','amount':28000,'currency':'INR','status':'processed'}
        entity.update(overrides)
        return entity

    def test_verified_webhook_confirms_without_browser_callback(self):
        b,p=self.payment()
        self.assertEqual(self.webhook(p).status_code,200)
        b.refresh_from_db();self.assertEqual(b.status,'CONFIRMED')
        self.assertEqual(PaymentAttempt.objects.get().state,'CAPTURED')

    def test_signature_is_over_exact_raw_body(self):
        b,p=self.payment()
        raw=json.dumps({'event':'payment.captured','payload':{'payment':{'entity':p}}}).encode()
        signature=hmac.new(b'webhook-only-secret',raw,hashlib.sha256).hexdigest()
        client=APIClient()
        response=client.post('/api/webhooks/razorpay/',raw+b' ',content_type='application/json',
            HTTP_X_RAZORPAY_SIGNATURE=signature,HTTP_X_RAZORPAY_EVENT_ID='evt_unit')
        self.assertEqual(response.status_code,403)
        self.assertEqual(WebhookEvent.objects.count(),0)
        b.refresh_from_db();self.assertEqual(b.status,'PENDING')

    def test_api_secret_cannot_be_used_as_webhook_secret(self):
        b,p=self.payment()
        self.assertEqual(self.webhook(p,secret=b'unit-test-secret').status_code,403)

    @override_settings(RAZORPAY_WEBHOOK_SECRET='')
    def test_missing_signing_secret_fails_closed(self):
        b,p=self.payment()
        self.assertEqual(self.webhook(p).status_code,503)

    @override_settings(RAZORPAY_WEBHOOK_PREVIOUS_SECRET='previous-webhook-secret')
    def test_previous_secret_supports_old_deliveries(self):
        b,p=self.payment()
        self.assertEqual(self.webhook(p,secret=b'previous-webhook-secret').status_code,200)

    def test_duplicate_events_apply_once(self):
        b,p=self.payment()
        self.assertEqual(self.webhook(p).status_code,200)
        response=self.webhook(p)
        self.assertEqual(response.data['status'],'DUPLICATE')
        self.assertEqual(WebhookEvent.objects.count(),1)
        self.assertEqual(PaymentAttempt.objects.count(),1)

    def test_reused_event_id_with_changed_body_is_rejected(self):
        b,p=self.payment();self.webhook(p)
        p=dict(p,status='failed')
        self.assertEqual(self.webhook(p).status_code,400)
        b.refresh_from_db();self.assertEqual(b.status,'CONFIRMED')

    def test_failed_event_cannot_undo_capture(self):
        b,p=self.payment();self.webhook(p)
        self.assertEqual(self.webhook(dict(p,status='failed'),kind='payment.failed',event_id='evt_failed').status_code,200)
        self.assertEqual(PaymentAttempt.objects.get().state,'CAPTURED')
        b.refresh_from_db();self.assertEqual(b.status,'CONFIRMED')

    def test_authorized_payment_waits_for_capture(self):
        b,p=self.payment(status='authorized',captured=False)
        self.assertEqual(self.webhook(p,kind='payment.authorized').status_code,200)
        b.refresh_from_db();self.assertEqual(b.status,'PENDING')
        self.assertEqual(PaymentAttempt.objects.get().state,'AUTHORIZED')
        self.assertEqual(self.client.post(f'/api/bookings/{b.id}/create-order/').status_code,400)

    def test_failed_attempt_is_saved_and_can_be_followed_by_success(self):
        b,p=self.payment(status='failed',captured=False)
        self.webhook(p,kind='payment.failed')
        self.assertEqual(PaymentAttempt.objects.get().state,'FAILED')
        p=dict(p,id='pay_retry',status='captured',captured=True)
        self.assertEqual(self.webhook(p,event_id='evt_retry').status_code,200)
        b.refresh_from_db();self.assertEqual(b.status,'CONFIRMED')
        self.assertEqual(b.razorpay_payment_id,'pay_retry')
        self.assertEqual(PaymentAttempt.objects.count(),2)

    def test_late_capture_queues_refund_without_resurrecting_hold(self):
        b,p=self.payment()
        Booking.objects.filter(pk=b.id).update(expires_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(self.webhook(p).status_code,200)
        b.refresh_from_db();self.assertEqual(b.status,'EXPIRED')
        self.assertEqual(Refund.objects.get().state,'REQUESTED')
        self.webhook(p,event_id='evt_repeated_capture')
        self.assertEqual(Refund.objects.count(),1)

    def test_cancelled_hold_later_paid_is_refunded(self):
        b,p=self.payment();cancel_booking(b.id,self.user)
        self.webhook(p)
        b.refresh_from_db();self.assertEqual(b.status,'CANCELLED')
        self.assertEqual(Refund.objects.get().amount_paise,28000)

    def test_paid_cancellation_queues_one_full_refund(self):
        b,p=self.payment();ingest_payment(p)
        cancel_booking(b.id,self.user);cancel_booking(b.id,self.user)
        self.assertEqual(Refund.objects.count(),1)
        self.assertEqual(Refund.objects.get().amount_paise,28000)

    def test_extra_capture_cannot_replace_ticket_payment(self):
        b,p=self.payment();ingest_payment(p)
        ingest_payment(dict(p,id='pay_extra'))
        b.refresh_from_db();self.assertEqual(b.razorpay_payment_id,'pay_unit')
        self.assertEqual(Refund.objects.get().attempt.payment_id,'pay_extra')

    def test_wrong_amount_is_quarantined_not_confirmed_or_auto_refunded(self):
        b,p=self.payment(amount=1)
        self.assertEqual(self.webhook(p).status_code,200)
        b.refresh_from_db();self.assertEqual(b.status,'PENDING')
        self.assertEqual(PaymentAttempt.objects.get().state,'REVIEW')
        self.assertEqual(Refund.objects.count(),0)

    @patch('bookings.payments.payment_client')
    def test_recovery_finds_payment_using_saved_order(self,client):
        b,p=self.payment()
        client.return_value.order.payments.return_value={'items':[p]}
        client.return_value.payment.fetch_multiple_refund.return_value={'items':[]}
        response=self.client.post(f'/api/bookings/{b.id}/recover-payment/', {'payment_id':'pay_fake'})
        self.assertEqual(response.status_code,200)
        client.return_value.order.payments.assert_called_once_with('order_unit')
        self.assertEqual(response.data['status'],'CONFIRMED')
        self.client.post(f'/api/bookings/{b.id}/recover-payment/')
        client.return_value.order.payments.assert_called_once()

    @patch('bookings.payments.payment_client')
    def test_pending_recovery_never_fakes_success(self,client):
        b,p=self.payment()
        client.return_value.order.payments.return_value={'items':[]}
        self.assertEqual(self.client.post(f'/api/bookings/{b.id}/recover-payment/').data['status'],'PENDING')

    def test_recovery_is_owner_scoped(self):
        b,p=self.payment();self.client.force_authenticate(self.other)
        self.assertEqual(self.client.post(f'/api/bookings/{b.id}/recover-payment/').status_code,404)

    @patch('bookings.payments.payment_client')
    def test_recovery_outage_is_safe(self,client):
        b,p=self.payment()
        client.return_value.order.payments.side_effect=requests.Timeout('private-provider-error')
        response=self.client.post(f'/api/bookings/{b.id}/recover-payment/')
        self.assertEqual(response.status_code,503)
        self.assertNotIn('private-provider-error',str(response.data))
        b.refresh_from_db();self.assertEqual(b.status,'PENDING')

    @patch('bookings.payments.payment_client')
    def test_refund_timeout_retries_same_idempotency_key(self,client):
        b,p=self.payment();ingest_payment(p);cancel_booking(b.id,self.user)
        refund=Refund.objects.get()
        client.return_value.payment.fetch_multiple_refund.return_value={'items':[]}
        client.return_value.payment.refund.side_effect=requests.Timeout('lost-response')
        process_refund(refund.id)
        refund.refresh_from_db();self.assertEqual(refund.state,'UNKNOWN')
        first=client.return_value.payment.refund.call_args
        Refund.objects.filter(pk=refund.id).update(next_check_at=timezone.now())
        client.return_value.payment.refund.side_effect=None
        client.return_value.payment.refund.return_value=self.refund_entity()
        process_refund(refund.id)
        second=client.return_value.payment.refund.call_args
        self.assertEqual(first,second)
        self.assertEqual(first.kwargs['headers']['X-Refund-Idempotency'],str(refund.idempotency_key))
        refund.refresh_from_db();self.assertEqual(refund.state,'PROCESSED')

    @patch('bookings.payments.payment_client')
    def test_existing_refund_is_polled_not_issued_again(self,client):
        b,p=self.payment();ingest_payment(p);cancel_booking(b.id,self.user)
        refund=Refund.objects.get()
        apply_refund(self.refund_entity(status='pending'))
        Refund.objects.filter(pk=refund.id).update(next_check_at=timezone.now())
        client.return_value.refund.fetch.return_value=self.refund_entity()
        process_refund(refund.id)
        client.return_value.payment.refund.assert_not_called()
        refund.refresh_from_db();self.assertEqual(refund.state,'PROCESSED')

    def test_refund_webhook_updates_cancelled_booking_tracking(self):
        b,p=self.payment();ingest_payment(p);cancel_booking(b.id,self.user)
        self.assertEqual(self.webhook(self.refund_entity(),kind='refund.processed').status_code,200)
        response=self.client.get(f'/api/bookings/{b.id}/')
        self.assertEqual(response.data['refunds'][0]['state'],'PROCESSED')
        self.assertEqual(response.data['payment_attempts'][0]['state'],'REFUNDED')
        self.assertEqual(response.data['status'],'CANCELLED')

    def test_processed_refund_is_not_downgraded_by_late_pending_or_failed(self):
        b,p=self.payment();ingest_payment(p);cancel_booking(b.id,self.user)
        self.webhook(self.refund_entity(),kind='refund.processed')
        self.webhook(self.refund_entity(status='pending'),kind='refund.created',event_id='evt_pending')
        self.webhook(self.refund_entity(status='failed'),kind='refund.failed',event_id='evt_failed')
        self.assertEqual(Refund.objects.get().state,'PROCESSED')

    def test_partial_refund_requires_manual_review(self):
        b,p=self.payment();ingest_payment(p);cancel_booking(b.id,self.user)
        self.webhook(self.refund_entity(amount=100),kind='refund.processed')
        self.assertEqual(Refund.objects.get().state,'REVIEW')

    def test_unknown_orders_and_unsupported_events_are_acknowledged(self):
        self.assertEqual(self.webhook({'id':'pay_unknown','order_id':'order_unknown'}).data['status'],'IGNORED')
        self.assertEqual(self.webhook({},kind='subscription.charged',event_id='evt_other').data['status'],'IGNORED')

    def test_malformed_verified_event_does_not_leave_success_receipt(self):
        response=self.webhook({},raw=b'{"event":"payment.captured","payload":{}}')
        self.assertEqual(response.status_code,400)
        self.assertEqual(WebhookEvent.objects.count(),0)

    def test_dashboard_refund_cancels_ticket_and_releases_seat(self):
        b,p=self.payment();ingest_payment(p)
        self.webhook(self.refund_entity(),kind='refund.processed')
        b.refresh_from_db();self.assertEqual(b.status,'CANCELLED')

    @patch('bookings.payments.payment_client')
    def test_worker_sweep_recovers_and_processes_durable_refund_queue(self,client):
        from .tasks import recover_payments_and_refunds
        b,p=self.payment();ingest_payment(p);cancel_booking(b.id,self.user)
        client.return_value.order.payments.return_value={'items':[p]}
        client.return_value.payment.fetch_multiple_refund.return_value={'items':[]}
        client.return_value.payment.refund.return_value=self.refund_entity()
        recover_payments_and_refunds()
        self.assertEqual(Refund.objects.get().state,'PROCESSED')

    @patch('bookings.payments.payment_client')
    def test_lost_create_response_is_discovered_before_another_refund(self,client):
        b,p=self.payment();ingest_payment(p);cancel_booking(b.id,self.user)
        refund=Refund.objects.get()
        Refund.objects.filter(pk=refund.pk).update(state='UNKNOWN')
        client.return_value.payment.fetch_multiple_refund.return_value={'items':[self.refund_entity()]}
        process_refund(refund.id)
        client.return_value.payment.refund.assert_not_called()
        refund.refresh_from_db();self.assertEqual(refund.state,'PROCESSED')
    @patch('bookings.payments.payment_client')
    def test_concurrent_refund_workers_submit_once(self,client):
        from concurrent.futures import ThreadPoolExecutor
        from django.db import close_old_connections
        b,p=self.payment();ingest_payment(p);cancel_booking(b.id,self.user)
        refund=Refund.objects.get()
        client.return_value.payment.fetch_multiple_refund.return_value={'items':[]}
        client.return_value.payment.refund.return_value=self.refund_entity(status='pending')
        def run(_):
            close_old_connections()
            try:
                return process_refund(refund.id).state
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            states=list(pool.map(run,range(2)))
        self.assertEqual(states,['PROCESSING','PROCESSING'])
        client.return_value.payment.refund.assert_called_once()

    def test_concurrent_duplicate_webhooks_are_idempotent(self):
        from concurrent.futures import ThreadPoolExecutor
        from django.db import close_old_connections
        b,p=self.payment()
        def run(_):
            close_old_connections()
            try:
                return self.webhook(p).data['status']
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(run,range(2)))
        self.assertCountEqual(results,['APPLIED','DUPLICATE'])
        self.assertEqual(PaymentAttempt.objects.count(),1)
        b.refresh_from_db();self.assertEqual(b.status,'CONFIRMED')

    def test_group_capture_and_cancellation_refund_the_complete_total(self):
        self.group=booking_tests.GroupCheckoutTests.group.__get__(self)
        self.details=booking_tests.GroupCheckoutTests.details.__get__(self)
        self.ready=booking_tests.GroupCheckoutTests.ready.__get__(self)
        b=self.group();self.ready(b);self.evidence(b)
        p=self.payment_record(b,amount=56000)
        self.assertEqual(self.webhook(p).status_code,200)
        self.assertEqual(Booking.objects.filter(status='CONFIRMED').count(),2)
        cancel_booking(b.id,self.user)
        self.assertEqual(Booking.objects.filter(status='CANCELLED').count(),2)
        self.assertEqual(Refund.objects.get().amount_paise,56000)
