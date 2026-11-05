"""Display metadata derived from the saved timetable, never invented live data."""
from datetime import datetime, time, timedelta
from .rules import IST
from .tariffs import LABELS


def journey_details(booking):
    stops = {s.sequence: s for s in booking.journey.train.stops.all()}
    origin, destination = stops.get(booking.from_seq), stops.get(booking.to_seq)

    def instant(stop, attribute):
        clock = getattr(stop, attribute, '') if stop else ''
        if not clock:
            return None
        return datetime.combine(booking.journey.date + timedelta(days=stop.day - 1), time.fromisoformat(clock), IST)

    departure, arrival = instant(origin, 'departure'), instant(destination, 'arrival')
    duration = int((arrival - departure).total_seconds() / 60) if departure and arrival else None
    return {
        'booked_at': booking.created_at,
        'departure_at': departure.isoformat() if departure else None,
        'arrival_at': arrival.isoformat() if arrival else None,
        'duration_minutes': duration if duration is not None and duration >= 0 else None,
        'origin_code': origin.station.code if origin else None,
        'destination_code': destination.station.code if destination else None,
        'class_name': LABELS.get(booking.seat.travel_class if booking.seat else booking.travel_class, booking.travel_class),
    }
