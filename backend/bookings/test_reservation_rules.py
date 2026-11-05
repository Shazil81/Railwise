from datetime import datetime, timedelta
from unittest.mock import patch
from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from . import tests as fixtures
from .models import Booking, BookingEmail
from .rules import IST, require_booking_open
from .services import book_seat, join_waitlist, cancel_booking, expire_journey
from .payments import require_payable


class ReservationRulesTests(TestCase):
    def setUp(self):
        fixtures.BookingTests.setUp(self)
        self.journey.date = datetime(2030, 1, 3).date()
        self.journey.save()
        self.train.stops.filter(sequence=1).update(departure='12:00')
        self.clock = patch('django.utils.timezone.now', return_value=datetime(2030, 1, 2, 9, 59, tzinfo=IST))
        self.clock.start()
        self.addCleanup(self.clock.stop)

    def test_tatkal_class_boundaries(self):
        for code, hour in [('SL', 11), ('3A', 10), ('CC', 10)]:
            with patch('django.utils.timezone.now', return_value=datetime(2030,1,2,hour-1,59,tzinfo=IST)):
                with self.assertRaises(ValidationError):
                    require_booking_open(self.journey,1,code,'TQ')
            with patch('django.utils.timezone.now', return_value=datetime(2030,1,2,hour,0,tzinfo=IST)):
                require_booking_open(self.journey,1,code,'TQ')

    def test_departure_closes_booking_payment_and_cancellation(self):
        booking = book_seat(self.user,self.journey.id,self.seat.id,1,5)
        with patch('django.utils.timezone.now', return_value=datetime(2030,1,3,12,0,tzinfo=IST)):
            for action in [lambda: book_seat(self.other,self.journey.id,self.seat.id,1,5),
                           lambda: require_payable(booking), lambda: cancel_booking(booking.id,self.user)]:
                with self.assertRaises(ValidationError):
                    action()

    def test_downstream_day_and_origin_tatkal_opening(self):
        self.train.stops.filter(sequence=2).update(day=2,departure='01:00')
        with patch('django.utils.timezone.now', return_value=datetime(2030,1,3,23,0,tzinfo=IST)):
            require_booking_open(self.journey,2,'SL','TQ')
        with patch('django.utils.timezone.now', return_value=datetime(2030,1,4,1,0,tzinfo=IST)):
            with self.assertRaises(ValidationError):
                require_booking_open(self.journey,2)

    def test_promotion_email_and_expiry_releases_to_next_passenger(self):
        first = book_seat(self.user,self.journey.id,self.seat.id,1,5)
        waiting = join_waitlist(self.other,self.journey.id,1,5)
        cancel_booking(first.id,self.user)
        waiting.refresh_from_db()
        self.assertEqual(waiting.status,'PENDING')
        self.assertTrue(BookingEmail.objects.filter(booking=waiting,kind='PROMOTED').exists())
        self.assertFalse(waiting.razorpay_payment_id)
        next_waiting = join_waitlist(self.user,self.journey.id,1,5)
        Booking.objects.filter(pk=waiting.pk).update(expires_at=timezone.now()-timedelta(seconds=1))
        expire_journey(self.journey.id)
        waiting.refresh_from_db(); next_waiting.refresh_from_db()
        self.assertEqual(waiting.status,'EXPIRED')
        self.assertEqual(next_waiting.status,'PENDING')

    def test_no_promotion_after_departure(self):
        first = book_seat(self.user,self.journey.id,self.seat.id,1,5)
        waiting = join_waitlist(self.other,self.journey.id,1,5)
        with patch('django.utils.timezone.now', return_value=datetime(2030,1,3,12,0,tzinfo=IST)):
            expire_journey(self.journey.id)
        waiting.refresh_from_db()
        self.assertEqual(waiting.status,'EXPIRED')

    def test_direct_booking_cannot_bypass_sixty_day_limit(self):
        self.journey.date += timedelta(days=61)
        self.journey.save()
        with self.assertRaises(ValidationError):
            book_seat(self.user,self.journey.id,self.seat.id,1,5)

    def test_hold_is_capped_at_boarding_departure(self):
        with patch('django.utils.timezone.now', return_value=datetime(2030,1,3,11,58,tzinfo=IST)):
            booking = book_seat(self.user,self.journey.id,self.seat.id,1,5)
        self.assertEqual(booking.expires_at, datetime(2030,1,3,12,0,tzinfo=IST))

    def test_sweep_expires_waitlist_even_without_an_expired_hold(self):
        from .tasks import sweep_expired_holds
        first = book_seat(self.user,self.journey.id,self.seat.id,1,5)
        waiting = join_waitlist(self.other,self.journey.id,1,5)
        Booking.objects.filter(pk=first.pk).update(status='CONFIRMED',expires_at=None)
        with patch('django.utils.timezone.now', return_value=datetime(2030,1,3,12,0,tzinfo=IST)):
            sweep_expired_holds()
        waiting.refresh_from_db()
        self.assertEqual(waiting.status,'EXPIRED')

    def test_email_worker_also_sweeps_holds_without_gateway_calls(self):
        from .tasks import send_booking_notifications
        with patch('bookings.tasks.sweep_expired_holds') as sweep, patch('bookings.notifications.dispatch_booking_emails',return_value={'sent':0}), patch('bookings.payments.payment_client',side_effect=AssertionError('No gateway call')):
            send_booking_notifications()
        sweep.assert_called_once_with()
