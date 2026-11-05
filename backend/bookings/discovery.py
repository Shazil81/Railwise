"""Offline station search, cached timetables, internal quotes and local inventory."""
import json
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Station, Train, Journey, Seat
from .services import expire_journey
from .tariffs import price_segment, RULES


@lru_cache(maxsize=1)
def station_directory():
    return json.loads((Path(__file__).parent/'data'/'stations.json').read_text(encoding='utf-8-sig'))


@lru_cache(maxsize=1)
def city_aliases():
    return json.loads((Path(__file__).parent/'data'/'city_aliases.json').read_text(encoding='utf-8'))


def terminal_group(value):
    """Curated city terminals, not a geographic radius or a provider lookup."""
    text=value.strip().casefold()
    aliases=city_aliases()
    codes=aliases.get(text)
    if codes is None:
        codes=next((items for items in aliases.values() if text.upper() in items),None)
    if codes is None:return None
    # Synonyms can list slightly different terminals; merge the connected group.
    merged=list(codes)
    for items in aliases.values():
        if set(items)&set(merged):
            merged.extend(code for code in items if code not in merged)
    name=next(name for name,items in aliases.items() if set(items)&set(merged))
    return {'name':name.title(),'codes':merged}


def search_terminals(value, include_nearby):
    text=value.strip().upper()
    group=terminal_group(text) if include_nearby else None
    codes=group['codes'] if group else [text]
    if text in codes:codes=[text]+[code for code in codes if code!=text]
    stations={station.code:station for station in Station.objects.filter(code__in=codes)}
    found=[code for code in codes if code in stations]
    if not found:raise ValidationError('Choose a known station code, or a supported city with nearby terminals enabled.')
    return found,[{'code':code,'name':stations[code].name} for code in found]


class StationSearchView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    def get(self, request):
        query = request.query_params.get('q','').strip().casefold()
        if not 1 <= len(query) <= 80:
            raise ValidationError('Enter a station name or code (up to 80 characters).')
        # Catalogue names take precedence over historical aliases; no network lookups.
        directory = {row['code']:row for row in station_directory() if row['code'] != 'CP'}
        directory.update({s.code:{'code':s.code,'name':s.name} for s in Station.objects.all()})
        directory['KOAA'] = {'code':'KOAA','name':'Kolkata'}
        aliases = city_aliases()
        city_codes = {code for city,codes in aliases.items() if query in city for code in codes}
        served = set(Station.objects.filter(trainstop__train__in_catalogue=True).values_list('code',flat=True))
        matches = [row for row in directory.values() if query in row['name'].casefold() or query in row['code'].casefold() or row['code'] in city_codes]
        matches.sort(key=lambda row:(row['code'].casefold()!=query, row['code'] not in served, not row['name'].casefold().startswith(query), row['name']))
        # Exact city names with several served terminals require an explicit station.
        # Never silently redirect Mumbai/Bengaluru/Kolkata to a different terminal.
        needs_selection = query in aliases and len(set(aliases[query]) & served) > 1
        return Response({'stations':matches[:30],'total':len(matches),'requires_selection':needs_selection,
            'is_city':query in aliases,'terminal_group':terminal_group(query),
            'warning':'','source':'Local station catalogue'})


def journey_data(journey, from_seq=None, to_seq=None, quota='GN'):
    stops = list(journey.train.stops.select_related('station').all())
    classes = []
    if from_seq is not None:
        expire_journey(journey.id)
        for travel_class in Seat.objects.filter(train=journey.train).order_by('travel_class').values_list('travel_class',flat=True).distinct():
            if travel_class in RULES:
                classes.append(price_segment(journey, from_seq, to_seq, travel_class, quota))
    return {'id':journey.id,'date':journey.date.isoformat(),'train':journey.train.name,'number':journey.train.number,
        'stops':[{'sequence':s.sequence,'code':s.station.code,'name':s.station.name,'distance_km':s.distance_km,
            'arrival':s.arrival,'departure':s.departure,'day':s.day} for s in stops], 'classes':classes}


class TrainSearchView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    def get(self, request):
        origin, destination = (request.query_params.get(key,'').strip().upper() for key in ('from','to'))
        quota = request.query_params.get('quota','GN').upper()
        nearby_value=request.query_params.get('include_nearby','true').lower()
        if nearby_value not in ('true','false','1','0'):
            raise ValidationError('include_nearby must be true or false.')
        include_nearby=nearby_value in ('true','1')
        if not origin or origin == destination or quota not in ('GN','TQ'):
            raise ValidationError('Choose two different stations and a valid quota.')
        try:
            travel = date.fromisoformat(request.query_params.get('date',''))
        except ValueError:
            raise ValidationError('Choose a valid travel date.') from None
        if not timezone.localdate() <= travel <= timezone.localdate()+timedelta(days=60):
            raise ValidationError('Choose a travel date within the next 60 days.')
        origins,from_stations=search_terminals(origin,include_nearby)
        destinations,to_stations=search_terminals(destination,include_nearby)
        if include_nearby and set(origins)&set(destinations):
            raise ValidationError('Choose two different cities or turn off nearby terminals for a local segment.')
        results=[]
        for train in Train.objects.filter(in_catalogue=True).prefetch_related('stops__station'):
            stops={s.station.code:s for s in train.stops.all()}
            pairs=[(a,b) for a in origins for b in destinations if a in stops and b in stops and stops[a].sequence<stops[b].sequence]
            for actual_from,actual_to in pairs:
                start_date=travel-timedelta(days=stops[actual_from].day-1)
                if (train.valid_from and start_date < train.valid_from) or (train.valid_until and start_date > train.valid_until):continue
                if train.run_days and ('Mon','Tue','Wed','Thu','Fri','Sat','Sun')[start_date.weekday()] not in train.run_days:continue
                journey,_=Journey.objects.get_or_create(train=train,date=start_date)
                row=journey_data(journey,stops[actual_from].sequence,stops[actual_to].sequence,quota)
                row.update(origin_code=actual_from,destination_code=actual_to,boarding_date=travel.isoformat(),
                    nearby_match=include_nearby and (actual_from!=origin or actual_to!=destination))
                results.append(row)
                # Prefer the selected terminals, then the curated group order. One
                # result per train avoids duplicate seat inventories for alternatives.
                break
        return Response({'journeys':results,'date':travel.isoformat(),'source':'Local route catalogue',
            'include_nearby':include_nearby,'from_stations':from_stations,'to_stations':to_stations})


class JourneyQuoteView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    def get(self,request,journey_id):
        from .serializers import SegmentSerializer
        serializer=SegmentSerializer(data={'journey_id':journey_id,'from_seq':request.query_params.get('from'),'to_seq':request.query_params.get('to')})
        serializer.is_valid(raise_exception=True)
        values=serializer.validated_data
        expire_journey(journey_id)
        return Response(price_segment(values['journey_id'],values['from_seq'],values['to_seq'],
            request.query_params.get('travel_class','SL'),request.query_params.get('quota','GN')))
