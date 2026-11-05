"""Public seat counts over SSE. No passenger/payment data or railway provider calls."""
import json
import time
from django.db import close_old_connections
from django.http import StreamingHttpResponse
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework.renderers import BaseRenderer, JSONRenderer
from .models import Journey, Seat
from .services import expire_journey
from .tariffs import price_segment


def validate_segments(raw):
    if len(raw)>8192:raise ValidationError('Too many inventory segments.')
    try:
        rows=json.loads(raw)
        if not isinstance(rows,list) or not 1<=len(rows)<=128:raise ValueError()
        segments=[]
        for row in rows:
            if not isinstance(row,list) or len(row)!=3 or any(type(v) is not int or v<=0 for v in row):raise ValueError()
            if tuple(row) not in segments:segments.append(tuple(row))
    except (ValueError,TypeError):raise ValidationError('Provide up to 128 [journey_id, from_seq, to_seq] segments.') from None
    journeys={j.id:j for j in Journey.objects.filter(id__in=[r[0] for r in segments]).select_related('train').prefetch_related('train__stops')}
    for jid,start,end in segments:
        if jid not in journeys:raise ValidationError('Unknown journey.')
        sequences={stop.sequence for stop in journeys[jid].train.stops.all()}
        if start>=end or start not in sequences or end not in sequences:raise ValidationError('Invalid inventory segment.')
    return segments


def inventory_snapshot(segments):
    rows=[]
    for jid,start,end in segments:
        journey=Journey.objects.select_related('train').prefetch_related('train__stops').get(pk=jid)
        expire_journey(jid)
        classes=[]
        for code in Seat.objects.filter(train=journey.train).values_list('travel_class',flat=True).distinct():
            quote=price_segment(journey,start,end,code)
            classes.append({'travel_class':code,'available_seats':quote['available_seats'],'capacity':quote['capacity']})
        rows.append({'id':jid,'from_seq':start,'to_seq':end,'classes':classes})
    return rows


def inventory_events(segments,lifetime=60,interval=3):
    import hashlib
    from django.core.cache import cache
    key = 'inventory-snapshot:' + hashlib.sha256(json.dumps(sorted(segments)).encode()).hexdigest()
    previous=None
    deadline=time.monotonic()+lifetime
    try:
        yield 'retry: 2000\n\n'
        while time.monotonic()<deadline:
            close_old_connections()
            # Share public counts between viewers; allocation still checks PostgreSQL.
            # TTL is shorter than the stream interval to keep display lag brief.
            rows=cache.get_or_set(key, lambda: inventory_snapshot(segments), timeout=min(2, interval))
            fingerprint=json.dumps(rows,sort_keys=True)
            if fingerprint!=previous:
                payload=json.dumps({'journeys':rows,'observed_at':timezone.now().isoformat()})
                yield 'event: inventory\ndata: '+payload+'\n\n'
                previous=fingerprint
            else:
                yield ': heartbeat\n\n'
            close_old_connections()
            time.sleep(interval)
    finally:
        close_old_connections()


class EventStreamRenderer(BaseRenderer):
    media_type='text/event-stream'
    format='event-stream'
    charset='utf-8'

    def render(self,data,accepted_media_type=None,renderer_context=None):
        return json.dumps(data).encode('utf-8')


class InventoryStreamView(APIView):
    permission_classes=[AllowAny]
    authentication_classes=[]
    renderer_classes=[EventStreamRenderer,JSONRenderer]

    def get(self,request):
        segments=validate_segments(request.query_params.get('segments',''))
        response=StreamingHttpResponse(inventory_events(segments),content_type='text/event-stream')
        response['Cache-Control']='no-cache, no-store'
        response['X-Accel-Buffering']='no'
        return response
