from datetime import timedelta
from unittest.mock import patch
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from . import tests as fixtures
from .models import PaymentAttempt, Refund
from .lifecycle import ingest_payment, apply_refund


@override_settings(RAZORPAY_KEY_ID='rzp_test_unit', RAZORPAY_KEY_SECRET='unit-test-secret',
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class BookingDisplayTests(TransactionTestCase):
    hold = fixtures.BookingTests.hold
    evidence = fixtures.BookingTests.evidence
    payment_record = fixtures.BookingTests.payment_record
    def payment(self, **overrides):
        booking = self.hold()
        self.evidence(booking)
        return booking, self.payment_record(booking, **overrides)

    def setUp(self):
        fixtures.BookingTests.setUp(self)
        self.journey.date = timezone.localdate() + timedelta(days=2)
        self.journey.save()

    def test_saved_timetable_uses_actual_boarding_day_and_overnight_duration(self):
        self.train.stops.filter(sequence=1).update(day=2, departure='23:00')
        self.train.stops.filter(sequence=5).update(day=3, arrival='06:30')
        b = self.hold()
        data = self.client.get(f'/api/bookings/{b.id}/').data
        self.assertEqual(data['date'], self.journey.date + timedelta(days=1))
        self.assertEqual(data['duration_minutes'], 450)
        self.assertIn('T23:00:00+05:30', data['departure_at'])
        self.assertIn('T06:30:00+05:30', data['arrival_at'])
        self.assertEqual(data['origin_code'], 'S1')
        self.assertEqual(data['booked_at'], b.created_at)

    def test_missing_timetable_times_are_not_invented(self):
        b = self.hold()
        data = self.client.get(f'/api/bookings/{b.id}/').data
        self.assertIsNone(data['departure_at'])
        self.assertIsNone(data['arrival_at'])
        self.assertIsNone(data['duration_minutes'])

    def test_cancel_preview_is_read_only_and_refund_uses_captured_amount(self):
        b, payment = self.payment()
        ingest_payment(payment)
        response = self.client.get(f'/api/bookings/{b.id}/cancel-preview/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['can_cancel'])
        self.assertEqual(response.data['refund_estimate'], '280.00')
        b.refresh_from_db()
        self.assertEqual(b.status, 'CONFIRMED')
        self.assertEqual(Refund.objects.count(), 0)

    def test_unpaid_preview_has_no_promised_refund(self):
        b = self.hold()
        data = self.client.get(f'/api/bookings/{b.id}/cancel-preview/').data
        self.assertEqual(data['refund_estimate'], '0.00')

    def test_cancel_preview_respects_owner_and_departure_cutoff(self):
        b = self.hold()
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(f'/api/bookings/{b.id}/cancel-preview/').status_code, 404)
        self.client.force_authenticate(self.user)
        with patch('bookings.rules.timezone.now', return_value=timezone.now()+timedelta(days=4)):
            data = self.client.get(f'/api/bookings/{b.id}/cancel-preview/').data
            self.assertFalse(data['can_cancel'])
            self.assertEqual(data['refund_estimate'], '0.00')
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(f'/api/bookings/{b.id}/cancel-preview/').status_code, 401)

    def test_verified_payment_metadata_is_idempotent_and_does_not_store_card_details(self):
        b, payment = self.payment(method='upi', created_at=1700000000, card={'last4':'1234'})
        ingest_payment(payment)
        attempt = PaymentAttempt.objects.get(booking=b)
        captured = attempt.captured_at
        self.assertEqual(attempt.method, 'upi')
        self.assertEqual(int(attempt.provider_created_at.timestamp()), 1700000000)
        self.assertIsNotNone(captured)
        ingest_payment(payment)
        attempt.refresh_from_db()
        self.assertEqual(attempt.captured_at, captured)
        data = self.client.get(f'/api/bookings/{b.id}/').data['payment_attempts'][0]
        self.assertEqual(data['method'], 'upi')
        self.assertNotIn('1234', str(data))

    def test_unknown_provider_metadata_is_safe(self):
        b, payment = self.payment(method='untrusted-method', created_at=10**30)
        ingest_payment(payment)
        attempt = PaymentAttempt.objects.get(booking=b)
        self.assertEqual(attempt.method, '')
        self.assertIsNone(attempt.provider_created_at)

    def test_refund_processed_time_is_recorded_once(self):
        b, payment = self.payment()
        ingest_payment(payment)
        entity={'id':'rfnd_unit','payment_id':payment['id'],'amount':payment['amount'],'currency':'INR','status':'processed'}
        refund = apply_refund(entity)
        processed = refund.processed_at
        self.assertIsNotNone(processed)
        self.assertEqual(apply_refund(entity).processed_at, processed)
