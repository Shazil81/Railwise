"""Allocation uses journey locks, then booking locks; PostgreSQL rejects overlap."""
from datetime import timedelta
from decimal import Decimal
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from .models import Booking, Journey, Seat, TrainStop
from .payments import confirm_payment  # compatibility import; always requires verified evidence
from .rules import departure_at

class SeatBusy(Exception): pass
class SeatTaken(Exception): pass

def validate_segment(journey, f, t):
    stops = set(TrainStop.objects.filter(train_id=journey.train_id).values_list('sequence', flat=True))
    if f >= t or f not in stops or t not in stops:
        raise ValidationError('Choose valid stops in route order.')
    day = TrainStop.objects.get(train_id=journey.train_id, sequence=f).day
    if journey.date + timedelta(days=day-1) < timezone.localdate():
        raise ValidationError('This journey is in the past.')

def _overlap_qs(jid, sid, f, t):
    return Booking.objects.filter(journey_id=jid, seat_id=sid, status__in=Booking.ACTIVE,
        from_seq__lt=t, to_seq__gt=f)

def _promote_locked(journey):
    from .rules import require_booking_open
    seats = list(Seat.objects.filter(train_id=journey.train_id).order_by('coach', 'number'))
    waiting=list(Booking.objects.select_for_update().filter(journey=journey, status=Booking.Status.WL).order_by('created_at', 'id'))
    # First allocate each class's own waiting list, then consider opted-in upgrades.
    for upgrade_pass,b in [(phase,item) for phase in (False,True) for item in waiting]:
        if b.status != Booking.Status.WL:continue
        if upgrade_pass and (not b.consider_auto_upgrade or b.confirmed_berths_only):continue
        try:
            require_booking_open(journey, b.from_seq, b.travel_class, b.quota)
        except ValidationError:
            b.status = Booking.Status.EXPIRED
            b.save(update_fields=['status'])
            continue
        ladders=[['SL','3A','2A','1A'],['CC','EC']]
        ladder=next((items for items in ladders if b.travel_class in items),[])
        eligible=ladder[ladder.index(b.travel_class)+1:] if upgrade_pass and ladder else [b.travel_class]
        candidates=sorted((seat for seat in seats if seat.travel_class in eligible),
            key=lambda seat:(eligible.index(seat.travel_class),b.berth_preference!='ANY' and seat.allocated_berth!=b.berth_preference,bool(b.preferred_coach) and seat.coach!=b.preferred_coach,seat.coach,seat.number))
        for seat in candidates:
            if not _overlap_qs(journey.id, seat.id, b.from_seq, b.to_seq).exists():
                b.seat = seat
                b.status = Booking.Status.PENDING
                b.expires_at = min(timezone.now() + timedelta(seconds=settings.BOOKING_HOLD_SECONDS), departure_at(journey, b.from_seq))
                b.save(update_fields=['seat', 'status', 'expires_at'])
                from .notifications import queue_booking_email
                queue_booking_email(b, 'PROMOTED')
                break

def _expire_locked(journey):
    count = Booking.objects.filter(journey=journey, status=Booking.Status.PENDING,
        expires_at__lte=timezone.now()).update(status=Booking.Status.EXPIRED, expires_at=None)
    _promote_locked(journey)
    return count

@transaction.atomic
def expire_journey(journey_id):
    return _expire_locked(Journey.objects.select_for_update().get(pk=journey_id))

@transaction.atomic
def book_seat(user, journey_id, seat_id, from_seq, to_seq, quota='GN', _quote=None, confirmed_berths_only=False, consider_auto_upgrade=False):
    j = Journey.objects.select_for_update().get(pk=journey_id)
    validate_segment(j, from_seq, to_seq)
    _expire_locked(j)
    seat = Seat.objects.filter(pk=seat_id, train_id=j.train_id).first()
    if not seat:
        raise ValidationError('Seat does not belong to this train.')
    from .rules import require_booking_open
    require_booking_open(j, from_seq, seat.travel_class, quota)
    if _overlap_qs(j.id, seat_id, from_seq, to_seq).exists():
        raise SeatTaken('That seat was just taken. Please refresh and choose another.')
    from .tariffs import price_segment
    quote = _quote or price_segment(j, from_seq, to_seq, seat.travel_class, quota)
    return Booking.objects.create(user=user, journey=j, seat_id=seat_id,
        confirmed_berths_only=confirmed_berths_only,consider_auto_upgrade=consider_auto_upgrade,
        from_seq=from_seq, to_seq=to_seq, status=Booking.Status.PENDING,
        amount=Decimal(quote['total']), travel_class=seat.travel_class, quota=quota, fare_details=quote,
        expires_at=min(timezone.now() + timedelta(seconds=settings.BOOKING_HOLD_SECONDS), departure_at(j, from_seq)))

