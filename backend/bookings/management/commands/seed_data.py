"""Install the bundled railway reference snapshot and local demo inventory."""
import json
import os
from pathlib import Path
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from bookings.models import Train, Station, TrainStop, Seat, Booking, Journey


class Command(BaseCommand):
    help = 'Seed offline real route references and local seats. No railway API or network access.'

    @transaction.atomic
    def handle(self, *args, **options):
        catalogue=json.loads((Path(__file__).resolve().parents[2]/'data'/'route_catalogue.json').read_text(encoding='utf8'))
        prefixes={'SL':'S','3A':'B','2A':'A','1A':'H','CC':'C','EC':'E'}
        imported=0
        for entry in catalogue['trains']:
            train,created=Train.objects.get_or_create(number=entry['train_no'],defaults={'name':entry['train_name']})
            existing=list(train.stops.order_by('sequence').values_list('station__code',flat=True))
            codes=[stop['station_code'] for stop in entry['route']]
            if existing and existing != codes:
                list(Journey.objects.select_for_update().filter(train=train))
                if Booking.objects.filter(journey__train=train).exists():
                    self.stderr.write(f'Skipped conflicting booked route {train.number}; existing data preserved.')
                    continue
                # An unbooked legacy reference can be replaced safely. Journey IDs and
                # user accounts stay intact; no paid/held/cancelled booking is rewritten.
                train.stops.all().delete()
                Seat.objects.filter(train=train).delete()
                self.stdout.write(f'Replaced unbooked legacy reference {train.number}.')
            train.name=entry['train_name'];train.in_catalogue=True;train.run_days=entry['runs_on']
            train.valid_from=entry.get('valid_from');train.valid_until=entry.get('valid_until');train.save()
            previous_distance=-1
            stations = {row['station_code']: row['station_name'] for row in entry['route']}
            Station.objects.bulk_create([Station(code=code,name=name) for code,name in stations.items()],
                update_conflicts=True, unique_fields=['code'], update_fields=['name'])
            station_map = Station.objects.in_bulk(stations, field_name='code')
            stops = []
            for index,row in enumerate(entry['route'],1):
                station=station_map[row['station_code']]
                distance=int(row['distance_km'])
                if distance <= previous_distance:
                    raise CommandError(f'Non-increasing distances in {train.number}')
                previous_distance=distance
                stops.append(TrainStop(train=train,sequence=index,station=station,
                    distance_km=distance,arrival=row.get('arrival','').replace('.',':'),
                    departure=row.get('departure','').replace('.',':'),day=int(row['day'])))
            TrainStop.objects.bulk_create(stops, update_conflicts=True,
                unique_fields=['train','sequence'], update_fields=['station','distance_km','arrival','departure','day'])
            existing_seats = {(seat.coach,seat.number):seat for seat in Seat.objects.filter(train=train)}
            missing_seats = []
            for travel_class in entry['demo_classes']:
                for number in range(1,13):
                    coach=prefixes[travel_class]+'1'
                    seat=existing_seats.get((coach,number))
                    if seat and seat.travel_class != travel_class:
                        raise CommandError(f'Existing seat {seat.id} has a different class; no inventory was changed.')
                    if not seat:
                        missing_seats.append(Seat(train=train,coach=coach,number=number,travel_class=travel_class))
            Seat.objects.bulk_create(missing_seats)
            imported+=1
        password=os.environ.get('DEMO_PASSWORD')
        if password:
            user,created=get_user_model().objects.get_or_create(username='demo')
            if created:
                user.set_password(password);user.save()
                self.stdout.write('Created non-staff demo user; password from DEMO_PASSWORD.')
        self.stdout.write(self.style.SUCCESS(f"Offline catalogue ready: {imported} real route references, 12 demo seats per class. Existing bookings preserved."))
