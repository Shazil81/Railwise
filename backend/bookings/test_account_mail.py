from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core import mail
from django.db import close_old_connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from .account_links import issue_link
from .account_mail import dispatch_account_emails, deliver_account_email
from .models import AccountEmail, AccountLink, AccountLinkDelivery


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class AccountMailTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user(username='queued',email='queued@example.invalid',password='Queue!Password927')

    def queue(self):
        raw='private-bearer-token-'+str(AccountLink.objects.count()+1)
        with patch('bookings.account_links.secrets.token_urlsafe',return_value=raw):
            issue_link(self.user,'verify')
        return AccountLinkDelivery.objects.latest('pk')

    def test_api_path_never_sends_and_outbox_has_no_plaintext_token(self):
        with patch('bookings.account_mail.send_mail') as sender:
            item=self.queue()
        sender.assert_not_called()
        self.assertNotIn('private-bearer-token',item.token_ciphertext)
        self.assertNotIn('private-bearer-token',item.link.digest)
        self.assertEqual(dispatch_account_emails(),{'SENT':1})
        self.assertIn('private-bearer-token',mail.outbox[0].body)
        item.refresh_from_db()
        self.assertEqual(item.token_ciphertext,'')
        self.assertIsNotNone(item.sent_at)
        dispatch_account_emails()
        self.assertEqual(len(mail.outbox),1)

    def test_retry_is_bounded_and_does_not_log_transport_details(self):
        item=self.queue()
        with patch('bookings.account_mail.send_mail',side_effect=RuntimeError('private-bearer-token queued@example.invalid secret-password')):
            with self.assertLogs('bookings.account_mail',level='WARNING') as logs:
                self.assertEqual(deliver_account_email(item.pk),'RETRY')
            self.assertNotIn('private-bearer-token',''.join(logs.output))
            self.assertNotIn(self.user.email,''.join(logs.output))
            self.assertNotIn('secret-password',''.join(logs.output))
            item.refresh_from_db()
            self.assertEqual(item.attempts,1)
            self.assertTrue(item.token_ciphertext)
            self.assertEqual(dispatch_account_emails(),{})
            AccountLinkDelivery.objects.filter(pk=item.pk).update(attempts=4,next_attempt_at=timezone.now())
            self.assertEqual(deliver_account_email(item.pk),'FAILED')
        item.refresh_from_db()
        self.assertEqual(item.token_ciphertext,'')

    def test_expired_superseded_and_consumed_links_never_send(self):
        item=self.queue()
        AccountLink.objects.filter(pk=item.link_id).update(expires_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(deliver_account_email(item.pk),'SKIPPED')
        item=self.queue()
        # A new request supersedes the old queue entry and destroys its payload.
        issue_link(self.user,'verify')
        item.refresh_from_db()
        self.assertEqual((item.state,item.token_ciphertext),('SKIPPED',''))
        latest=AccountLinkDelivery.objects.latest('pk')
        AccountLink.objects.filter(pk=latest.link_id).update(used_at=timezone.now())
        self.assertEqual(deliver_account_email(latest.pk),'SKIPPED')
        self.assertEqual(len(mail.outbox),0)

    def test_identity_changes_do_not_redirect_the_link(self):
        for change in [{'email':'new@example.invalid'},{'is_active':False},{'password':'changed-hash'}]:
            item=self.queue()
            with transaction.atomic():
                old={key:getattr(self.user,key) for key in change}
                get_user_model().objects.filter(pk=self.user.pk).update(**change)
                self.assertEqual(deliver_account_email(item.pk),'SKIPPED')
                get_user_model().objects.filter(pk=self.user.pk).update(**old)
        self.assertEqual(len(mail.outbox),0)

    def test_invalid_encrypted_payload_fails_closed(self):
        item=self.queue()
        AccountLinkDelivery.objects.filter(pk=item.pk).update(token_ciphertext='corrupt')
        self.assertEqual(deliver_account_email(item.pk),'FAILED')
        self.assertEqual(len(mail.outbox),0)

    def test_outbox_rolls_back_with_link_transaction(self):
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                self.queue()
                raise RuntimeError('rollback')
        self.assertFalse(AccountLink.objects.exists())
        self.assertFalse(AccountLinkDelivery.objects.exists())

    def test_reset_is_skipped_if_verified_identity_is_revoked_before_delivery(self):
        AccountEmail.objects.create(user=self.user,verified_email=self.user.email)
        issue_link(self.user,'reset')
        AccountEmail.objects.filter(user=self.user).delete()
        self.assertEqual(dispatch_account_emails(),{'SKIPPED':1})
        self.assertEqual(len(mail.outbox),0)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ConcurrentAccountMailTests(TransactionTestCase):
    def test_two_dispatchers_send_only_once(self):
        user=get_user_model().objects.create_user(username='concurrent-mail',email='mail@example.invalid',password='Queue!Password927')
        issue_link(user,'verify')
        pk=AccountLinkDelivery.objects.get().pk
        def deliver(_):
            close_old_connections()
            try:
                return deliver_account_email(pk)
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(list(pool.map(deliver,range(2))),['SENT','SENT'])
        self.assertEqual(len(mail.outbox),1)
