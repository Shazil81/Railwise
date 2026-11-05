from decimal import Decimal
from django.http import HttpResponse
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from .models import Booking, Journey, Seat, Refund
from .serializers import BookingSerializer, SegmentSerializer, PaymentVerificationSerializer, PassengerDetailsSerializer
from .payments import create_order
from .tickets import confirmation_snapshot, render_ticket, ticket_available
from .lifecycle import recover_booking, handle_webhook
from .booking_display import journey_details
from .services import (SeatTaken, book_seat, confirm_payment, join_waitlist,
    waitlist_position, cancel_booking, expire_journey, book_group, group_members, save_passengers, accept_review)

def booking_data(b):
    stops = {s.sequence: s.station.name for s in b.journey.train.stops.all()}
    members = list(group_members(b).select_related('seat'))
    total = sum(m.amount for m in members)
    return {
        **journey_details(b),
        'payment_mode': 'test' if settings.RAZORPAY_KEY_ID.startswith('rzp_test_') else 'live' if settings.RAZORPAY_KEY_ID.startswith('rzp_live_') else 'unconfigured',
        'confirmed_berths_only':b.confirmed_berths_only,'consider_auto_upgrade':b.consider_auto_upgrade,
        'preferred_coach':b.preferred_coach,'gstin':b.gstin,
        'allocated_class':b.seat.travel_class if b.seat else None,
        'email_notifications': [{'id':n.id,'kind':n.kind,'state':n.state,'attempts':n.attempts,
            'recipient':n.recipient,'created_at':n.created_at,'sent_at':n.sent_at,'message':n.last_error,'delivery_channel':n.delivery_channel}
            for n in b.email_notifications.order_by('-created_at','-id')],
        'passengers': [{'booking_id': m.id, 'seat': str(m.seat) if m.seat else None, 'name': m.passenger_name, 'age': m.passenger_age, 'gender': m.passenger_gender, 'fare': str(m.amount),
            'coach':m.seat.coach if m.seat else None,'seat_number':m.seat.number if m.seat else None,
            'country':m.passenger_country,'berth_preference':m.berth_preference,'allocated_berth':m.seat.allocated_berth if m.seat else None,
            'allocated_class':m.seat.travel_class if m.seat else None,
            'berth_preference_met':m.berth_preference=='ANY' or bool(m.seat and m.seat.allocated_berth==m.berth_preference)} for m in members],
        'contact_email': b.contact_email, 'contact_phone': b.contact_phone, 'reviewed_at': b.reviewed_at,
        'travel_class': b.travel_class, 'quota': b.quota, 'fare_details': b.fare_details,
        'fare_breakdown': {'passenger_count': len(members), 'base_fare': str(total), 'booking_fee': '0.00', 'total': str(total), 'currency': 'INR', 'label': 'Server-calculated project fare; not an Indian Railways tariff'},
        'payment_attempts': [{'payment_id': a.payment_id, 'state': a.state, 'amount': format(Decimal(a.amount_paise) / 100, '.2f'), 'message': a.failure_message, 'updated_at': a.updated_at,
            'created_at':a.created_at,'method':a.method or None,'provider_created_at':a.provider_created_at,'captured_at':a.captured_at} for a in b.payment_attempts.order_by('-created_at')],
        'refunds': [{'reference': r.id, 'provider_id': r.provider_id, 'payment_id': r.attempt.payment_id, 'state': r.state, 'amount': format(Decimal(r.amount_paise) / 100, '.2f'), 'reason': r.reason, 'message': r.message, 'updated_at': r.updated_at,
            'created_at':r.created_at,'processed_at':r.processed_at} for r in Refund.objects.filter(attempt__booking=b).select_related('attempt').order_by('-created_at')],
        'payment_checked_at': b.payment_checked_at,
        'ticket_available': ticket_available(b),
        'booking_reference': f'RW-{b.id:08d}',
        'booking_id': b.id,
        'status': b.status,
        'amount': float(total),
        'razorpay_order_id': b.razorpay_order_id,
        'razorpay_payment_id': b.razorpay_payment_id,
        'expires_at': b.expires_at,
        'seat': ', '.join(str(m.seat) for m in members if m.seat),
        'train': b.journey.train.name,
        'train_number': b.journey.train.number,
        'date': b.boarding_date,
        'origin': stops.get(b.from_seq),
        'destination': stops.get(b.to_seq),
        'position': waitlist_position(b) if b.status == Booking.Status.WL else None
    }

