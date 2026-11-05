from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import StringIO
from unittest.mock import patch
from django.core import mail
from django.core.management import call_command
from django.db import close_old_connections, transaction
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from . import tests as fixtures
from .models import AccountEmail, BookingEmail, Refund
from .notifications import deliver_booking_email, dispatch_booking_emails
from .lifecycle import ingest_payment, apply_refund
from .services import cancel_booking


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'], BOOKING_EMAIL_MAX_ATTEMPTS=3)
class NotificationTests(TransactionTestCase):
    hold=fixtures.BookingTests.hold
    evidence=fixtures.BookingTests.evidence
    payment_record=fixtures.BookingTests.payment_record
    group=fixtures.GroupCheckoutTests.group
    details=fixtures.GroupCheckoutTests.details
    ready=fixtures.GroupCheckoutTests.ready

    def setUp(self):
        fixtures.BookingTests.setUp(self)
        self.user.email='verified@example.com'
        self.user.save(update_fields=['email'])
        AccountEmail.objects.create(user=self.user,verified_email=self.user.email)

    def captured(self):
        b=self.hold();self.evidence(b)
        return ingest_payment(self.payment_record(b))

    def refund(self,state='processed'):
        return apply_refund({'id':'rfnd_unit','payment_id':'pay_unit','amount':28000,'currency':'INR','status':state})

    def test_capture_queues_once_without_sending_in_transaction(self):
        b=self.captured()
        ingest_payment(self.payment_record(b))
        self.assertEqual(BookingEmail.objects.count(),1)
        item=BookingEmail.objects.get()
        self.assertEqual(item.kind,'CONFIRMED')
        self.assertEqual(len(mail.outbox),0)
        self.assertEqual(deliver_booking_email(item.id),'SENT')
        self.assertEqual(deliver_booking_email(item.id),'SENT')
        self.assertEqual(len(mail.outbox),1)
        item.refresh_from_db()
        self.assertEqual(item.delivery_channel,'local')
        self.assertEqual(mail.outbox[0].to,['verified@example.com'])
        self.assertNotIn(b.contact_email,mail.outbox[0].to)
        for text in ['Test Traveller','C1-1','Station 1','Station 5','280.00','pay_unit','NOT VALID FOR TRAVEL']:
            self.assertIn(text,mail.outbox[0].body)

    def test_rollback_removes_event_and_no_email_escapes(self):
        b=self.hold();self.evidence(b)
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                ingest_payment(self.payment_record(b))
                raise RuntimeError('rollback')
        self.assertEqual(BookingEmail.objects.count(),0)
        self.assertEqual(len(mail.outbox),0)

    def test_duplicate_cancellation_and_refund_queue(self):
        b=self.captured()
        cancel_booking(b.id,self.user);cancel_booking(b.id,self.user)
        self.assertEqual(BookingEmail.objects.filter(kind='CANCELLED').count(),1)
        self.assertEqual(BookingEmail.objects.filter(kind='REFUND_REQUESTED').count(),1)
        self.assertEqual(Refund.objects.count(),1)

    def test_pending_cancellation_without_payment_also_notifies(self):
        b=self.hold()
        cancel_booking(b.id,self.user)
        self.assertEqual(BookingEmail.objects.get().kind,'CANCELLED')
        self.assertEqual(Refund.objects.count(),0)

    def test_processed_refund_is_notified_once(self):
        b=self.captured();cancel_booking(b.id,self.user)
        self.refund();self.refund()
        self.assertEqual(BookingEmail.objects.filter(kind='REFUND_PROCESSED').count(),1)
        item=BookingEmail.objects.get(kind='REFUND_PROCESSED')
        self.assertEqual(deliver_booking_email(item.id),'SENT')
        self.assertIn('Bank credit timing',mail.outbox[0].body)
        self.assertIn('rfnd_unit',mail.outbox[0].body)

    def test_failed_and_processing_refund_updates(self):
        b=self.captured();cancel_booking(b.id,self.user)
        self.refund('pending');self.refund('failed');self.refund('failed')
        self.assertEqual(BookingEmail.objects.filter(kind='REFUND_PROCESSING').count(),1)
        self.assertEqual(BookingEmail.objects.filter(kind='REFUND_FAILED').count(),1)

    def test_smtp_failure_redacted_retry_then_success(self):
        self.captured();item=BookingEmail.objects.get()
        with patch('bookings.notifications.EmailMessage.send',side_effect=RuntimeError('secret@example.com sensitive-password')):
            self.assertEqual(deliver_booking_email(item.id),'RETRY')
        item.refresh_from_db()
        self.assertNotIn('sensitive',item.last_error)
        self.assertGreater(item.next_attempt_at,timezone.now())
        self.assertEqual(deliver_booking_email(item.id),'RETRY')
        item.refresh_from_db();self.assertEqual(item.attempts,1)
        BookingEmail.objects.filter(pk=item.pk).update(next_attempt_at=timezone.now())
        self.assertEqual(deliver_booking_email(item.id),'SENT')
        self.assertEqual(len(mail.outbox),1)

    def test_zero_backend_result_and_retry_limit(self):
        self.captured();item=BookingEmail.objects.get()
        with patch('bookings.notifications.EmailMessage.send',return_value=0):
            for _ in range(3):
                BookingEmail.objects.filter(pk=item.pk).update(next_attempt_at=timezone.now())
                deliver_booking_email(item.id)
        item.refresh_from_db();self.assertEqual(item.state,'FAILED')
        self.assertEqual(item.attempts,3)
        self.assertEqual(dispatch_booking_emails(),{})

    def test_unverified_waits_then_verification_wakes_queue(self):
        AccountEmail.objects.all().delete()
        self.captured();item=BookingEmail.objects.get()
        self.assertEqual(item.state,'WAITING_VERIFICATION')
        self.assertEqual(dispatch_booking_emails(),{})
        from .account_links import issue_link
        with patch('bookings.account_links.secrets.token_urlsafe',return_value='verification-test-token'):
            issue_link(self.user,'verify')
        self.assertEqual(self.client.post('/api/accounts/verify-email/',{'token':'verification-test-token'}).status_code,200)
        item.refresh_from_db();self.assertEqual(item.state,'QUEUED')
        self.assertEqual(deliver_booking_email(item.id),'SENT')

    def test_changed_email_never_redirects_existing_event(self):
        self.captured();item=BookingEmail.objects.get()
        self.user.email='different@example.com';self.user.save()
        self.assertEqual(deliver_booking_email(item.id),'WAITING_VERIFICATION')
        AccountEmail.objects.update(verified_email=self.user.email)
        self.assertEqual(deliver_booking_email(item.id),'SKIPPED')
        self.assertEqual(len(mail.outbox),0)

    def test_old_confirmation_and_refund_states_are_skipped(self):
        b=self.captured();confirmation=BookingEmail.objects.get()
        cancel_booking(b.id,self.user)
        queued=BookingEmail.objects.get(kind='REFUND_REQUESTED')
        self.refund()
        self.assertEqual(deliver_booking_email(confirmation.id),'SKIPPED')
        self.assertEqual(deliver_booking_email(queued.id),'SKIPPED')

    def test_owner_only_delivery_metadata_excludes_body(self):
        b=self.captured()
        response=self.client.get(f'/api/bookings/{b.id}/')
        self.assertEqual(response.data['email_notifications'][0]['state'],'QUEUED')
        self.assertNotIn('body',response.data['email_notifications'][0])
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(f'/api/bookings/{b.id}/').status_code,404)

    def test_two_workers_send_same_notification_once(self):
        self.captured();item=BookingEmail.objects.get()
        def deliver(_):
            close_old_connections()
            try:return deliver_booking_email(item.id)
            finally:close_old_connections()
        with patch('bookings.notifications.EmailMessage.send',return_value=1) as send:
            with ThreadPoolExecutor(max_workers=2) as pool:
                self.assertEqual(list(pool.map(deliver,[1,2])),['SENT','SENT'])
            self.assertEqual(send.call_count,1)

    def test_management_command_dispatches_without_gateway_calls(self):
        self.captured()
        with patch('bookings.payments.payment_client') as gateway:
            call_command('send_booking_notifications',stdout=StringIO())
            gateway.assert_not_called()
        self.assertEqual(len(mail.outbox),1)

    def test_group_confirmation_contains_all_passengers_once(self):
        b=self.group();self.ready(b);self.evidence(b)
        b=ingest_payment(self.payment_record(b,amount=56000))
        item=BookingEmail.objects.get(kind='CONFIRMED')
        self.assertEqual(BookingEmail.objects.count(),1)
        self.assertEqual(deliver_booking_email(item.id),'SENT')
        for value in ['Test Traveller A','Test Traveller B','C1-1','C1-2','560.00']:
            self.assertIn(value,mail.outbox[0].body)

    def test_new_state_skips_superseded_emails_even_while_unverified(self):
        AccountEmail.objects.all().delete()
        b=self.captured();cancel_booking(b.id,self.user);self.refund()
        self.assertEqual(BookingEmail.objects.get(kind='CONFIRMED').state,'SKIPPED')
        self.assertEqual(BookingEmail.objects.get(kind='REFUND_REQUESTED').state,'SKIPPED')

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend')
    def test_console_backend_prints_email_without_smtp(self):
        self.captured();item=BookingEmail.objects.get()
        stream=StringIO()
        with patch('sys.stdout',stream):
            self.assertEqual(deliver_booking_email(item.id),'SENT')
        self.assertIn('verified@example.com',stream.getvalue())
        self.assertIn('Booking confirmed',stream.getvalue())
