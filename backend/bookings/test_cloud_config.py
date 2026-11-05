"""Cloud configuration must not silently fall back to local services."""
import os
import subprocess
import sys
from pathlib import Path
from django.test import SimpleTestCase


class CloudConfigTests(SimpleTestCase):
    def run_config(self, **overrides):
        env = {**os.environ, 'SECRET_KEY': 'test-only-' * 8,
               'ALLOWED_HOSTS': 'railwise-api.onrender.com',
               'FRONTEND_URL': 'https://railwise.vercel.app',
               'DATABASE_URL': 'postgresql://test:password@db.example.invalid/neondb?sslmode=require',
               'REDIS_URL': 'rediss://default:password@redis.example.invalid:6379/0', **overrides}
        return subprocess.run([sys.executable, '-c',
            'from railway_core import cloud as c; '
            'assert c.DATABASES["default"]["OPTIONS"]["sslmode"] == "require"; '
            'assert c.DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"]; '
            'assert c.CELERY_BROKER_USE_SSL["ssl_cert_reqs"] == 2; '
            'assert c.CELERY_BROKER_TRANSPORT_OPTIONS["global_keyprefix"] == "railwise:"; '
            'assert c.CELERY_RESULT_BACKEND_TRANSPORT_OPTIONS["global_keyprefix"] == "railwise:"; '
            'assert c.CORS_ALLOWED_ORIGINS == ["https://railwise.vercel.app"]'],
            env=env, cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)

    def test_secure_cloud_configuration(self):
        result = self.run_config()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_database_is_rejected(self):
        self.assertNotEqual(self.run_config(DATABASE_URL='').returncode, 0)

    def test_plaintext_redis_is_rejected(self):
        self.assertNotEqual(self.run_config(REDIS_URL='redis://localhost:6379/0').returncode, 0)
