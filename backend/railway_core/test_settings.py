"""Isolated providers for repeatable regression runs; never use for serving."""
from .settings import *  # noqa: F403

EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
CELERY_BROKER_URL = 'memory://'
CELERY_RESULT_BACKEND = 'cache+memory://'
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
if os.environ.get('RAILWISE_TEST_DB_NAME'):
    name = os.environ['RAILWISE_TEST_DB_NAME']
    if not name.startswith('test_'):
        raise ValueError('An isolated test database name must start with test_.')
    DATABASES['default']['TEST'] = {'NAME': name}