class JourneyView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        journeys = Journey.objects.filter(date__gte=timezone.localdate()).select_related('train').prefetch_related('train__stops__station')
        return Response([{'id': j.id, 'date': j.date, 'train': j.train.name,
            'number': j.train.number, 'stops': [{'sequence': s.sequence,
            'code': s.station.code, 'name': s.station.name} for s in j.train.stops.all()]} for j in journeys.order_by('date', 'train__number')])


class JourneyDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self,request,journey_id):
        j=get_object_or_404(Journey.objects.select_related('train').prefetch_related('train__stops__station'),pk=journey_id)
        return Response({'id':j.id,'date':j.date,'train':j.train.name,'number':j.train.number,
            'stops':[{'sequence':s.sequence,'code':s.station.code,'name':s.station.name,
                'distance_km':s.distance_km,'arrival':s.arrival,'departure':s.departure,'day':s.day}
                for s in j.train.stops.all()]})


class AutomaticBookingView(APIView):
    def post(self,request):
        from .serializers import AutomaticBookingSerializer
        from .services import book_automatically
        serializer=AutomaticBookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(booking_data(book_automatically(request.user,serializer.validated_data)),status=201)

class AvailabilityView(APIView):
    permission_classes = [AllowAny]
    def get(self, request, journey_id):
        s = SegmentSerializer(data={'journey_id': journey_id,
            'from_seq': request.query_params.get('from'), 'to_seq': request.query_params.get('to')})
        s.is_valid(raise_exception=True)
        d = s.validated_data
        j = d['journey_id']
        expire_journey(j.id)
        busy = Booking.objects.filter(journey=j, seat__isnull=False, status__in=Booking.ACTIVE,
            from_seq__lt=d['to_seq'], to_seq__gt=d['from_seq']).values_list('seat_id', flat=True)
        seats = Seat.objects.filter(train=j.train)
        travel_class = request.query_params.get('travel_class')
        if travel_class:
            seats = seats.filter(travel_class=travel_class)
        return Response([{'id': seat.id, 'label': str(seat), 'travel_class':seat.travel_class,'berth_type':seat.allocated_berth} for seat in seats.exclude(id__in=busy).order_by('coach', 'number')])

class BookView(APIView):
    def get(self, request):
        for jid in Booking.objects.filter(user=request.user).values_list('journey_id', flat=True).distinct():
            expire_journey(jid)
        bookings = Booking.objects.filter(user=request.user, group_parent__isnull=True).select_related('journey__train', 'seat').prefetch_related('journey__train__stops__station').order_by('-id')
        return Response([booking_data(b) for b in bookings])

    def post(self, request):
        s = BookingSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        try:
            b = book_group(request.user, d['journey_id'].id, d['seat_ids'], d['from_seq'], d['to_seq'], d['quota'],
                d['confirmed_berths_only'],d['consider_auto_upgrade'])
        except SeatTaken as exc:
            return Response({'error': str(exc)}, status=409)
        return Response(booking_data(b), status=201)

class RazorpayCreateOrderView(APIView):
    def post(self, request, booking_id):
        booking = get_object_or_404(Booking, pk=booking_id, user=request.user)
        expire_journey(booking.journey_id)
        booking, order = create_order(booking_id, request.user)
        return Response({
            'order_id': order['id'], 'amount': order['amount'], 'currency': order['currency'],
            'key_id': settings.RAZORPAY_KEY_ID, 'booking_id': booking.id,
            'train': booking.journey.train.name, 'train_number': booking.journey.train.number,
            'seat': ', '.join(str(m.seat) for m in group_members(booking).select_related('seat') if m.seat),
            'user_name': booking.passenger_name, 'user_email': booking.contact_email, 'user_phone': booking.contact_phone,
        })

class RazorpayVerifyPaymentView(APIView):
    def post(self, request, booking_id):
        get_object_or_404(Booking, pk=booking_id, user=request.user)
        serializer = PaymentVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        booking = confirm_payment(booking_id, request.user,
            order_id=data['razorpay_order_id'], payment_id=data['razorpay_payment_id'],
            signature=data['razorpay_signature'])
        return Response(booking_data(booking))

