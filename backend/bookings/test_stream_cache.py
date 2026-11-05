from unittest.mock import patch
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings
from .inventory_stream import inventory_events


@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class StreamCacheTests(SimpleTestCase):
    def test_viewers_share_short_lived_public_snapshot(self):
        cache.clear()
        rows = [{'id': 1, 'from_seq': 1, 'to_seq': 5, 'classes': []}]
        streams = [inventory_events([(1, 1, 5)]) for _ in range(2)]
        try:
            with patch('bookings.inventory_stream.inventory_snapshot', return_value=rows) as snapshot, patch('bookings.inventory_stream.close_old_connections'):
                for stream in streams:
                    next(stream)
                    self.assertIn('event: inventory', next(stream))
                self.assertEqual(snapshot.call_count, 1)
        finally:
            with patch('bookings.inventory_stream.close_old_connections'):
                for stream in streams: stream.close()
            cache.clear()
