"""Reproducible contention benchmark against an isolated PostgreSQL test DB."""
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from django.db import close_old_connections
from django.test import TransactionTestCase
from . import tests as fixtures
from .models import Booking
from .services import SeatTaken


class ContentionBenchmark(TransactionTestCase):
    setUp = fixtures.BookingTests.setUp
    hold = fixtures.BookingTests.hold

    def test_one_seat_under_contention(self):
        def attempt(_):
            close_old_connections()
            started = time.perf_counter()
            try:
                self.hold()
                outcome = 'won'
            except SeatTaken:
                outcome = 'taken'
            finally:
                close_old_connections()
            return outcome, (time.perf_counter()-started)*1000
        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=10) as pool:
            results = list(pool.map(attempt, range(100)))
        elapsed = time.perf_counter()-started
        latencies = sorted(value for _, value in results)
        winners = sum(outcome == 'won' for outcome, _ in results)
        self.assertEqual(winners, 1)
        self.assertEqual(Booking.objects.filter(status='PENDING').count(), 1)
        report = dict(attempts=100, threads=10, winners=winners, conflicts=100-winners,
                      elapsed_seconds=round(elapsed, 3), attempts_per_second=round(100/elapsed, 2),
                      p50_ms=round(latencies[49], 2), p95_ms=round(latencies[94], 2),
                      scope='Local service calls with DB connections; not HTTP throughput')
        destination = os.environ.get('RAILWISE_BENCHMARK_REPORT')
        if destination:
            Path(destination).write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
        print('Contention benchmark:', json.dumps(report))
