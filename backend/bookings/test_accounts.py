from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token


class AccountTests(TestCase):
    def tearDown(self):
        cache.clear()

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.payload = dict(username='newtraveller', email='traveller@example.com',
            password='Violet!Railway482', password_confirm='Violet!Railway482')

    def test_signup_hashes_password_and_authenticates(self):
        response = self.client.post('/api/accounts/signup/', self.payload)
        self.assertEqual(response.status_code, 201)
        user = get_user_model().objects.get(username='newtraveller')
        self.assertTrue(user.check_password(self.payload['password']))
        self.assertNotEqual(user.password, self.payload['password'])
        self.assertFalse(user.is_staff)
        self.assertNotIn('password', response.data)
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.client.credentials(HTTP_AUTHORIZATION='Token '+response.data['token'])
        self.assertEqual(self.client.get('/api/bookings/').status_code, 200)

    def test_validation_leaves_no_partial_accounts(self):
        for changes in [dict(password='12345678', password_confirm='12345678'),
                dict(password_confirm='different'), dict(email='invalid'), dict(username='bad name')]:
            response = self.client.post('/api/accounts/signup/', self.payload | changes)
            self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(get_user_model().objects.count(), 0)

    def test_duplicate_and_privilege_fields(self):
        self.client.post('/api/accounts/signup/', self.payload | dict(is_staff=True, is_superuser=True))
        user = get_user_model().objects.get()
        self.assertFalse(user.is_staff or user.is_superuser)
        self.assertEqual(self.client.post('/api/accounts/signup/', self.payload).status_code, 400)
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_logout_revokes_token_and_login_issues_new_one(self):
        token = self.client.post('/api/accounts/signup/', self.payload).data['token']
        self.client.credentials(HTTP_AUTHORIZATION='Token '+token)
        self.assertEqual(self.client.post('/api/accounts/logout/').status_code, 204)
        self.assertFalse(Token.objects.filter(key=token).exists())
        self.assertEqual(self.client.get('/api/bookings/').status_code, 401)
        response = self.client.post('/api/token/', dict(username=self.payload['username'], password=self.payload['password']))
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.data['token'], token)

    def test_inactive_user_cannot_login(self):
        user = get_user_model().objects.create_user(username='inactive', password=self.payload['password'], is_active=False)
        response = self.client.post('/api/token/', dict(username=user.username, password=self.payload['password']))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Token.objects.count(), 0)

    def test_login_rate_limit(self):
        for _ in range(10):
            self.assertEqual(self.client.post('/api/token/', dict(username='missing', password='incorrect')).status_code, 400)
        response = self.client.post('/api/token/', dict(username='missing', password='incorrect'))
        self.assertEqual(response.status_code, 429)
        self.assertIn('Retry-After', response)

    def test_signup_rate_limit_and_anonymous_logout(self):
        for _ in range(5):
            self.assertEqual(self.client.post('/api/accounts/signup/', {}).status_code, 400)
        self.assertEqual(self.client.post('/api/accounts/signup/', {}).status_code, 429)
        self.assertEqual(self.client.post('/api/accounts/logout/').status_code, 401)
