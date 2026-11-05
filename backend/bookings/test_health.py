from unittest.mock import patch
from django.db import OperationalError
from django.test import TestCase


class HealthTests(TestCase):
    def test_public_health_checks_database(self):
        response = self.client.get('/api/health/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})

    def test_failure_does_not_expose_connection_details(self):
        with patch('railway_core.health.connection.cursor', side_effect=OperationalError('private database details')):
            response = self.client.get('/api/health/')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {'status': 'unavailable'})
