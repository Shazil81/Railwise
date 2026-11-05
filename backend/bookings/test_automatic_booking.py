from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import close_old_connections
from django.test import TransactionTestCase, override_settings
from rest_framework.exceptions import ValidationError
from . import tests as fixtures
from .models import Booking,Seat
from .services import book_automatically,book_seat,group_members
from .serializers import AutomaticBookingSerializer


class AutomaticBookingTests(TransactionTestCase):
    def setUp(self):fixtures.BookingTests.setUp(self)

    def payload(self,preferences=('LB',)):
        return {'journey_id':self.journey.id,'from_seq':1,'to_seq':5,'travel_class':'SL','quota':'GN',
            'passengers':[{'name':'Demo Traveller','age':25,'gender':'Male','berth_preference':p} for p in preferences],
            'contact_email':'demo@example.invalid','contact_phone':'9999999999'}

    def test_allocates_preferences_without_client_seat_ids(self):
        Seat.objects.create(train=self.train,coach='C1',number=3)
        response=self.client.post('/api/bookings/automatic/',self.payload(('UB','LB')),format='json')
        self.assertEqual(response.status_code,201,response.data)
        self.assertEqual([p['allocated_berth'] for p in response.data['passengers']],['UB','LB'])
        self.assertEqual(response.data['status'],'PENDING')
        self.assertFalse(response.data['ticket_available'])
        self.assertFalse(response.data['razorpay_order_id'])
        self.assertEqual(len({p['seat'] for p in response.data['passengers']}),2)

    def test_insufficient_group_inventory_leaves_no_partial_hold(self):
        response=self.client.post('/api/bookings/automatic/',self.payload(('LB','UB')),format='json')
        self.assertEqual(response.status_code,400)
        self.assertFalse(Booking.objects.exists())

    def test_unsupported_preference_rolls_back_entire_allocation(self):
        Seat.objects.create(train=self.train,coach='A1',number=1,travel_class='2A')
        body=self.payload(('MB',));body['travel_class']='2A'
        self.assertEqual(self.client.post('/api/bookings/automatic/',body,format='json').status_code,400)
        self.assertFalse(Booking.objects.exists())

    def test_sold_out_never_reuses_an_occupied_seat(self):
        book_seat(self.other,self.journey.id,self.seat.id,1,5)
        response=self.client.post('/api/bookings/automatic/',{**self.payload(),'confirmed_berths_only':True},format='json')
        self.assertEqual(response.status_code,400)
        self.assertEqual(Booking.objects.count(),1)

    def test_sold_out_single_passenger_can_waitlist_without_payment(self):
        book_seat(self.other,self.journey.id,self.seat.id,1,5)
        response=self.client.post('/api/bookings/automatic/',self.payload(),format='json')
        self.assertEqual(response.status_code,201)
        self.assertEqual(response.data['status'],'WL')
        self.assertIsNone(response.data['passengers'][0]['seat'])
        self.assertEqual(response.data['passengers'][0]['berth_preference'],'LB')
        self.assertFalse(response.data['ticket_available'])

    def test_requires_login_and_valid_passengers(self):
        self.client.force_authenticate(None)
        self.assertIn(self.client.post('/api/bookings/automatic/',self.payload(),format='json').status_code,[401,403])
        self.client.force_authenticate(self.user)
        for changes in [{'passengers':[]},{'passengers':self.payload()['passengers']*7},{'contact_phone':'123'}]:
            self.assertEqual(self.client.post('/api/bookings/automatic/',{**self.payload(),**changes},format='json').status_code,400)
        self.assertFalse(Booking.objects.exists())

    def test_adjacent_segment_remains_available(self):
        book_seat(self.other,self.journey.id,self.seat.id,1,3)
        body=self.payload();body['from_seq']=3
        self.assertEqual(self.client.post('/api/bookings/automatic/',body,format='json').status_code,201)

    def test_concurrent_requests_have_only_one_winner(self):
        serializer=AutomaticBookingSerializer(data={**self.payload(),'confirmed_berths_only':True});serializer.is_valid(raise_exception=True)
        def allocate(user):
            close_old_connections()
            try:
                try:return book_automatically(user,serializer.validated_data).id
                except ValidationError:return None
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(allocate,[self.user,self.other]))
        self.assertEqual(sum(result is not None for result in results),1)
        self.assertEqual(Booking.objects.filter(status='PENDING').count(),1)

    def test_public_journey_details_support_reload(self):
        self.client.force_authenticate(None)
        response=self.client.get(f'/api/journeys/{self.journey.id}/')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.data['stops'][0]['code'],'S1')

    @override_settings(DEBUG=True)
    def test_demo_setup_and_login_without_resetting_existing_password(self):
        with patch.dict('os.environ',{'DEMO_PASSWORD':'local-demo-password'}):
            call_command('setup_demo_user',stdout=StringIO())
            user=get_user_model().objects.get(username='demo')
            self.assertFalse(user.is_staff)
            self.client.force_authenticate(None)
            self.assertEqual(self.client.post('/api/token/',{'username':'demo','password':'local-demo-password'}).status_code,200)
            with self.assertRaises(CommandError):call_command('setup_demo_user',stdout=StringIO())
            user.refresh_from_db();self.assertTrue(user.check_password('local-demo-password'))

    @override_settings(DEBUG=False)
    def test_demo_setup_refuses_production(self):
        with self.assertRaises(CommandError):call_command('setup_demo_user',stdout=StringIO())
