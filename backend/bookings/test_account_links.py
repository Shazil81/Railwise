from datetime import timedelta
from unittest.mock import patch
from urllib.parse import urlsplit, parse_qs
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient
from .models import AccountEmail, AccountLink


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', FRONTEND_URL='https://railwise.example', ACCOUNT_LINK_TIMEOUT=1800)
class AccountLinkTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(username='traveller', email='traveller@example.com', password='Violet!Railway482')
        self.identity = {'username': self.user.username, 'email': self.user.email}

    def tearDown(self):
        cache.clear()

    def request_link(self, purpose='verify'):
        path = 'request-verification' if purpose == 'verify' else 'forgot-password'
        response = self.client.post(f'/api/accounts/{path}/', self.identity)
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertNotIn('token', response.data)
        url = next(line for line in mail.outbox[-1].body.splitlines() if line.startswith('https://'))
        self.assertTrue(url.startswith('https://railwise.example/#'))
        return parse_qs(urlsplit(url).fragment)['token'][0]

    def verified(self):
        AccountEmail.objects.create(user=self.user, verified_email=self.user.email)

    def consume(self, token, purpose='verify', **extra):
        path = 'verify-email' if purpose == 'verify' else 'reset-password'
        return self.client.post(f'/api/accounts/{path}/', {'token': token, **extra})

    def test_verify_single_use_and_hashed_storage(self):
        token = self.request_link()
        self.assertNotEqual(AccountLink.objects.get().digest, token)
        response = self.consume(token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(AccountEmail.objects.get().verified_email, self.user.email)
        self.assertEqual(self.consume(token).status_code, 400)
        self.assertEqual(len(mail.outbox), 1)

    def test_unknown_identity_and_unverified_reset_are_generic(self):
        response = self.client.post('/api/accounts/forgot-password/', self.identity)
        missing = self.client.post('/api/accounts/forgot-password/', self.identity | {'username': 'unknown'})
        wrong_email = self.client.post('/api/accounts/forgot-password/', self.identity | {'email': 'other@example.com'})
        self.assertEqual(response.data, missing.data)
        self.assertEqual(response.data, wrong_email.data)
        self.assertEqual(AccountLink.objects.count(), 0)

    def test_reset_changes_password_revokes_sessions_and_rejects_replay(self):
        self.verified()
        old = Token.objects.create(user=self.user)
        token = self.request_link('reset')
        password = {'password': 'New!OrchidTraveller625', 'password_confirm': 'New!OrchidTraveller625'}
        self.assertEqual(self.consume(token, 'reset', **password).status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(password['password']))
        self.assertFalse(Token.objects.filter(pk=old.pk).exists())
        self.assertEqual(self.consume(token, 'reset', **password).status_code, 400)
        self.client.credentials(HTTP_AUTHORIZATION='Token '+old.key)
        self.assertEqual(self.client.get('/api/bookings/').status_code, 401)
        self.assertEqual(self.client.post('/api/token/', {'username':self.user.username,'password':password['password']}).status_code, 200)

    def test_weak_and_mismatched_password_do_not_consume_link(self):
        self.verified()
        token = self.request_link('reset')
        for password, confirmation in [('12345678','12345678'), ('Strong!Password694','different')]:
            self.assertEqual(self.consume(token, 'reset', password=password,password_confirm=confirmation).status_code,400)
        self.assertIsNone(AccountLink.objects.get().used_at)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Violet!Railway482'))

    def test_expired_tampered_and_wrong_purpose_links(self):
        token = self.request_link()
        self.assertEqual(self.consume(token+'x').status_code,400)
        self.assertEqual(self.consume(token,'reset').status_code,400)
        AccountLink.objects.update(expires_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(self.consume(token).status_code,400)

    def test_resend_invalidates_previous_link(self):
        old = self.request_link()
        new = self.request_link()
        self.assertEqual(self.consume(old).status_code,400)
        self.assertEqual(self.consume(new).status_code,200)

    def test_password_change_elsewhere_invalidates_link(self):
        token=self.request_link()
        self.user.set_password('Changed!Password652')
        self.user.save(update_fields=['password'])
        self.assertEqual(self.consume(token).status_code,400)

    def test_email_change_and_inactive_user_invalidate_link(self):
        token = self.request_link()
        self.user.email='changed@example.com'
        self.user.save(update_fields=['email'])
        self.assertEqual(self.consume(token).status_code,400)
        self.user.email=self.identity['email']
        self.user.is_active=False
        self.user.save()
        self.assertEqual(self.consume(token).status_code,400)

    def test_status_is_owner_only_and_tracks_current_email(self):
        self.assertEqual(self.client.get('/api/accounts/me/').status_code,401)
        self.client.force_authenticate(self.user)
        self.assertFalse(self.client.get('/api/accounts/me/').data['email_verified'])
        self.verified()
        self.assertTrue(self.client.get('/api/accounts/me/').data['email_verified'])
        self.user.email='changed@example.com'
        self.user.save()
        self.assertFalse(self.client.get('/api/accounts/me/').data['email_verified'])

    def test_throttle_covers_known_and_unknown_accounts(self):
        for _ in range(5):
            self.assertEqual(self.client.post('/api/accounts/request-verification/', self.identity | {'username':'unknown'}).status_code,202)
        self.assertEqual(self.client.post('/api/accounts/request-verification/',self.identity).status_code,429)

    def test_provider_failure_does_not_leak_or_rollback_signup(self):
        with patch('bookings.account_links.send_mail',side_effect=RuntimeError('sensitive provider details')):
            with self.assertLogs('bookings.account_links',level='WARNING') as log:
                response=self.client.post('/api/accounts/request-verification/',self.identity)
        self.assertEqual(response.status_code,202)
        self.assertNotIn('sensitive',str(log.output))
        self.assertNotIn(self.user.email,str(log.output))

    def test_signup_sends_verification_after_commit(self):
        with self.captureOnCommitCallbacks(execute=True):
            response=self.client.post('/api/accounts/signup/',{'username':'newtraveller','email':'new@example.com',
                'password':'Violet!Journey492','password_confirm':'Violet!Journey492'})
        self.assertEqual(response.status_code,201)
        self.assertEqual(mail.outbox[-1].to,['new@example.com'])
        self.assertIn('Verify your email',mail.outbox[-1].subject)

    def test_same_email_requires_matching_username(self):
        self.verified()
        other=get_user_model().objects.create_user(username='another',email=self.user.email,password='Violet!Railway482')
        token=self.request_link('reset')
        self.assertEqual(AccountLink.objects.get().user_id,self.user.id)
        self.assertEqual(self.consume(token,'reset',password='New!OrchidTraveller625',password_confirm='New!OrchidTraveller625').status_code,200)
        other.refresh_from_db()
        self.assertTrue(other.check_password('Violet!Railway482'))


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ConcurrentResetTests(TransactionTestCase):
    def test_two_consumers_only_change_password_once(self):
        from concurrent.futures import ThreadPoolExecutor
        from django.db import close_old_connections
        from .account_links import issue_link
        user=get_user_model().objects.create_user(username='concurrent',email='race@example.com',password='Violet!Railway482')
        AccountEmail.objects.create(user=user,verified_email=user.email)
        raw='single-use-concurrent-test-token'
        with patch('bookings.account_links.secrets.token_urlsafe',return_value=raw):
            issue_link(user,'reset')
        def consume(index):
            close_old_connections()
            try:
                password=f'Concurrent!Orchid625-{index}'
                response=APIClient().post('/api/accounts/reset-password/',{'token':raw,'password':password,'password_confirm':password})
                return response.status_code,index
            finally:
                close_old_connections()
        cache.clear()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(consume,[1,2]))
        self.assertEqual(sorted(code for code,_ in results),[200,400])
        winner=next(index for code,index in results if code==200)
        user.refresh_from_db()
        self.assertTrue(user.check_password(f'Concurrent!Orchid625-{winner}'))
        cache.clear()
