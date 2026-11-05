"""PC-hosted background jobs: Neon records, private Docker Redis broker."""
from .cloud import *  # noqa: F403

# Jobs are picked from durable Neon rows by beat; the HTTP API does not enqueue them.
CELERY_BROKER_URL = 'redis://redis:6379/0'
CELERY_RESULT_BACKEND = 'redis://redis:6379/1'
CELERY_BROKER_USE_SSL = None
CELERY_REDIS_BACKEND_USE_SSL = None
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
