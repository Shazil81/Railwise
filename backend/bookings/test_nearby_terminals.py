from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from .models import Booking, Journey, Seat, Station, Train, TrainStop


class NearbyTerminalTests(TestCase):
    def setUp(self):
        self.client=APIClient()
        self.day=timezone.localdate()+timedelta(days=1)
        self.stations={code:Station.objects.create(code=code,name=name) for code,name in [
            ('PNBE','Patna Jn'),('RJPB','Rajendra Nagar'),('PPTA','Patliputra'),
            ('HWH','Howrah'),('KOAA','Kolkata'),('SDAH','Sealdah')]}
        self.train('EXACT',[('PNBE',1),('RJPB',1),('HWH',1)])
        self.train('OTHER',[('RJPB',1),('KOAA',2)])
        downstream=self.train('DAYTWO',[('PPTA',1),('PNBE',2),('SDAH',2)])
        downstream.run_days=[('Mon','Tue','Wed','Thu','Fri','Sat','Sun')[(self.day-timedelta(days=1)).weekday()]]
        downstream.save()
        self.network=patch('requests.sessions.Session.request',side_effect=AssertionError('Nearby search must stay offline'))
        self.network.start();self.addCleanup(self.network.stop)

    def train(self,number,stops):
        train=Train.objects.create(number=number,name=number,in_catalogue=True)
        for sequence,(code,day) in enumerate(stops,1):
            TrainStop.objects.create(train=train,station=self.stations[code],sequence=sequence,
                distance_km=(sequence-1)*100,day=day,arrival='12:00',departure='12:05')
        Seat.objects.create(train=train,coach='S1',number=1)
        return train

    def search(self,origin='PNBE',destination='HWH',**extra):
        return self.client.get('/api/trains/search/',{'from':origin,'to':destination,'date':self.day.isoformat(),**extra})

    def test_exact_search_remains_available_explicitly(self):
        response=self.search(include_nearby='false')
        self.assertEqual(response.status_code,200)
        self.assertEqual([row['number'] for row in response.data['journeys']],['EXACT'])
        self.assertFalse(response.data['include_nearby'])

    def test_station_code_search_expands_both_ends_by_default(self):
        response=self.search()
        self.assertTrue(response.data['include_nearby'])
        self.assertEqual({row['number'] for row in response.data['journeys']},{'EXACT','OTHER','DAYTWO'})

    def test_city_names_expand_terminals_without_duplicate_train_cards(self):
        response=self.search('Patna','Kolkata',include_nearby='true')
        self.assertEqual(response.status_code,200)
        rows=response.data['journeys']
        self.assertEqual({row['number'] for row in rows},{'EXACT','OTHER','DAYTWO'})
        self.assertEqual(len(rows),len({row['number'] for row in rows}))
        self.assertEqual({s['code'] for s in response.data['from_stations']},{'PNBE','RJPB','PPTA'})
        other=next(row for row in rows if row['number']=='OTHER')
        self.assertEqual((other['origin_code'],other['destination_code']),('RJPB','KOAA'))
        self.assertTrue(other['nearby_match'])

    def test_selected_station_has_priority_and_nearby_is_explicit(self):
        rows=self.search('RJPB','HWH',include_nearby='1').data['journeys']
        exact=next(row for row in rows if row['number']=='EXACT')
        self.assertEqual(exact['origin_code'],'RJPB')
        self.assertFalse(exact['nearby_match'])
        self.assertEqual(exact['classes'][0]['distance_km'],100)

    def test_downstream_boarding_uses_its_own_origin_date(self):
        rows=self.search('Patna','Kolkata',include_nearby='true').data['journeys']
        row=next(row for row in rows if row['number']=='DAYTWO')
        self.assertEqual(row['origin_code'],'PNBE')
        self.assertEqual(row['boarding_date'],self.day.isoformat())
        self.assertEqual(Journey.objects.get(pk=row['id']).date,self.day-timedelta(days=1))

    def test_booking_uses_actual_terminal_segment_and_fare(self):
        row=next(row for row in self.search(include_nearby='true').data['journeys'] if row['number']=='OTHER')
        user=get_user_model().objects.create_user('nearby-test')
        self.client.force_authenticate(user)
        from_seq=next(s['sequence'] for s in row['stops'] if s['code']==row['origin_code'])
        to_seq=next(s['sequence'] for s in row['stops'] if s['code']==row['destination_code'])
        seat=Seat.objects.get(train__number='OTHER')
        response=self.client.post('/api/bookings/',{'journey_id':row['id'],'seat_ids':[seat.id],
            'from_seq':from_seq,'to_seq':to_seq},format='json')
        self.assertEqual(response.status_code,201)
        booking=Booking.objects.get(pk=response.data['booking_id'])
        self.assertEqual(booking.boarding_date,self.day)
        self.assertEqual(str(booking.amount),row['classes'][0]['total'])
        self.assertEqual(response.data['origin'],'Rajendra Nagar')
        self.assertEqual(response.data['destination'],'Kolkata')

    def test_invalid_or_same_city_groups_are_rejected(self):
        for origin,destination,flag in [('Patna','Kolkata','false'),('Unknown','HWH','true'),('PNBE','RJPB','true'),('PNBE','HWH','yes')]:
            self.assertEqual(self.search(origin,destination,include_nearby=flag).status_code,400)

    def test_special_validity_is_retained_when_expanding_groups(self):
        Train.objects.filter(number='OTHER').update(valid_until=timezone.localdate()-timedelta(days=1))
        rows=self.search('Patna','Kolkata',include_nearby='true').data['journeys']
        self.assertNotIn('OTHER',{row['number'] for row in rows})

    def test_autocomplete_exposes_local_city_groups_and_aliases(self):
        for query in ['Patna','PNBE']:
            response=self.client.get('/api/stations/search/',{'q':query})
            self.assertEqual(response.data['terminal_group']['name'],'Patna')
            self.assertIn('RJPB',response.data['terminal_group']['codes'])
            self.assertEqual(response.data['is_city'],query=='Patna')
