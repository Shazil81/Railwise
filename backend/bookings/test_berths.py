from concurrent.futures import ThreadPoolExecutor
from django.db import close_old_connections
from django.test import TransactionTestCase
from rest_framework.exceptions import ValidationError
from . import tests as fixtures
from .models import Booking,Seat
from .services import book_seat,book_group,save_passengers,group_members
from .berths import inferred_berth


class BerthPreferenceTests(TransactionTestCase):
    def setUp(self):fixtures.BookingTests.setUp(self)

    def new_seat(self,number,code='SL'):
        return Seat.objects.create(train=self.train,coach='C1' if code=='SL' else 'A1',number=number,travel_class=code)

    def details(self,b,preferences):
        return {'passengers':[{'booking_id':member.id,'name':f'Demo Passenger','age':25,'gender':'Male','berth_preference':preference}
            for member,preference in zip(group_members(b),preferences)],'contact_email':'demo@example.invalid','contact_phone':'9999999999'}

    def test_layouts_and_explicit_overrides(self):
        self.assertEqual([inferred_berth('SL',i) for i in range(1,9)],['LB','MB','UB','LB','MB','UB','SL','SU'])
        self.assertEqual(inferred_berth('2A',6),'SU')
        self.assertEqual(inferred_berth('CC',1),'NA')
        self.seat.berth_type='UB';self.seat.save()
        self.assertEqual(self.seat.allocated_berth,'UB')

    def test_matching_berth_is_allocated_without_changing_fare_or_expiry(self):
        upper=self.new_seat(3)
        b=book_seat(self.user,self.journey.id,upper.id,1,5)
        amount,expiry=b.amount,b.expires_at
        response=self.client.put(f'/api/bookings/{b.id}/passengers/',self.details(b,['LB']),format='json')
        self.assertEqual(response.status_code,200)
        passenger=response.data['passengers'][0]
        self.assertEqual(passenger['allocated_berth'],'LB')
        self.assertTrue(passenger['berth_preference_met'])
        b.refresh_from_db()
        self.assertEqual(b.seat_id,self.seat.id)
        self.assertEqual((b.amount,b.expires_at),(amount,expiry))

    def test_group_can_swap_held_seats_atomically(self):
        upper=self.new_seat(3)
        b=book_group(self.user,self.journey.id,[self.seat.id,upper.id],1,5)
        save_passengers(b.id,self.user,self.details(b,['UB','LB']))
        members=list(group_members(b))
        self.assertEqual([m.seat_id for m in members],[upper.id,self.seat.id])
        self.assertEqual(len({m.seat_id for m in members}),2)

    def test_no_preference_does_not_take_only_requested_lower_berth(self):
        upper=self.new_seat(3)
        b=book_group(self.user,self.journey.id,[self.seat.id,upper.id],1,5)
        save_passengers(b.id,self.user,self.details(b,['ANY','LB']))
        members=list(group_members(b))
        self.assertEqual(members[1].seat_id,self.seat.id)

    def test_occupied_preference_has_clear_fallback(self):
        book_seat(self.other,self.journey.id,self.seat.id,1,5)
        upper=self.new_seat(3)
        b=book_seat(self.user,self.journey.id,upper.id,1,5)
        response=self.client.put(f'/api/bookings/{b.id}/passengers/',self.details(b,['LB']),format='json')
        self.assertEqual(response.status_code,200)
        passenger=response.data['passengers'][0]
        self.assertEqual(passenger['allocated_berth'],'UB')
        self.assertFalse(passenger['berth_preference_met'])

    def test_adjacent_segments_can_reuse_preferred_berth(self):
        book_seat(self.other,self.journey.id,self.seat.id,1,3)
        upper=self.new_seat(3)
        b=book_seat(self.user,self.journey.id,upper.id,3,5)
        save_passengers(b.id,self.user,self.details(b,['LB']))
        b.refresh_from_db();self.assertEqual(b.seat_id,self.seat.id)

    def test_unsupported_preference_rolls_back_all_group_changes(self):
        lower=self.new_seat(1,'2A');upper=self.new_seat(2,'2A')
        b=book_group(self.user,self.journey.id,[lower.id,upper.id],1,5)
        with self.assertRaises(ValidationError):save_passengers(b.id,self.user,self.details(b,['LB','MB']))
        self.assertEqual(list(group_members(b).values_list('seat_id',flat=True)),[lower.id,upper.id])
        self.assertFalse(group_members(b).exclude(passenger_name='').exists())

    def test_checkout_started_locks_berth_changes(self):
        b=book_seat(self.user,self.journey.id,self.seat.id,1,5)
        b.razorpay_order_id='order_berth_locked';b.save()
        self.assertEqual(self.client.put(f'/api/bookings/{b.id}/passengers/',self.details(b,['UB']),format='json').status_code,400)
        b.refresh_from_db();self.assertEqual(b.berth_preference,'ANY')

    def test_competing_preferences_cannot_get_the_same_lower_berth(self):
        upper1=self.new_seat(3);upper2=self.new_seat(6)
        first=book_seat(self.user,self.journey.id,upper1.id,1,5)
        second=book_seat(self.other,self.journey.id,upper2.id,1,5)
        payloads=[(first.id,self.user,self.details(first,['LB'])),(second.id,self.other,self.details(second,['LB']))]
        def allocate(payload):
            close_old_connections()
            try:
                bid,user,body=payload
                return save_passengers(bid,user,body).seat_id
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:assigned=list(pool.map(allocate,payloads))
        self.assertEqual(len(set(assigned)),2)
        self.assertEqual(assigned.count(self.seat.id),1)

    def test_invalid_preference_is_rejected_by_serializer(self):
        b=book_seat(self.user,self.journey.id,self.seat.id,1,5)
        self.assertEqual(self.client.put(f'/api/bookings/{b.id}/passengers/',self.details(b,['INVALID']),format='json').status_code,400)
