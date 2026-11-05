from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient
from . import tests as fixtures
from .models import Booking, Seat, Train, TrainStop, Journey
from .services import book_seat, book_group, join_waitlist, cancel_booking
from .tariffs import price_segment


class LocalEngineTests(TestCase):
    def setUp(self):
        fixtures.BookingTests.setUp(self)
        self.train.in_catalogue=True
        self.train.save()

    def test_distance_class_and_quota_rules(self):
        for code,total in [('SL','280.00'),('3A','640.00'),('2A','930.00'),('1A','1460.00')]:
            quote=price_segment(self.journey,1,5,code)
            self.assertEqual(quote['total'],total)
            self.assertEqual(quote['distance_km'],400)
        tatkal=price_segment(self.journey,1,5,'SL','TQ')
        self.assertEqual(tatkal['tatkal_surcharge'],'78.00')
        self.assertEqual(tatkal['total'],'358.00')

    def test_dynamic_demand_is_segment_specific_and_group_price_is_frozen(self):
        seats=[self.seat]+[Seat.objects.create(train=self.train,coach='S1',number=n) for n in range(2,6)]
        group=book_group(self.user,self.journey.id,[seat.id for seat in seats[:4]],1,5)
        self.assertEqual(set(Booking.objects.values_list('amount',flat=True)),{Decimal('280.00')})
        quote=price_segment(self.journey,1,5,'SL')
        self.assertEqual(quote['available_seats'],1)
        self.assertEqual(quote['demand_surcharge'],'26.00')
        self.assertEqual(quote['total'],'306.00')
        book_seat(self.other,self.journey.id,seats[4].id,1,5)
        group.refresh_from_db()
        self.assertEqual(group.amount,Decimal('280.00'))
        self.assertEqual(group.fare_details['total'],'280.00')

    def test_adjacent_route_reuses_capacity_without_demand_surcharge(self):
        book_seat(self.user,self.journey.id,self.seat.id,1,3)
        quote=price_segment(self.journey,3,5,'SL')
        self.assertEqual(quote['available_seats'],1)
        self.assertEqual(quote['demand_surcharge'],'0.00')

    def test_class_waitlist_does_not_take_another_class_seat(self):
        ac=Seat.objects.create(train=self.train,coach='B1',number=1,travel_class='3A')
        sleeper=book_seat(self.user,self.journey.id,self.seat.id,1,5)
        waiting=join_waitlist(self.other,self.journey.id,1,5,'SL')
        ac_booking=book_seat(self.user,self.journey.id,ac.id,1,5)
        cancel_booking(ac_booking.id,self.user)
        waiting.refresh_from_db()
        self.assertEqual(waiting.status,'WL')
        cancel_booking(sleeper.id,self.user)
        waiting.refresh_from_db()
        self.assertEqual(waiting.status,'PENDING')
        self.assertEqual(waiting.seat_id,self.seat.id)
        self.assertEqual(waiting.travel_class,'SL')

    def test_mixed_class_group_and_invalid_quota_rejected_atomically(self):
        ac=Seat.objects.create(train=self.train,coach='B1',number=1,travel_class='3A')
        with self.assertRaises(ValidationError):
            book_group(self.user,self.journey.id,[self.seat.id,ac.id],1,5)
        with self.assertRaises(ValidationError):
            book_seat(self.user,self.journey.id,self.seat.id,1,5,'BAD')
        self.assertEqual(Booking.objects.count(),0)

    def test_client_cannot_override_fare_or_class(self):
        response=self.client.post('/api/bookings/',{'journey_id':self.journey.id,'seat_ids':[self.seat.id],
            'from_seq':1,'to_seq':5,'amount':'0.01','travel_class':'1A','quota':'TQ'},format='json')
        self.assertEqual(response.status_code,201)
        self.assertEqual(response.data['amount'],358)
        self.assertEqual(response.data['travel_class'],'SL')
        self.assertEqual(response.data['fare_details']['distance_km'],400)

    def test_local_search_works_without_network_and_respects_running_days(self):
        client=APIClient()
        with patch('requests.sessions.Session.request',side_effect=AssertionError('Network must not be used')):
            response=client.get('/api/trains/search/',{'from':'S1','to':'S5','date':timezone.localdate().isoformat()})
        self.assertEqual(response.status_code,200)
        self.assertEqual(len(response.data['journeys']),1)
        self.assertEqual(response.data['journeys'][0]['classes'][0]['available_seats'],1)
        self.train.run_days=['Never'];self.train.save()
        self.assertEqual(client.get('/api/trains/search/',{'from':'S1','to':'S5','date':timezone.localdate().isoformat()}).data['journeys'],[])

    def test_downstream_boarding_today_can_start_yesterday(self):
        self.journey.date=timezone.localdate()-timedelta(days=1);self.journey.save()
        TrainStop.objects.filter(train=self.train,sequence__gte=3).update(day=2)
        booking=book_seat(self.user,self.journey.id,self.seat.id,3,5)
        self.assertEqual(booking.status,'PENDING')

    def test_expired_holds_are_reconciled_before_quote(self):
        booking=book_seat(self.user,self.journey.id,self.seat.id,1,5)
        Booking.objects.filter(pk=booking.id).update(expires_at=timezone.now()-timedelta(seconds=1))
        response=self.client.get(f'/api/journeys/{self.journey.id}/quote/',{'from':1,'to':5,'travel_class':'SL'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.data['available_seats'],1)
        self.assertEqual(response.data['demand_surcharge'],'0.00')

    def test_static_catalogue_seed_is_repeatable_and_names_resolve_offline(self):
        with patch('requests.sessions.Session.request',side_effect=AssertionError('Network must not be used')):
            call_command('seed_data',verbosity=0)
            first=(Train.objects.count(),Seat.objects.count(),TrainStop.objects.count())
            call_command('seed_data',verbosity=0)
            self.assertEqual(first,(Train.objects.count(),Seat.objects.count(),TrainStop.objects.count()))
            client=APIClient()
            for name,code in [('Patna','PNBE'),('Kolkata','KOAA'),('Howrah','HWH')]:
                rows=client.get('/api/stations/search/',{'q':name}).data['stations']
                self.assertTrue(any(row['code']==code for row in rows))
                self.assertFalse(any(row['code']=='CP' for row in rows))

    def test_live_provider_features_have_been_removed(self):
        self.assertEqual(self.client.get('/api/trains/15017/live/').status_code,404)
        self.assertEqual(self.client.get('/api/trains/12004/fares/').status_code,404)

    def test_seed_replaces_only_unbooked_legacy_reference(self):
        legacy=Train.objects.create(number='22436',name='Legacy reference')
        TrainStop.objects.create(train=legacy,station=self.train.stops.first().station,sequence=1)
        Seat.objects.create(train=legacy,coach='C1',number=1)
        call_command('seed_data',verbosity=0)
        legacy.refresh_from_db()
        self.assertTrue(legacy.in_catalogue)
        self.assertTrue(legacy.stops.count()>1)
        self.assertEqual(set(legacy.seats.values_list('travel_class',flat=True)),{'CC','EC'})

    def test_seed_keeps_conflicting_booked_route_and_imports_other_services(self):
        legacy=Train.objects.create(number='22436',name='Booked reference')
        stop=TrainStop.objects.create(train=legacy,station=self.train.stops.first().station,sequence=1)
        journey=Journey.objects.create(train=legacy,date=timezone.localdate())
        seat=Seat.objects.create(train=legacy,coach='C1',number=1)
        booking=Booking.objects.create(user=self.user,journey=journey,seat=seat,from_seq=1,to_seq=2,status='CONFIRMED')
        call_command('seed_data',verbosity=0)
        self.assertEqual(list(legacy.stops.values_list('id',flat=True)),[stop.id])
        self.assertTrue(Booking.objects.filter(pk=booking.id,seat=seat).exists())
        self.assertTrue(Train.objects.filter(number='22348',in_catalogue=True).exists())
