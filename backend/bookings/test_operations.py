import json
import logging
from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.test import TestCase, Client, override_settings
from django.utils import timezone
from . import tests as fixtures
from .models import Booking, BookingEmail, PaymentAttempt, Refund, OperationAudit
from .operations import VIEW_PERMISSIONS, operations_snapshot, retry_failed_emails
from .ops_logging import OperationsFormatter


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class OperationsTests(TestCase):
    def setUp(self):
        fixtures.BookingTests.setUp(self)
        self.web=Client()
        self.staff=get_user_model().objects.create_user('operator',is_staff=True)
        names=[permission.split('.')[1] for permission in VIEW_PERMISSIONS]
        self.staff.user_permissions.set(Permission.objects.filter(content_type__app_label='bookings',codename__in=names))
        self.booking=fixtures.BookingTests.hold(self)
        self.email=BookingEmail.objects.create(booking=self.booking,event_key='ops-fixture',kind='CANCELLED',state='FAILED',
            recipient='private@example.com',subject='secret subject',body='private passenger email body',attempts=5,last_error='sensitive provider error')

    def allow_retry(self):
        self.staff.user_permissions.add(Permission.objects.get(content_type__app_label='bookings',codename='change_bookingemail'))
        self.staff=get_user_model().objects.get(pk=self.staff.pk)

    def test_anonymous_and_nonstaff_cannot_view_dashboard(self):
        self.assertEqual(self.web.get('/admin/operations/').status_code,302)
        self.web.force_login(self.user)
        self.assertEqual(self.web.get('/admin/operations/').status_code,302)

    def test_staff_without_all_view_permissions_is_denied(self):
        self.staff.user_permissions.clear()
        self.web.force_login(self.staff)
        self.assertEqual(self.web.get('/admin/operations/').status_code,403)

    def test_readonly_operator_sees_snapshot_without_secrets(self):
        self.web.force_login(self.staff)
        response=self.web.get('/admin/operations/')
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'Keep every journey on track.')
        self.assertNotContains(response,'Retry email')
        for secret in ['private@example.com','private passenger email body','sensitive provider error','secret subject']:
            self.assertNotContains(response,secret)
        self.assertIn('no-store',response['Cache-Control'])

    def test_get_does_not_mutate_expired_holds_or_call_providers(self):
        Booking.objects.filter(pk=self.booking.pk).update(expires_at=timezone.now()-timedelta(minutes=1))
        self.web.force_login(self.staff)
        with patch('bookings.payments.payment_client') as gateway,patch('bookings.notifications.EmailMessage.send') as email:
            response=self.web.get('/admin/operations/')
        self.assertEqual(response.context['snapshot']['alerts']['holds'],1)
        self.booking.refresh_from_db();self.assertEqual(self.booking.status,'PENDING')
        gateway.assert_not_called();email.assert_not_called()

    def test_retry_requires_post_and_change_permission(self):
        self.web.force_login(self.staff)
        url=f'/admin/operations/emails/{self.email.pk}/retry/'
        self.assertEqual(self.web.get(url).status_code,405)
        self.assertEqual(self.web.post(url).status_code,403)
        self.assertEqual(OperationAudit.objects.count(),0)

    def test_retry_only_requeues_and_records_actor(self):
        self.allow_retry();self.web.force_login(self.staff)
        with patch('bookings.payments.payment_client') as gateway,patch('bookings.notifications.EmailMessage.send') as email:
            response=self.web.post(f'/admin/operations/emails/{self.email.pk}/retry/')
        self.assertEqual(response.status_code,302)
        self.email.refresh_from_db()
        self.assertEqual(self.email.state,'RETRY');self.assertEqual(self.email.attempts,0)
        audit=OperationAudit.objects.get()
        self.assertEqual(audit.actor_id,self.staff.pk);self.assertEqual(audit.outcome,'REQUEUED')
        self.assertEqual(audit.target_id,self.email.pk)
        gateway.assert_not_called();email.assert_not_called()

    def test_repeated_retry_does_not_reset_live_notification(self):
        self.allow_retry()
        self.assertEqual(retry_failed_emails(self.staff,[self.email.pk]),1)
        self.assertEqual(retry_failed_emails(self.staff,[self.email.pk]),0)
        self.assertEqual(list(OperationAudit.objects.order_by('pk').values_list('outcome',flat=True)),['REQUEUED','SKIPPED'])

    def test_csrf_is_required_even_for_authorized_staff(self):
        self.allow_retry();client=Client(enforce_csrf_checks=True);client.force_login(self.staff)
        self.assertEqual(client.post(f'/admin/operations/emails/{self.email.pk}/retry/').status_code,403)
        response=client.get('/admin/operations/')
        token=response.cookies['csrftoken'].value
        self.assertEqual(client.post(f'/admin/operations/emails/{self.email.pk}/retry/',HTTP_X_CSRFTOKEN=token).status_code,302)

    def test_retry_rollback_keeps_original_state_and_no_audit(self):
        self.allow_retry()
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                retry_failed_emails(self.staff,[self.email.pk])
                raise RuntimeError('rollback')
        self.email.refresh_from_db();self.assertEqual(self.email.state,'FAILED')
        self.assertEqual(OperationAudit.objects.count(),0)

    def test_summary_counts_groups_and_exception_thresholds(self):
        Booking.objects.create(group_parent=self.booking,user=self.user,journey=self.journey,from_seq=1,to_seq=5,status='CANCELLED')
        attempt=PaymentAttempt.objects.create(booking=self.booking,payment_id='pay_ops',order_id='order_ops',amount_paise=28000,state='AUTHORIZED')
        refund=Refund.objects.create(attempt=attempt,amount_paise=28000,reason='fixture')
        snapshot=operations_snapshot()
        self.assertEqual(snapshot['bookings'],{'PENDING':1})
        self.assertEqual(snapshot['alerts']['payments'],0);self.assertEqual(snapshot['alerts']['refunds'],0)
        # Fresh provider polling must not hide an old unresolved payment.
        PaymentAttempt.objects.filter(pk=attempt.pk).update(created_at=timezone.now()-timedelta(minutes=20))
        Refund.objects.filter(pk=refund.pk).update(created_at=timezone.now()-timedelta(minutes=20))
        snapshot=operations_snapshot()
        self.assertEqual(snapshot['alerts']['payments'],1);self.assertEqual(snapshot['alerts']['refunds'],1)

    def test_mutation_service_blocks_nonstaff_even_with_permission(self):
        self.user.user_permissions.add(Permission.objects.get(content_type__app_label='bookings',codename='change_bookingemail'))
        with self.assertRaises(PermissionDenied):retry_failed_emails(self.user,[self.email.pk])

    def test_batch_limit_and_missing_target(self):
        self.allow_retry()
        with self.assertRaises(ValidationError):retry_failed_emails(self.staff,list(range(201)))
        self.web.force_login(self.staff)
        self.assertEqual(self.web.post('/admin/operations/emails/999999/retry/').status_code,404)

    def test_structured_log_excludes_freeform_secrets(self):
        record=logging.LogRecord('railwise.operations',logging.INFO,'',0,'password=secret@example.com',(),None)
        record.actor_id=10;record.notification_id=20;record.outcome='REQUEUED';record.password='sensitive'
        text=OperationsFormatter().format(record)
        self.assertNotIn('secret',text);self.assertNotIn('password',text)
        self.assertEqual(json.loads(text)['notification_id'],20)

    def test_audit_admin_is_readonly(self):
        from django.contrib import admin
        from django.test import RequestFactory
        request=RequestFactory().get('/admin/');request.user=self.staff
        modeladmin=admin.site._registry[OperationAudit]
        self.assertFalse(modeladmin.has_add_permission(request))
        self.assertFalse(modeladmin.has_change_permission(request))
        self.assertFalse(modeladmin.has_delete_permission(request))
