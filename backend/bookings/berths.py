"""Local demo coach layouts; not an official rolling-stock coach chart."""
LABELS={'ANY':'No preference','LB':'Lower','MB':'Middle','UB':'Upper','SL':'Side Lower','SU':'Side Upper','NA':'Seat (no berth)'}
LAYOUTS={'SL':['LB','MB','UB','LB','MB','UB','SL','SU'],
    '3A':['LB','MB','UB','LB','MB','UB','SL','SU'],
    '2A':['LB','UB','LB','UB','SL','SU'],'1A':['LB','UB'],'CC':['NA'],'EC':['NA']}


def inferred_berth(travel_class,number):
    layout=LAYOUTS.get(travel_class,['NA'])
    return layout[(number-1)%len(layout)]


def allocate_preferences(journey,members,passengers,preferred_coach=''):
    """Plan a group reassignment before changing any seats. Caller holds journey lock."""
    from rest_framework.exceptions import ValidationError
    from .models import Booking,Seat
    by_id={p['booking_id']:p for p in passengers}
    plans={}
    available={}
    for member in members:
        if not member.seat_id:raise ValidationError('Every passenger needs a held seat.')
        code=member.seat.travel_class
        preference=by_id[member.id].get('berth_preference',member.berth_preference)
        if preference!='ANY' and preference not in LAYOUTS.get(code,[]):
            raise ValidationError(f'{LABELS.get(preference,preference)} is not supported in {code}. Choose no preference or a supported berth.')
        plans[member.id]={'preference':preference,'class':code}
        if code not in available:
            occupied=Booking.objects.filter(journey=journey,status__in=Booking.ACTIVE,seat__isnull=False,
                from_seq__lt=member.to_seq,to_seq__gt=member.from_seq).exclude(id__in=[b.id for b in members]).values_list('seat_id',flat=True)
            available[code]=sorted(Seat.objects.filter(train=journey.train,travel_class=code).exclude(id__in=occupied),
                key=lambda seat:(bool(preferred_coach) and seat.coach!=preferred_coach,seat.coach,seat.number))
    # Specific requests first so a no-preference passenger doesn't take the only match.
    ordered=sorted(members,key=lambda member:(plans[member.id]['preference']=='ANY',
        sum(seat.allocated_berth==plans[member.id]['preference'] for seat in available[plans[member.id]['class']]),member.id))
    used=set()
    for member in ordered:
        plan=plans[member.id]
        candidates=[seat for seat in available[plan['class']] if seat.id not in used]
        matches=[seat for seat in candidates if seat.allocated_berth==plan['preference']] if plan['preference']!='ANY' else []
        preferred=next((seat for seat in matches if seat.id==member.seat_id and (not preferred_coach or seat.coach==preferred_coach)),None)
        seat=preferred or (matches[0] if matches else next((seat for seat in candidates if seat.coach==preferred_coach),None) or next((seat for seat in candidates if seat.id==member.seat_id),None))
        seat=seat or (candidates[0] if candidates else None)
        if seat is None:raise ValidationError('Seats changed while allocating berths. Refresh this booking.')
        plan['seat']=seat;used.add(seat.id)
    return plans