@transaction.atomic
def join_waitlist(user, journey_id, from_seq, to_seq, travel_class='SL', quota='GN', confirmed_berths_only=False, consider_auto_upgrade=False):
    if confirmed_berths_only:raise ValidationError('Confirmed berths only: waitlisting is not permitted. Choose available seats.')
    j = Journey.objects.select_for_update().get(pk=journey_id)
    validate_segment(j, from_seq, to_seq)
    from .rules import require_booking_open
    require_booking_open(j, from_seq, travel_class, quota)
    _expire_locked(j)
    existing = Booking.objects.filter(user=user, journey=j, from_seq=from_seq, to_seq=to_seq, travel_class=travel_class, quota=quota, status=Booking.Status.WL).first()
    if existing:
        existing.consider_auto_upgrade=consider_auto_upgrade
        existing.save(update_fields=['consider_auto_upgrade'])
        return existing
    if not Seat.objects.filter(train=j.train,travel_class=travel_class).exists():
        raise ValidationError('This class is not offered on this train.')
    for seat in Seat.objects.filter(train_id=j.train_id, travel_class=travel_class):
        if not _overlap_qs(j.id, seat.id, from_seq, to_seq).exists():
            raise ValidationError('Seats are available. Select a seat instead.')
    from .tariffs import price_segment
    quote = price_segment(j,from_seq,to_seq,travel_class,quota)
    return Booking.objects.create(user=user, journey=j, from_seq=from_seq, to_seq=to_seq, status=Booking.Status.WL,
        confirmed_berths_only=False,consider_auto_upgrade=consider_auto_upgrade,
        amount=Decimal(quote['total']),travel_class=travel_class,quota=quota,fare_details=quote)

def waitlist_position(b):
    return Booking.objects.filter(journey_id=b.journey_id, travel_class=b.travel_class, status=Booking.Status.WL, id__lte=b.id).count()

def group_members(booking):
    from django.db.models import Q
    if booking.group_parent_id:
        raise ValidationError('Manage passengers through the main booking reference.')
    return Booking.objects.filter(Q(pk=booking.pk) | Q(group_parent_id=booking.pk)).order_by('id')

@transaction.atomic
def book_group(user, journey_id, seat_ids, from_seq, to_seq, quota='GN', confirmed_berths_only=False, consider_auto_upgrade=False):
    if not 1 <= len(seat_ids) <= 6 or len(set(seat_ids)) != len(seat_ids):
        raise ValidationError('Select between 1 and 6 different seats.')
    journey = Journey.objects.select_for_update().get(pk=journey_id)
    validate_segment(journey,from_seq,to_seq)
    _expire_locked(journey)
    seats = list(Seat.objects.filter(pk__in=seat_ids, train=journey.train))
    if len(seats) != len(seat_ids) or len({seat.travel_class for seat in seats}) != 1:
        raise ValidationError('Choose seats from one class on this train.')
    from .tariffs import price_segment
    quote = price_segment(journey,from_seq,to_seq,seats[0].travel_class,quota)
    leader = None
    for seat_id in seat_ids:
        b = book_seat(user, journey_id, seat_id, from_seq, to_seq, quota, _quote=quote,
            confirmed_berths_only=confirmed_berths_only,consider_auto_upgrade=consider_auto_upgrade)
        if leader is None:
            leader = b
        else:
            b.group_parent = leader
            b.expires_at = leader.expires_at
            b.save(update_fields=['group_parent', 'expires_at'])
    return leader

def lock_main_booking(booking_id, user):
    jid = Booking.objects.get(pk=booking_id, user=user).journey_id
    Journey.objects.select_for_update().get(pk=jid)
    booking = Booking.objects.select_for_update().get(pk=booking_id, user=user)
    if booking.group_parent_id:
        raise ValidationError('Use the main booking reference.')
    return booking


