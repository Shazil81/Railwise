"""Project reservation rules, evaluated in Indian time (not official IRCTC policy)."""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from django.utils import timezone
from rest_framework.exceptions import ValidationError

IST = ZoneInfo('Asia/Kolkata')


def departure_at(journey, sequence):
    stop = journey.train.stops.get(sequence=sequence)
    clock = stop.departure or stop.arrival
    # Legacy fixtures without timetable times retain date-only behaviour.
    parsed = time.fromisoformat(clock) if clock else time(23, 59, 59)
    return datetime.combine(journey.date + timedelta(days=stop.day - 1), parsed, IST)


def require_booking_open(journey, sequence, travel_class='SL', quota='GN'):
    train = journey.train
    if (train.valid_from and journey.date < train.valid_from) or (train.valid_until and journey.date > train.valid_until):
        raise ValidationError('This service does not operate on the selected origin date.')
    now = timezone.now().astimezone(IST)
    departure = departure_at(journey, sequence)
    if now >= departure:
        raise ValidationError('Booking is closed: this train has departed your boarding station.')
    if departure.date() > now.date() + timedelta(days=60):
        raise ValidationError('Bookings open up to 60 days before boarding.')
    if quota not in ('GN', 'TQ'):
        raise ValidationError('Choose a supported quota.')
    if quota == 'TQ':
        origin = departure_at(journey, journey.train.stops.order_by('sequence').first().sequence)
        opening = datetime.combine(origin.date() - timedelta(days=1), time(11 if travel_class == 'SL' else 10), IST)
        if now < opening:
            raise ValidationError(f'Tatkal opens at {opening:%d %b %Y %H:%M} IST for this service.')


def require_cancellation_open(booking):
    if timezone.now() >= departure_at(booking.journey, booking.from_seq):
        raise ValidationError('Cancellation is closed after departure from your boarding station.')
