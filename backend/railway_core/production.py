"""Same-origin deployment settings. Supply secrets through the service environment."""
from .settings import *  # noqa: F403
from django.core.exceptions import ImproperlyConfigured

DEBUG = False
if SECRET_KEY == 'local-development-only-change-before-deployment' or len(SECRET_KEY) < 50:
    raise ImproperlyConfigured('Production requires a random SECRET_KEY of at least 50 characters.')
if not os.environ.get('ALLOWED_HOSTS') or '*' in ALLOWED_HOSTS:
    raise ImproperlyConfigured('Set explicit production ALLOWED_HOSTS.')
if not os.environ.get('FRONTEND_URL', '').startswith('https://'):
    raise ImproperlyConfigured('Set an HTTPS FRONTEND_URL.')
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
CSRF_TRUSTED_ORIGINS = [os.environ['FRONTEND_URL'].rstrip('/')]
CORS_ALLOWED_ORIGINS = CSRF_TRUSTED_ORIGINS
CACHES = {'default': {
    'BACKEND': 'django.core.cache.backends.redis.RedisCache',
    'LOCATION': os.environ.get('REDIS_CACHE_URL', REDIS_URL),
    'KEY_PREFIX': 'railwise-production',
}}