class PayView(RazorpayVerifyPaymentView):
    """Legacy URL uses the same mandatory verification. No demo bypass."""
    pass

class CancelView(APIView):
    def post(self, request, booking_id):
        get_object_or_404(Booking, pk=booking_id, user=request.user)
        return Response(booking_data(cancel_booking(booking_id, request.user)))


class CancellationPreviewView(APIView):
    def get(self, request, booking_id):
        from .rules import require_cancellation_open
        from rest_framework.exceptions import ValidationError
        b = get_object_or_404(Booking.objects.select_related('journey__train'), pk=booking_id,
                              user=request.user, group_parent__isnull=True)
        allowed = b.status in ['PENDING', 'CONFIRMED', 'WL']
        reason = '' if allowed else 'This booking is no longer active.'
        if allowed:
            try:
                require_cancellation_open(b)
            except ValidationError as exc:
                allowed, reason = False, str(exc.detail[0])
        paid = sum(a.amount_paise for a in b.payment_attempts.filter(state='CAPTURED', refund__isnull=True))
        return Response({'can_cancel': allowed, 'reason': reason,
                         'refund_estimate': format(Decimal(paid if allowed else 0) / 100, '.2f'), 'currency': 'INR',
                         'notice': 'Eligible captured payments are refunded in full under this project policy. Final eligibility is checked again when you confirm. Bank credit is tracked separately.'})

class WaitlistView(APIView):
    def post(self, request):
        s = SegmentSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        b = join_waitlist(request.user, d['journey_id'].id, d['from_seq'], d['to_seq'], d['travel_class'], d['quota'],
            d['confirmed_berths_only'],d['consider_auto_upgrade'])
        return Response(booking_data(b), status=201)

class BookingDetailView(APIView):
    def get(self, request, booking_id):
        b = get_object_or_404(Booking, pk=booking_id, user=request.user, group_parent__isnull=True)
        expire_journey(b.journey_id)
        b.refresh_from_db()
        return Response(booking_data(b))

class PassengerDetailsView(APIView):
    def put(self, request, booking_id):
        b = get_object_or_404(Booking, pk=booking_id, user=request.user, group_parent__isnull=True)
        expire_journey(b.journey_id)
        serializer = PassengerDetailsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(booking_data(save_passengers(b.id, request.user, serializer.validated_data)))

class ReviewView(APIView):
    def post(self, request, booking_id):
        b = get_object_or_404(Booking, pk=booking_id, user=request.user, group_parent__isnull=True)
        expire_journey(b.journey_id)
        return Response(booking_data(accept_review(b.id, request.user)))


class PaymentRecoveryView(APIView):
    def post(self, request, booking_id):
        b = get_object_or_404(Booking, pk=booking_id, user=request.user, group_parent__isnull=True)
        expire_journey(b.journey_id)
        return Response(booking_data(recover_booking(b.id, user=request.user)))

class RazorpayWebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            size = int(request.META.get('CONTENT_LENGTH') or 0)
        except ValueError:
            return Response({'error': 'Invalid content length.'}, status=400)
        if size > 262144:
            return Response({'error': 'Webhook payload is too large.'}, status=413)
        body = request.body
        if len(body) > 262144:
            return Response({'error': 'Webhook payload is too large.'}, status=413)
        outcome = handle_webhook(body, request.headers.get('X-Razorpay-Signature'),
            request.headers.get('X-Razorpay-Event-Id'))
        return Response({'status': outcome})


def private_response(response):
    response['Cache-Control'] = 'private, no-store, max-age=0'
    response['Pragma'] = 'no-cache'
    response['X-Content-Type-Options'] = 'nosniff'
    return response

class ConfirmationView(APIView):
    def get(self, request, booking_id):
        return private_response(Response(confirmation_snapshot(booking_id, request.user)))

class TicketDownloadView(APIView):
    def get(self, request, booking_id):
        snapshot = confirmation_snapshot(booking_id, request.user)
        response = HttpResponse(render_ticket(snapshot), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="Railwise-{snapshot["reference"]}.pdf"'
        return private_response(response)
