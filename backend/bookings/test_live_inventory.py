import json
from unittest.mock import patch
from django.test import TransactionTestCase
from rest_framework.exceptions import ValidationError
from . import tests as fixtures
from .models import Booking, Seat
from .services import book_seat,book_group,join_waitlist,cancel_booking,expire_journey,group_members
from .tariffs import price_segment
from .inventory_stream import inventory_events,validate_segments


class LiveInventoryTests(TransactionTestCase):
    def setUp(self):
        fixtures.BookingTests.setUp(self)

    def test_sse_reports_hold_and_cancellation_without_private_details(self):
        segments=[(self.journey.id,1,5)]
        with patch('bookings.inventory_stream.time.sleep'),patch('bookings.inventory_stream.close_old_connections'):
            stream=inventory_events(segments,lifetime=60,interval=0)
            self.assertIn('retry:',next(stream))
            initial=next(stream)
            self.assertIn('"available_seats": 1',initial)
            booking=book_seat(self.user,self.journey.id,self.seat.id,1,5)
            held=next(stream)
            self.assertIn('"available_seats": 0',held)
            self.assertNotIn('passenger',held)
            self.assertNotIn('payment',held)
            cancel_booking(booking.id,self.user)
            self.assertIn('"available_seats": 1',next(stream))
            self.assertIn('heartbeat',next(stream))
            stream.close()

    def test_public_stream_validates_segments_and_sets_nonbuffering_headers(self):
        self.client.force_authenticate(None)
        response=self.client.get('/api/inventory/stream/',{'segments':json.dumps([[self.journey.id,1,5]])},HTTP_ACCEPT='text/event-stream')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response['Content-Type'],'text/event-stream')
        self.assertEqual(response['X-Accel-Buffering'],'no')
        response.close()
        for raw in ['{}','[]','[[true,1,5]]','[[1,5,1]]','[[999999,1,5]]']:
            with self.assertRaises(ValidationError):validate_segments(raw)

    def test_confirmed_only_rejects_waitlist_on_the_server(self):
        book_seat(self.user,self.journey.id,self.seat.id,1,5)
        response=self.client.post('/api/waitlist/',{'journey_id':self.journey.id,'from_seq':1,'to_seq':5,
            'confirmed_berths_only':True},format='json')
        self.assertEqual(response.status_code,400)
        self.assertFalse(Booking.objects.filter(status='WL').exists())

    def test_preferences_are_persisted_for_every_group_member(self):
        other=Seat.objects.create(train=self.train,coach='S1',number=2)
        booking=book_group(self.user,self.journey.id,[self.seat.id,other.id],1,5,
            confirmed_berths_only=True,consider_auto_upgrade=True)
        self.assertTrue(all(b.confirmed_berths_only and b.consider_auto_upgrade for b in group_members(booking)))
        response=self.client.get(f'/api/bookings/{booking.id}/')
        self.assertTrue(response.data['confirmed_berths_only'])
        self.assertTrue(response.data['consider_auto_upgrade'])

    def upgrade_setup(self,opt_in):
        ac=Seat.objects.create(train=self.train,coach='B1',number=1,travel_class='3A')
        book_seat(self.user,self.journey.id,self.seat.id,1,5)
        occupied=book_seat(self.user,self.journey.id,ac.id,1,5)
        waiting=join_waitlist(self.other,self.journey.id,1,5,consider_auto_upgrade=opt_in)
        return ac,occupied,waiting

    def test_no_upgrade_without_consent(self):
        ac,occupied,waiting=self.upgrade_setup(False)
        cancel_booking(occupied.id,self.user)
        waiting.refresh_from_db()
        self.assertEqual(waiting.status,'WL')

    def test_consented_upgrade_keeps_original_fare_and_occupies_actual_class(self):
        ac,occupied,waiting=self.upgrade_setup(True)
        amount=waiting.amount
        cancel_booking(occupied.id,self.user)
        waiting.refresh_from_db()
        self.assertEqual(waiting.status,'PENDING')
        self.assertEqual(waiting.seat_id,ac.id)
        self.assertEqual(waiting.amount,amount)
        self.assertEqual(waiting.travel_class,'SL')
        self.assertEqual(price_segment(self.journey,1,5,'3A')['available_seats'],0)
        self.assertIsNone(waiting.razorpay_payment_id)

    def test_own_class_waitlist_has_priority_over_upgrade(self):
        ac,occupied,waiting=self.upgrade_setup(True)
        native=join_waitlist(self.user,self.journey.id,1,5,'3A')
        cancel_booking(occupied.id,self.user)
        native.refresh_from_db();waiting.refresh_from_db()
        self.assertEqual(native.seat_id,ac.id)
        self.assertEqual(waiting.status,'WL')

    def test_upgrade_is_not_a_downgrade_or_cross_family_change(self):
        ac=Seat.objects.create(train=self.train,coach='B1',number=1,travel_class='3A')
        occupied=book_seat(self.user,self.journey.id,ac.id,1,5)
        waiting=join_waitlist(self.other,self.journey.id,1,5,'3A',consider_auto_upgrade=True)
        Seat.objects.create(train=self.train,coach='C2',number=1,travel_class='CC')
        expire_journey(self.journey.id)
        waiting.refresh_from_db()
        self.assertEqual(waiting.status,'WL')

    def test_preferences_survive_passenger_edits_and_lock_after_checkout(self):
        b=book_seat(self.user,self.journey.id,self.seat.id,1,5,confirmed_berths_only=True,consider_auto_upgrade=True)
        body={'passengers':[{'booking_id':b.id,'name':'Demo Passenger','age':25,'gender':'Male'}],
            'contact_email':'demo@example.invalid','contact_phone':'9999999999'}
        response=self.client.put(f'/api/bookings/{b.id}/passengers/',body,format='json')
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.data['consider_auto_upgrade'])
        b.razorpay_order_id='order_locked';b.save(update_fields=['razorpay_order_id'])
        body['consider_auto_upgrade']=False
        self.assertEqual(self.client.put(f'/api/bookings/{b.id}/passengers/',body,format='json').status_code,400)
        b.refresh_from_db();self.assertTrue(b.consider_auto_upgrade)

    def test_checkout_never_accepts_a_missing_seat(self):
        from .payments import require_checkout_ready
        b=fixtures.BookingTests.hold(self)
        b.seat=None;b.save(update_fields=['seat'])
        with self.assertRaises(ValidationError):require_checkout_ready(b)
