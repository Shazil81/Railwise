import json
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from .models import Train, Station, Seat, TrainStop, Journey
from .services import book_seat


class CatalogueCoverageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.catalogue=json.loads((Path(__file__).parent/'data'/'route_catalogue.json').read_text(encoding='utf8'))
        with patch('requests.sessions.Session.request',side_effect=AssertionError('Catalogue seeding must stay offline')):
            call_command('seed_data',verbosity=0)

    def test_snapshots_are_unique_ordered_and_all_seeded(self):
        rows=self.catalogue['trains']
        self.assertGreaterEqual(len(rows),112)
        self.assertEqual(len({row['train_no'] for row in rows}),len(rows))
        self.assertEqual(Train.objects.filter(in_catalogue=True).count(),len(rows))
        self.assertEqual(TrainStop.objects.count(),sum(len(row['route']) for row in rows))
        self.assertGreaterEqual(Station.objects.count(),486)
        for train in rows:
            if train.get('valid_from') or train.get('valid_until'):
                self.assertLessEqual(date.fromisoformat(train['valid_from']),date.fromisoformat(train['valid_until']))
            distances=[int(stop['distance_km']) for stop in train['route']]
            days=[int(stop['day']) for stop in train['route']]
            self.assertEqual(distances,sorted(set(distances)))
            self.assertEqual(days,sorted(days))
            self.assertEqual(len({stop['station_code'] for stop in train['route']}),len(distances))

    def test_all_reviewed_patna_howrah_services_appear_on_correct_boarding_days_offline(self):
        manifest=json.loads((Path(__file__).parent/'data'/'route_coverage.json').read_text())
        required=set(manifest['corridors'][0]['train_numbers'])
        direct={}
        for train in self.catalogue['trains']:
            codes=[stop['station_code'] for stop in train['route']]
            if 'PNBE' in codes and 'HWH' in codes and codes.index('PNBE')<codes.index('HWH'):
                direct[train['train_no']]=train
        self.assertTrue(required.issubset(direct))
        weekdays=('Mon','Tue','Wed','Thu','Fri','Sat','Sun')
        client=APIClient()
        seen=set()
        with patch('requests.sessions.Session.request',side_effect=AssertionError('No runtime railway calls')):
            for offset in range(1,8):
                boarding=timezone.localdate()+timedelta(days=offset)
                expected=set()
                for number,train in direct.items():
                    origin=boarding-timedelta(days=int(next(s['day'] for s in train['route'] if s['station_code']=='PNBE'))-1)
                    if train.get('valid_from') and origin<date.fromisoformat(train['valid_from']):continue
                    if train.get('valid_until') and origin>date.fromisoformat(train['valid_until']):continue
                    if weekdays[origin.weekday()] in train['runs_on']:expected.add(number)
                response=client.get('/api/trains/search/',{'include_nearby':'false','from':'PNBE','to':'HWH','date':boarding.isoformat()})
                self.assertEqual(response.status_code,200)
                actual={train['number'] for train in response.data['journeys']}
                self.assertEqual(actual,expected)
                self.assertGreaterEqual(len(actual),3)
                self.assertNotIn('12352',actual)  # Rajendra Nagar is a separate station.
                self.assertNotIn('13128',actual)  # Kolkata terminal is not Howrah.
                seen.update(actual)
        self.assertTrue(required.issubset(seen))

    def test_special_trains_obey_origin_validity_even_for_day_two_boarding(self):
        from rest_framework.exceptions import ValidationError
        from .rules import require_booking_open
        weekdays=('Mon','Tue','Wed','Thu','Fri','Sat','Sun')
        client=APIClient()
        for entry in self.catalogue['trains']:
            if not entry.get('valid_until'):continue
            train=Train.objects.get(number=entry['train_no'])
            start=date.fromisoformat(entry['valid_from']);end=date.fromisoformat(entry['valid_until'])
            boarding_offset=int(next(stop['day'] for stop in entry['route'] if stop['station_code']=='PNBE'))-1
            cases=[(start-timedelta(days=n),False) for n in range(1,8)]
            cases += [(start+timedelta(days=n),True) for n in range(7)]
            cases += [(end+timedelta(days=n),False) for n in range(1,8)]
            checked=set()
            for origin,expected in cases:
                category='inside' if expected else 'before' if origin<start else 'after'
                if category in checked or weekdays[origin.weekday()] not in entry['runs_on']:continue
                checked.add(category)
                boarding=origin+timedelta(days=boarding_offset)
                with patch('django.utils.timezone.localdate',return_value=boarding), patch('requests.sessions.Session.request',side_effect=AssertionError('Search must stay offline')):
                    response=client.get('/api/trains/search/',{'include_nearby':'false','from':'PNBE','to':'HWH','date':boarding.isoformat()})
                self.assertEqual(response.status_code,200)
                self.assertEqual(entry['train_no'] in {row['number'] for row in response.data['journeys']},expected,(entry['train_no'],category))
                if not expected:
                    journey,_=Journey.objects.get_or_create(train=train,date=origin)
                    with self.assertRaisesMessage(ValidationError,'does not operate'):
                        require_booking_open(journey,1)
            self.assertEqual(checked,{'before','inside','after'})

    def test_major_corridors_offer_multiple_local_services(self):
        client=APIClient()
        with patch('requests.sessions.Session.request',side_effect=AssertionError('No runtime railway calls')):
            for origin,destination in [('NDLS','HWH'),('HWH','NDLS'),('SBC','MAS'),('MAS','SBC'),('PNBE','NDLS')]:
                seen=set()
                for offset in range(1,8):
                    day=timezone.localdate()+timedelta(days=offset)
                    response=client.get('/api/trains/search/',{'include_nearby':'false','from':origin,'to':destination,'date':day.isoformat()})
                    self.assertEqual(response.status_code,200)
                    seen.update(train['number'] for train in response.data['journeys'])
                self.assertGreaterEqual(len(seen),2,(origin,destination))

    def test_regional_and_reverse_searches_use_only_database(self):
        pairs=[('MMCT','NDLS'),('NDLS','MMCT'),('SBIB','NDLS'),('HYB','NDLS'),('SBC','NDLS'),
            ('MAS','SBC'),('SBC','MAS'),('CSMT','PUNE'),('PUNE','CSMT'),('CSMT','HWH'),
            ('HWH','CSMT'),('TVC','NDLS'),('ANVT','KYQ'),('KYQ','ANVT'),('ASR','BDTS'),('PURI','ANVT')]
        client=APIClient()
        weekdays=('Mon','Tue','Wed','Thu','Fri','Sat','Sun')
        with patch('requests.sessions.Session.request',side_effect=AssertionError('Search must stay offline')):
            for origin,destination in pairs:
                train=next(row for row in self.catalogue['trains'] if origin in [s['station_code'] for s in row['route']]
                    and destination in [s['station_code'] for s in row['route']]
                    and [s['station_code'] for s in row['route']].index(origin)<[s['station_code'] for s in row['route']].index(destination))
                boarding_day=int(next(s for s in train['route'] if s['station_code']==origin)['day'])
                travel=next(timezone.localdate()+timedelta(days=offset) for offset in range(7)
                    if weekdays[(timezone.localdate()+timedelta(days=offset-boarding_day+1)).weekday()] in train['runs_on'])
                response=client.get('/api/trains/search/',{'include_nearby':'false','from':origin,'to':destination,'date':travel.isoformat()})
                self.assertEqual(response.status_code,200,(origin,destination))
                self.assertIn(train['train_no'],[row['number'] for row in response.data['journeys']],(origin,destination))
                for service in response.data['journeys']:
                    self.assertTrue(service['classes'])
                    self.assertTrue(all(quote['available_seats']==12 for quote in service['classes']))

    def test_city_aliases_surface_served_terminals_without_redirecting(self):
        client=APIClient()
        with patch('requests.sessions.Session.request',side_effect=AssertionError('Autocomplete must stay offline')):
            for query,expected in [('Mumbai','CSMT'),('Bangalore','SBC'),('Bengaluru','SMVB'),
                ('Chennai','MAS'),('Hyderabad','HYB'),('Ahmedabad','SBIB'),('Guwahati','KYQ'),('Trivandrum','TVC')]:
                response=client.get('/api/stations/search/',{'q':query})
                self.assertEqual(response.status_code,200)
                self.assertIn(expected,[row['code'] for row in response.data['stations']],query)
            self.assertTrue(client.get('/api/stations/search/',{'q':'Mumbai'}).data['requires_selection'])
            self.assertFalse(client.get('/api/stations/search/',{'q':'MMCT'}).data['requires_selection'])

    def test_repeat_seed_does_not_reset_inventory_or_bookings(self):
        train=Train.objects.get(number='12951')
        journey=Journey.objects.create(train=train,date=timezone.localdate()+timedelta(days=1))
        seat=train.seats.first()
        user=get_user_model().objects.create_user('catalogue-test-user')
        booking=book_seat(user,journey.id,seat.id,1,2)
        counts=(Train.objects.count(),Station.objects.count(),TrainStop.objects.count(),Seat.objects.count())
        with patch('requests.sessions.Session.request',side_effect=AssertionError('Repeated seed must stay offline')):
            call_command('seed_data',verbosity=0)
        self.assertEqual(counts,(Train.objects.count(),Station.objects.count(),TrainStop.objects.count(),Seat.objects.count()))
        booking.refresh_from_db()
        self.assertEqual(booking.status,'PENDING')
        self.assertEqual(booking.seat_id,seat.id)
