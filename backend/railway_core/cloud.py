"""Render API/worker + Neon PostgreSQL + Upstash Redis."""
import ssl

import dj_database_url
from .production import *  # noqa: F403

if not os.environ.get('DATABASE_URL', '').startswith(('postgres://', 'postgresql://')):
    raise ImproperlyConfigured('Set DATABASE_URL to the Neon PostgreSQL connection string.')
if not REDIS_URL.startswith('rediss://'):
    raise ImproperlyConfigured('Cloud Redis requires a TLS rediss:// connection string.')

DATABASES = {'default': dj_database_url.parse(
    os.environ['DATABASE_URL'], conn_max_age=60, conn_health_checks=True, ssl_require=True,
)}
DATABASES['default']['DISABLE_SERVER_SIDE_CURSORS'] = True
CELERY_BROKER_USE_SSL = {'ssl_cert_reqs': ssl.CERT_REQUIRED}
CELERY_REDIS_BACKEND_USE_SSL = {'ssl_cert_reqs': ssl.CERT_REQUIRED}
# Reduce idle polling/command consumption on metered Redis.
CELERY_BROKER_TRANSPORT_OPTIONS = {
    'polling_interval': 5, 'visibility_timeout': 3600, 'global_keyprefix': 'railwise:',
}
CELERY_RESULT_BACKEND_TRANSPORT_OPTIONS = {'global_keyprefix': 'railwise:'}
CELERY_WORKER_ENABLE_REMOTE_CONTROL = False
CELERY_WORKER_SEND_TASK_EVENTS = False
CELERY_TASK_IGNORE_RESULT = True
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}
