from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest.mock import patch, MagicMock
import razorpay
from django.contrib.auth import get_user_model
from django.db import IntegrityError, close_old_connections, transaction
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.exceptions import ValidationError
from .models import Booking, Journey, Seat, Station, Train, TrainStop
from .services import book_seat, cancel_booking, confirm_payment, expire_journey, join_waitlist, SeatTaken
from .tasks import expire_unpaid_booking

@override_settings(RAZORPAY_KEY_ID='rzp_test_unit', RAZORPAY_KEY_SECRET='unit-test-secret', PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class BookingTests(TransactionTestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('traveller', password='test-password')
        self.other = get_user_model().objects.create_user('other')
        self.train = Train.objects.create(number='TEST', name='Test train')
        for n in range(1,6):
            station = Station.objects.create(code=f'S{n}', name=f'Station {n}')
            TrainStop.objects.create(train=self.train, station=station, sequence=n, distance_km=(n-1)*100)
        self.seat = Seat.objects.create(train=self.train, coach='C1', number=1)
        self.journey = Journey.objects.create(train=self.train, date=timezone.localdate())
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def hold(self, f=1, t=5):
        b = book_seat(self.user, self.journey.id, self.seat.id, f, t)
        b.passenger_name, b.passenger_age, b.passenger_gender = 'Test Traveller', 25, 'Male'
        b.contact_email, b.contact_phone, b.reviewed_at = 'traveller@example.com', '9999999999', timezone.now()
        b.save(update_fields=['passenger_name', 'passenger_age', 'passenger_gender', 'contact_email', 'contact_phone', 'reviewed_at'])
        return b

    def test_overlap_is_rejected(self):
        self.hold(1,3)
        with self.assertRaises(SeatTaken): self.hold(2,4)

    def test_adjacent_segments_share_a_seat(self):
        self.hold(1,3)
        self.hold(3,5)
        self.assertEqual(Booking.objects.filter(status='PENDING').count(), 2)

    def test_database_constraint_rejects_overlap_without_service(self):
        self.hold(1,3)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Booking.objects.create(user=self.user, journey=self.journey, seat=self.seat,
                from_seq=2, to_seq=4, status='CONFIRMED')

    def test_invalid_route(self):
        for f,t in [(4,2),(2,2),(1,99)]:
            with self.assertRaises(ValidationError): self.hold(f,t)

    def test_foreign_train_seat(self):
        train = Train.objects.create(number='OTHER',name='Other')
        seat = Seat.objects.create(train=train,coach='C1',number=1)
        with self.assertRaises(ValidationError):
            book_seat(self.user,self.journey.id,seat.id,1,5)

    def test_early_expiry_task_does_not_release_live_hold(self):
        b=self.hold()
        expire_unpaid_booking(b.id)
        b.refresh_from_db()
        self.assertEqual(b.status,'PENDING')

    def test_expired_hold_releases_on_availability_read(self):
        b=self.hold()
        Booking.objects.filter(pk=b.id).update(expires_at=timezone.now()-timedelta(seconds=1))
        response=self.client.get(f'/api/journeys/{self.journey.id}/availability/?from=1&to=5')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.data[0]['id'],self.seat.id)
        b.refresh_from_db()
        self.assertEqual(b.status,'EXPIRED')

    def test_expired_payment_rejected_and_expiry_committed(self):
        b=self.hold()
        Booking.objects.filter(pk=b.id).update(expires_at=timezone.now()-timedelta(seconds=1))
        with self.assertRaises(ValidationError): self.confirm(b)
        b.refresh_from_db()
        self.assertEqual(b.status,'EXPIRED')

    def test_payment_retry_is_idempotent(self):
        b=self.hold()
        self.confirm(b)
        self.confirm(b)
        b.refresh_from_db()
        self.assertEqual(b.status,'CONFIRMED')
        self.assertIsNone(b.expires_at)

    def test_waitlist_only_when_full_and_no_duplicates(self):
        with self.assertRaises(ValidationError): join_waitlist(self.user,self.journey.id,1,5)
        self.hold()
        a=join_waitlist(self.other,self.journey.id,1,5)
        b=join_waitlist(self.other,self.journey.id,1,5)
        self.assertEqual(a.id,b.id)

    def test_cancel_promotes_fifo_to_unpaid_hold(self):
        b=self.hold()
        first=join_waitlist(self.other,self.journey.id,1,5)
        second=join_waitlist(self.user,self.journey.id,1,5)
        cancel_booking(b.id,self.user)
        first.refresh_from_db();second.refresh_from_db()
        self.assertEqual(first.status,'PENDING')
        self.assertIsNotNone(first.expires_at)
        self.assertEqual(second.status,'WL')

    def test_promotion_checks_entire_route_not_just_freed_segment(self):
        left=self.hold(1,3);right=self.hold(3,5)
        waiting=join_waitlist(self.other,self.journey.id,1,5)
        cancel_booking(left.id,self.user)
        waiting.refresh_from_db();self.assertEqual(waiting.status,'WL')
        cancel_booking(right.id,self.user)
        waiting.refresh_from_db();self.assertEqual(waiting.status,'PENDING')

    def test_compatible_waitlisted_segments_both_promoted(self):
        b=self.hold()
        a=join_waitlist(self.other,self.journey.id,1,3)
        c=join_waitlist(self.user,self.journey.id,3,5)
        cancel_booking(b.id,self.user)
        a.refresh_from_db();c.refresh_from_db()
        self.assertEqual((a.status,c.status),('PENDING','PENDING'))

    def test_expiry_promotes_waitlist(self):
        b=self.hold()
        wl=join_waitlist(self.other,self.journey.id,1,5)
        Booking.objects.filter(pk=b.id).update(expires_at=timezone.now()-timedelta(seconds=1))
        expire_journey(self.journey.id)
        wl.refresh_from_db();self.assertEqual(wl.status,'PENDING')

    def test_api_invalid_payloads_are_400_not_500(self):
        for payload in [{},{'journey_id':999,'seat_id':self.seat.id,'from_seq':1,'to_seq':5},
                        {'journey_id':self.journey.id,'seat_id':self.seat.id,'from_seq':'bad','to_seq':5}]:
            self.assertEqual(self.client.post('/api/bookings/',payload).status_code,400)
        self.assertEqual(self.client.get(f'/api/journeys/{self.journey.id}/availability/').status_code,400)

    def test_another_users_booking_is_private(self):
        b=self.hold()
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get('/api/bookings/').data,[])
        for action in ['pay','cancel']:
            self.assertEqual(self.client.post(f'/api/bookings/{b.id}/{action}/').status_code,404)

    def test_public_browse_private_booking(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get('/api/journeys/').status_code,200)
        self.assertEqual(self.client.get(f'/api/journeys/{self.journey.id}/availability/?from=1&to=5').status_code,200)
        self.assertEqual(self.client.post('/api/bookings/',{}).status_code,401)

    def test_fifty_concurrent_attempts_have_one_winner(self):
        def attempt(_):
            close_old_connections()
            try:
                self.hold()
                return 'won'
            except SeatTaken:
                return 'taken'
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=10) as pool:
            results=list(pool.map(attempt,range(50)))
        self.assertEqual(results.count('won'),1)
        self.assertEqual(results.count('taken'),49)
        self.assertEqual(Booking.objects.filter(status='PENDING').count(),1)

    def evidence(self, booking, order_id='order_unit', payment_id='pay_unit'):
        import hmac, hashlib
        Booking.objects.filter(pk=booking.id).update(razorpay_order_id=order_id)
        booking.refresh_from_db()
        signature = hmac.new(b'unit-test-secret', f'{order_id}|{payment_id}'.encode(), hashlib.sha256).hexdigest()
        return {'razorpay_order_id': order_id, 'razorpay_payment_id': payment_id, 'razorpay_signature': signature}

    def payment_record(self, booking, **overrides):
        record = {'id': 'pay_unit', 'order_id': 'order_unit', 'amount': int(booking.amount * 100),
                  'currency': 'INR', 'status': 'captured', 'captured': True, 'amount_refunded': 0}
        record.update(overrides)
        return record

    def confirm(self, booking):
        data = self.evidence(booking)
        with patch('bookings.payments.payment_client') as client:
            client.return_value.payment.fetch.return_value = self.payment_record(booking)
            return confirm_payment(booking.id, self.user, payment_id=data['razorpay_payment_id'],
                order_id=data['razorpay_order_id'], signature=data['razorpay_signature'])

    @patch('bookings.payments.payment_client')
    def test_order_creation_and_retry_reuses_order(self, mock_client):
        b = self.hold()
        order = {'id': 'order_unit', 'amount': int(b.amount * 100), 'currency': 'INR'}
        mock_client.return_value.order.create.return_value = order
        mock_client.return_value.order.fetch.return_value = order
        url = f'/api/bookings/{b.id}/create-order/'
        for _ in range(2):
            response = self.client.post(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['order_id'], 'order_unit')
            self.assertNotIn('secret', str(response.data))
        mock_client.return_value.order.create.assert_called_once()
        b.refresh_from_db(); self.assertEqual(b.razorpay_order_id, 'order_unit')

    @patch('bookings.payments.payment_client')
    def test_real_hmac_and_captured_payment_confirm(self, mock_client):
        b = self.hold(); data = self.evidence(b)
        mock_client.return_value.payment.fetch.return_value = self.payment_record(b)
        for endpoint in ['verify-payment', 'pay']:
            response = self.client.post(f'/api/bookings/{b.id}/{endpoint}/', data)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['status'], 'CONFIRMED')
        mock_client.return_value.payment.fetch.assert_called_once_with('pay_unit')
        b.refresh_from_db(); self.assertEqual(b.razorpay_payment_id, 'pay_unit')

    def test_empty_and_partial_payload_cannot_bypass_either_endpoint(self):
        b = self.hold()
        for endpoint in ['pay', 'verify-payment']:
            for payload in [{}, {'razorpay_order_id': 'order_unit'},
                            {'razorpay_order_id': [], 'razorpay_payment_id': {}, 'razorpay_signature': 123}]:
                self.assertEqual(self.client.post(f'/api/bookings/{b.id}/{endpoint}/', payload, format='json').status_code, 400)
        b.refresh_from_db(); self.assertEqual(b.status, 'PENDING')

    @patch('bookings.payments.payment_client')
    def test_wrong_signature_is_rejected_before_gateway_fetch(self, client):
        b = self.hold(); data = self.evidence(b); data['razorpay_signature'] = '0' * 64
        self.assertEqual(self.client.post(f'/api/bookings/{b.id}/verify-payment/', data).status_code, 400)
        client.return_value.payment.fetch.assert_not_called()
        b.refresh_from_db(); self.assertEqual(b.status, 'PENDING')

    def test_valid_payment_for_another_order_cannot_confirm_booking(self):
        b = self.hold(); data = self.evidence(b)
        Booking.objects.filter(pk=b.id).update(razorpay_order_id='order_other')
        self.assertEqual(self.client.post(f'/api/bookings/{b.id}/verify-payment/', data).status_code, 400)
        b.refresh_from_db(); self.assertEqual(b.status, 'PENDING')

    def test_booking_without_saved_order_cannot_be_confirmed(self):
        b = self.hold(); data = self.evidence(b)
        Booking.objects.filter(pk=b.id).update(razorpay_order_id=None)
        self.assertEqual(self.client.post(f'/api/bookings/{b.id}/verify-payment/', data).status_code, 400)

    @patch('bookings.payments.payment_client')
    def test_gateway_payment_must_match_all_trusted_fields(self, client):
        b = self.hold(); data = self.evidence(b)
        for mismatch in [{'id': 'pay_other'}, {'order_id': 'order_other'}, {'amount': 1},
                         {'currency': 'USD'}, {'status': 'authorized'}, {'status': 'failed'},
                         {'captured': False}, {'amount_refunded': 100}]:
            with self.subTest(mismatch=mismatch):
                client.return_value.payment.fetch.return_value = self.payment_record(b, **mismatch)
                self.assertEqual(self.client.post(f'/api/bookings/{b.id}/verify-payment/', data).status_code, 400)
                b.refresh_from_db(); self.assertEqual(b.status, 'PENDING')

    @patch('bookings.payments.payment_client')
    def test_expired_and_cancelled_holds_cannot_be_paid(self, client):
        b = self.hold(); data = self.evidence(b)
        Booking.objects.filter(pk=b.id).update(expires_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(self.client.post(f'/api/bookings/{b.id}/verify-payment/', data).status_code, 400)
        b.refresh_from_db(); self.assertEqual(b.status, 'EXPIRED')
        Booking.objects.filter(pk=b.id).update(status='CANCELLED')
        self.assertEqual(self.client.post(f'/api/bookings/{b.id}/verify-payment/', data).status_code, 400)
        client.return_value.payment.fetch.assert_not_called()

    @patch('bookings.payments.payment_client')
    def test_hold_expiring_during_gateway_fetch_is_not_confirmed(self, client):
        from unittest.mock import patch as clock_patch
        b = self.hold(); data = self.evidence(b)
        future = b.expires_at + timedelta(seconds=1)
        def fetch(_):
            clock = clock_patch('bookings.payments.timezone.now', return_value=future)
            clock.start(); self.addCleanup(clock.stop)
            return self.payment_record(b)
        client.return_value.payment.fetch.side_effect = fetch
        self.assertEqual(self.client.post(f'/api/bookings/{b.id}/verify-payment/', data).status_code, 400)
        b.refresh_from_db(); self.assertEqual(b.status, 'PENDING')

    @override_settings(RAZORPAY_KEY_ID='', RAZORPAY_KEY_SECRET='')
    def test_missing_configuration_fails_closed(self):
        b = self.hold(); data = self.evidence(b)
        for endpoint in ['create-order', 'verify-payment']:
            self.assertEqual(self.client.post(f'/api/bookings/{b.id}/{endpoint}/', data).status_code, 503)
        b.refresh_from_db(); self.assertEqual(b.status, 'PENDING')

    @patch('bookings.payments.payment_client')
    def test_gateway_failure_does_not_leak_exception_or_confirm(self, client):
        import requests
        b = self.hold(); data = self.evidence(b)
        client.return_value.payment.fetch.side_effect = requests.Timeout('private-gateway-details')
        response = self.client.post(f'/api/bookings/{b.id}/verify-payment/', data)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('private-gateway-details', str(response.data))
        b.refresh_from_db(); self.assertEqual(b.status, 'PENDING')

    @patch('bookings.payments.payment_client')
    def test_changed_payment_on_confirmed_booking_is_rejected(self, client):
        import hmac, hashlib
        b = self.hold(); data = self.evidence(b)
        client.return_value.payment.fetch.return_value = self.payment_record(b)
        self.assertEqual(self.client.post(f'/api/bookings/{b.id}/verify-payment/', data).status_code, 200)
        data['razorpay_payment_id'] = 'pay_other'
        data['razorpay_signature'] = hmac.new(b'unit-test-secret', b'order_unit|pay_other', hashlib.sha256).hexdigest()
        self.assertEqual(self.client.post(f'/api/bookings/{b.id}/verify-payment/', data).status_code, 400)

    def test_payment_and_order_ids_are_database_unique(self):
        b = self.hold(1, 3)
        Booking.objects.filter(pk=b.id).update(razorpay_order_id='order_unit', razorpay_payment_id='pay_unit')
        other = self.hold(3, 5)
        for fields in [{'razorpay_payment_id': 'pay_unit'}, {'razorpay_order_id': 'order_unit'}]:
            with self.assertRaises(IntegrityError), transaction.atomic():
                Booking.objects.filter(pk=other.id).update(**fields)

    @patch('bookings.payments.payment_client')
    def test_used_payment_cannot_confirm_a_second_booking(self, client):
        b = self.hold(1, 3); data = self.evidence(b)
        client.return_value.payment.fetch.return_value = self.payment_record(b)
        self.assertEqual(self.client.post(f'/api/bookings/{b.id}/verify-payment/', data).status_code, 200)
        other = self.hold(3, 5)
        data = self.evidence(other, order_id='order_other')
        self.assertEqual(self.client.post(f'/api/bookings/{other.id}/verify-payment/', data).status_code, 400)
        other.refresh_from_db(); self.assertEqual(other.status, 'PENDING')

    def test_payment_endpoints_are_owner_scoped(self):
        b = self.hold(); data = self.evidence(b)
        self.client.force_authenticate(self.other)
        for endpoint in ['pay', 'create-order', 'verify-payment']:
            self.assertEqual(self.client.post(f'/api/bookings/{b.id}/{endpoint}/', data).status_code, 404)

    @patch('bookings.payments.payment_client')
    def test_invalid_gateway_order_is_not_saved(self, client):
        b = self.hold()
        client.return_value.order.create.return_value = {'id': 'order_unit', 'amount': 1, 'currency': 'USD'}
        self.assertEqual(self.client.post(f'/api/bookings/{b.id}/create-order/').status_code, 503)
        b.refresh_from_db(); self.assertIsNone(b.razorpay_order_id)

@override_settings(RAZORPAY_KEY_ID='rzp_test_unit', RAZORPAY_KEY_SECRET='unit-test-secret', PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class GroupCheckoutTests(TransactionTestCase):
    setUp = BookingTests.setUp

    def group(self):
        self.second = Seat.objects.create(train=self.train, coach='C1', number=2)
        response = self.client.post('/api/bookings/', {'journey_id': self.journey.id,
            'seat_ids': [self.seat.id, self.second.id], 'from_seq': 1, 'to_seq': 5}, format='json')
        self.assertEqual(response.status_code, 201)
        return Booking.objects.get(pk=response.data['booking_id'])

    def details(self, b):
        from .services import group_members
        return {'passengers': [{'booking_id': m.id, 'name': f'Test Traveller {chr(65+i)}', 'age': 25+i,
            'gender': 'Prefer not to say'} for i,m in enumerate(group_members(b))],
            'contact_email': 'group@example.com', 'contact_phone': '9999999999'}

    def ready(self, b):
        response = self.client.put(f'/api/bookings/{b.id}/passengers/', self.details(b), format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.post(f'/api/bookings/{b.id}/review/').status_code, 200)
        b.refresh_from_db()

    def test_group_has_two_seats_one_deadline_and_total(self):
        from .services import group_members
        b = self.group(); members = list(group_members(b))
        self.assertEqual(len(members), 2)
        self.assertEqual(members[0].expires_at, members[1].expires_at)
        response = self.client.get(f'/api/bookings/{b.id}/')
        self.assertEqual(response.data['amount'], 560)
        self.assertEqual(response.data['fare_breakdown']['total'], '560.00')
        self.assertEqual(len(self.client.get('/api/bookings/').data), 1)

    def test_group_hold_is_atomic_when_second_seat_is_taken(self):
        second = Seat.objects.create(train=self.train,coach='C1',number=2)
        book_seat(self.other,self.journey.id,second.id,1,5)
        response = self.client.post('/api/bookings/', {'journey_id': self.journey.id,
            'seat_ids': [self.seat.id,second.id], 'from_seq': 1,'to_seq':5}, format='json')
        self.assertEqual(response.status_code,409)
        self.assertEqual(Booking.objects.count(),1)
        self.assertFalse(Booking.objects.filter(user=self.user).exists())

    def test_duplicate_and_oversized_seat_lists_are_rejected(self):
        for seats in [[],[self.seat.id,self.seat.id],list(range(1,8))]:
            response = self.client.post('/api/bookings/', {'journey_id': self.journey.id,
                'seat_ids': seats,'from_seq':1,'to_seq':5}, format='json')
            self.assertEqual(response.status_code,400)
        self.assertEqual(Booking.objects.count(),0)

    def test_details_and_review_are_required_before_order(self):
        b = self.group()
        self.assertEqual(self.client.post(f'/api/bookings/{b.id}/create-order/').status_code,400)
        self.assertEqual(self.client.post(f'/api/bookings/{b.id}/review/').status_code,400)
        self.assertEqual(self.client.put(f'/api/bookings/{b.id}/passengers/', self.details(b), format='json').status_code,200)
        self.assertEqual(self.client.post(f'/api/bookings/{b.id}/create-order/').status_code,400)

    def test_invalid_passenger_or_contact_does_not_save_any_details(self):
        b = self.group()
        for field,value in [('age',0),('age',121),('name','12345'),('gender','invalid')]:
            data = self.details(b); data['passengers'][1][field]=value
            self.assertEqual(self.client.put(f'/api/bookings/{b.id}/passengers/',data,format='json').status_code,400)
        for field,value in [('contact_email','invalid'),('contact_phone','123')]:
            data=self.details(b);data[field]=value
            self.assertEqual(self.client.put(f'/api/bookings/{b.id}/passengers/',data,format='json').status_code,400)
        b.refresh_from_db();self.assertEqual(b.passenger_name,'')

    def test_every_seat_needs_exactly_one_passenger(self):
        b=self.group();data=self.details(b)
        for passengers in [data['passengers'][:1],[data['passengers'][0]]*2,
                           [dict(data['passengers'][0], booking_id=99999),data['passengers'][1]]]:
            self.assertEqual(self.client.put(f'/api/bookings/{b.id}/passengers/',dict(data,passengers=passengers),format='json').status_code,400)
        self.assertFalse(Booking.objects.exclude(passenger_name='').exists())

    def test_details_persist_and_edit_invalidates_review(self):
        b=self.group();self.ready(b)
        response=self.client.get(f'/api/bookings/{b.id}/')
        self.assertEqual(response.data['contact_email'],'group@example.com')
        self.assertEqual(response.data['passengers'][1]['name'],'Test Traveller B')
        self.assertIsNotNone(response.data['reviewed_at'])
        self.assertEqual(self.client.put(f'/api/bookings/{b.id}/passengers/',self.details(b),format='json').status_code,200)
        b.refresh_from_db();self.assertIsNone(b.reviewed_at)

    @patch('bookings.payments.payment_client')
    def test_group_order_charges_backend_total_and_locks_details(self,client):
        b=self.group();self.ready(b)
        client.return_value.order.create.return_value={'id':'order_unit','amount':56000,'currency':'INR'}
        response=self.client.post(f'/api/bookings/{b.id}/create-order/', {'amount':1},format='json')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.data['amount'],56000)
        self.assertEqual(response.data['user_email'],'group@example.com')
        self.assertEqual(response.data['user_phone'],'9999999999')
        self.assertEqual(client.return_value.order.create.call_args.kwargs['data']['amount'],56000)
        self.assertEqual(self.client.put(f'/api/bookings/{b.id}/passengers/',self.details(b),format='json').status_code,400)

    @patch('bookings.payments.payment_client')
    def test_one_verified_payment_confirms_every_passenger(self,client):
        b=self.group();self.ready(b)
        data=BookingTests.evidence(self,b)
        client.return_value.payment.fetch.return_value=BookingTests.payment_record(self,b,amount=56000)
        response=self.client.post(f'/api/bookings/{b.id}/verify-payment/',data,format='json')
        self.assertEqual(response.status_code,200)
        self.assertEqual(Booking.objects.filter(status='CONFIRMED').count(),2)
        self.assertEqual(Booking.objects.filter(razorpay_payment_id='pay_unit').count(),1)
        self.assertEqual(response.data['amount'],560)

    @patch('bookings.payments.payment_client')
    def test_single_fare_payment_cannot_confirm_group(self,client):
        b=self.group();self.ready(b);data=BookingTests.evidence(self,b)
        client.return_value.payment.fetch.return_value=BookingTests.payment_record(self,b)
        self.assertEqual(self.client.post(f'/api/bookings/{b.id}/verify-payment/',data,format='json').status_code,400)
        self.assertEqual(Booking.objects.filter(status='PENDING').count(),2)

    def test_group_cancellation_releases_all_seats(self):
        b=self.group()
        self.assertEqual(self.client.post(f'/api/bookings/{b.id}/cancel/').status_code,200)
        self.assertEqual(Booking.objects.filter(status='CANCELLED').count(),2)
        self.assertEqual(len(self.client.get(f'/api/journeys/{self.journey.id}/availability/?from=1&to=5').data),2)

    def test_group_expiry_releases_all_seats(self):
        b=self.group()
        Booking.objects.update(expires_at=timezone.now()-timedelta(seconds=1))
        self.client.get(f'/api/bookings/{b.id}/')
        self.assertEqual(Booking.objects.filter(status='EXPIRED').count(),2)

    def test_group_members_cannot_be_paid_or_cancelled_independently(self):
        b=self.group();child=b.companions.get()
        for endpoint in ['create-order','cancel','review']:
            self.assertEqual(self.client.post(f'/api/bookings/{child.id}/{endpoint}/').status_code,400 if endpoint!='review' else 404)
        self.assertEqual(Booking.objects.filter(status='PENDING').count(),2)

    def test_passenger_details_are_owner_scoped(self):
        b=self.group();data=self.details(b);self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(f'/api/bookings/{b.id}/').status_code,404)
        self.assertEqual(self.client.put(f'/api/bookings/{b.id}/passengers/',data,format='json').status_code,404)
        self.assertEqual(self.client.post(f'/api/bookings/{b.id}/review/').status_code,404)