@transaction.atomic
def book_automatically(user, data):
    """Allocate a complete passenger group; clients never choose seat identifiers."""
    journey = Journey.objects.select_for_update().get(pk=data['journey_id'].id)
    f,t = data['from_seq'],data['to_seq']
    validate_segment(journey,f,t)
    _expire_locked(journey)
    from .rules import require_booking_open
    require_booking_open(journey,f,data['travel_class'],data['quota'])
    from .berths import LAYOUTS
    for passenger in data['passengers']:
        preference=passenger.get('berth_preference','ANY')
        if preference!='ANY' and preference not in LAYOUTS.get(data['travel_class'],[]):
            raise ValidationError('This berth preference is not supported in the selected class.')
    occupied = Booking.objects.filter(journey=journey,status__in=Booking.ACTIVE,
        from_seq__lt=t,to_seq__gt=f,seat__isnull=False).values_list('seat_id',flat=True)
    seats = list(Seat.objects.filter(train=journey.train,travel_class=data['travel_class'])
        .exclude(id__in=occupied).order_by('coach','number')[:len(data['passengers'])])
    if len(seats) != len(data['passengers']):
        if not seats and len(data['passengers'])==1 and not data['confirmed_berths_only']:
            passenger=data['passengers'][0]
            waiting=join_waitlist(user,journey.id,f,t,data['travel_class'],data['quota'],False,data['consider_auto_upgrade'])
            waiting.passenger_name=passenger['name'];waiting.passenger_age=passenger['age'];waiting.passenger_gender=passenger['gender']
            waiting.berth_preference=passenger.get('berth_preference','ANY')
            waiting.passenger_country=passenger.get('country','India')
            waiting.preferred_coach=data.get('preferred_coach','');waiting.gstin=data.get('gstin','')
            waiting.contact_email=data['contact_email'];waiting.contact_phone=data['contact_phone']
            waiting.save(update_fields=['passenger_name','passenger_age','passenger_gender','berth_preference','contact_email','contact_phone','passenger_country','preferred_coach','gstin'])
            return waiting
        raise ValidationError('Not enough seats remain for all passengers in this class. Choose another class or train; no seats were held.')
    leader=book_group(user,journey.id,[seat.id for seat in seats],f,t,data['quota'],
        data['confirmed_berths_only'],data['consider_auto_upgrade'])
    passengers=[{**passenger,'booking_id':member.id} for member,passenger in zip(group_members(leader),data['passengers'])]
    return save_passengers(leader.id,user,{**data,'passengers':passengers})

@transaction.atomic
def save_passengers(booking_id, user, data):
    from .payments import require_payable
    b = lock_main_booking(booking_id, user)
    members = list(group_members(b).select_for_update())
    for member in members:
        require_payable(member)
    if b.razorpay_order_id:
        raise ValidationError('Passenger details are locked after payment checkout starts.')
    passengers = data['passengers']
    ids = [p['booking_id'] for p in passengers]
    if len(set(ids)) != len(ids) or set(ids) != {m.id for m in members}:
        raise ValidationError('Provide one passenger for every held seat in this booking.')
    by_id = {p['booking_id']: p for p in passengers}
    from .berths import allocate_preferences
    coach=data.get('preferred_coach',b.preferred_coach)
    plans=allocate_preferences(b.journey,members,passengers,coach)
    if any(member.seat_id!=plans[member.id]['seat'].id for member in members):
        # Release only inside this atomic transaction to permit safe group swaps.
        group_members(b).update(seat=None)
    for member in members:
        p = by_id[member.id]
        member.seat=plans[member.id]['seat']
        member.berth_preference=plans[member.id]['preference']
        member.passenger_country=p.get('country',member.passenger_country)
        member.passenger_name, member.passenger_age, member.passenger_gender = p['name'], p['age'], p['gender']
        member.save(update_fields=['passenger_name', 'passenger_age', 'passenger_gender','seat','berth_preference','passenger_country'])
    b.refresh_from_db()
    b.contact_email, b.contact_phone = data['contact_email'], data['contact_phone']
    b.reviewed_at = None
    b.preferred_coach=coach;b.gstin=data.get('gstin',b.gstin)
    b.confirmed_berths_only=data.get('confirmed_berths_only',b.confirmed_berths_only)
    b.consider_auto_upgrade=data.get('consider_auto_upgrade',b.consider_auto_upgrade)
    group_members(b).update(confirmed_berths_only=b.confirmed_berths_only,consider_auto_upgrade=b.consider_auto_upgrade,preferred_coach=b.preferred_coach)
    b.save(update_fields=['contact_email', 'contact_phone', 'reviewed_at','confirmed_berths_only','consider_auto_upgrade','preferred_coach','gstin'])
    return b

@transaction.atomic
def accept_review(booking_id, user):
    from .payments import require_checkout_ready
    b = lock_main_booking(booking_id, user)
    require_checkout_ready(b, reviewed=False)
    if not b.reviewed_at:
        b.reviewed_at = timezone.now()
        b.save(update_fields=['reviewed_at'])
    return b

@transaction.atomic
def cancel_booking(booking_id, user):
    b = lock_main_booking(booking_id, user)
    cancelled_now = b.status in [Booking.Status.PENDING, Booking.Status.CONFIRMED, Booking.Status.WL]
    if b.status in [Booking.Status.PENDING, Booking.Status.CONFIRMED, Booking.Status.WL]:
        from .rules import require_cancellation_open
        require_cancellation_open(b)
        group_members(b).filter(status__in=['PENDING', 'CONFIRMED', 'WL']).update(status=Booking.Status.CANCELLED, expires_at=None)
        _promote_locked(b.journey)
    b.refresh_from_db()
    from .lifecycle import queue_booking_refunds
    queue_booking_refunds(b)
    if cancelled_now:
        from .notifications import queue_booking_email
        queue_booking_email(b, 'CANCELLED')
    return b
