"""Versioned project pricing. Values are demo rules, not official railway tariffs."""
from decimal import Decimal, ROUND_HALF_UP
from rest_framework.exceptions import ValidationError
from .models import Booking, Seat

# rate/km, minimum base, reservation fee, minimum and maximum Tatkal surcharge
RULES = {
    'SL': ('0.65','100','20','50','200'), '3A': ('1.50','250','40','150','400'),
    '2A': ('2.20','350','50','200','500'), '1A': ('3.50','600','60','300','750'),
    'CC': ('1.20','180','40','100','300'), 'EC': ('2.70','450','60','250','600'),
}
LABELS = dict(Seat._meta.get_field('travel_class').choices)


def price_segment(journey, from_seq, to_seq, travel_class='SL', quota='GN'):
    if travel_class not in RULES or quota not in ('GN','TQ'):
        raise ValidationError('Choose a supported class and quota.')
    stops = {stop.sequence:stop for stop in journey.train.stops.all()}
    if from_seq >= to_seq or from_seq not in stops or to_seq not in stops:
        raise ValidationError('Choose stops in route order.')
    start, end = stops[from_seq], stops[to_seq]
    if start.distance_km is None or end.distance_km is None:
        # Older inventory remains manageable, but new priced holds require route distances.
        raise ValidationError('This route has no distance data. Load the local route catalogue first.')
    distance = end.distance_km - start.distance_km
    if distance <= 0:
        raise ValidationError('Route distances must increase along the journey.')
    rate, minimum, reservation, tq_min, tq_max = map(Decimal, RULES[travel_class])
    seats = Seat.objects.filter(train=journey.train, travel_class=travel_class)
    total = seats.count()
    busy = Booking.objects.filter(journey=journey, seat__travel_class=travel_class, seat__isnull=False, status__in=Booking.ACTIVE,
        from_seq__lt=to_seq, to_seq__gt=from_seq).values_list('seat_id', flat=True)
    available = seats.exclude(id__in=busy).count()
    base = max(minimum, Decimal(distance) * rate)
    dynamic = base * Decimal('0.10') if total and (total-available) * 100 >= total * 80 else Decimal('0')
    tatkal = min(tq_max, max(tq_min, base * Decimal('0.30'))) if quota == 'TQ' else Decimal('0')
    money = lambda value: format(value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP), '.2f')
    # Round each component once so the displayed components add to the stored total.
    components = {name:money(value) for name,value in [('base_fare',base),('reservation_fee',reservation),('demand_surcharge',dynamic),('tatkal_surcharge',tatkal)]}
    from .rules import require_booking_open
    booking_error = ''
    try:
        require_booking_open(journey, from_seq, travel_class, quota)
    except ValidationError as error:
        booking_error = str(error.detail[0])
    return {'booking_open':not booking_error,'booking_error':booking_error,'version':'local-v1','currency':'INR','distance_km':distance,'travel_class':travel_class,
        'class_name':LABELS[travel_class],'quota':quota,'rate_per_km':str(rate),**components,
        'total':money(sum(map(Decimal,components.values()))),'available_seats':available,'capacity':total,
        'label':'Project fare rules; not an official Indian Railways tariff'}
