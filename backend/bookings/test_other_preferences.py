from django.test import TransactionTestCase
from . import tests as fixtures
from .models import Seat,Booking


class OtherPreferenceTests(TransactionTestCase):
    def setUp(self):fixtures.BookingTests.setUp(self)

    def body(self,**changes):
        body={'journey_id':self.journey.id,'from_seq':1,'to_seq':5,'travel_class':'SL','quota':'GN',
            'passengers':[{'name':'Demo Traveller','age':25,'gender':'Male','country':'Nepal','berth_preference':'LB'}],
            'contact_email':'demo@example.invalid','contact_phone':'9999999999',
            'preferred_coach':'C2','gstin':'27ABCDE1234F1Z5','confirmed_berths_only':True,'consider_auto_upgrade':True}
        return {**body,**changes}

    def test_country_and_other_preferences_persist_and_coach_is_considered(self):
        preferred=Seat.objects.create(train=self.train,coach='C2',number=1)
        response=self.client.post('/api/bookings/automatic/',self.body(),format='json')
        self.assertEqual(response.status_code,201,response.data)
        self.assertEqual(response.data['passengers'][0]['seat'],str(preferred))
        self.assertEqual(response.data['passengers'][0]['country'],'Nepal')
        self.assertEqual(response.data['preferred_coach'],'C2')
        self.assertEqual(response.data['gstin'],'27ABCDE1234F1Z5')
        self.assertTrue(response.data['confirmed_berths_only'])
        self.assertTrue(response.data['consider_auto_upgrade'])
        self.assertEqual(self.client.get(f"/api/bookings/{response.data['booking_id']}/").data['gstin'],'27ABCDE1234F1Z5')

    def test_unavailable_coach_falls_back_within_selected_class(self):
        response=self.client.post('/api/bookings/automatic/',self.body(preferred_coach='Z9'),format='json')
        self.assertEqual(response.status_code,201)
        self.assertEqual(response.data['passengers'][0]['seat'],str(self.seat))
        self.assertEqual(response.data['preferred_coach'],'Z9')

    def test_invalid_country_coach_and_gstin_rejected_before_holding(self):
        for changes in [{'preferred_coach':'../bad'},{'gstin':'INVALID'},
                {'passengers':[{**self.body()['passengers'][0],'country':'12345'}]}]:
            response=self.client.post('/api/bookings/automatic/',self.body(**changes),format='json')
            self.assertEqual(response.status_code,400,response.data)
            self.assertFalse(Booking.objects.exists())

    def test_existing_clients_default_to_india_and_can_leave_optional_fields_blank(self):
        body=self.body(preferred_coach='',gstin='');body['passengers'][0].pop('country')
        response=self.client.post('/api/bookings/automatic/',body,format='json')
        self.assertEqual(response.status_code,201,response.data)
        self.assertEqual(response.data['passengers'][0]['country'],'India')

    def test_edits_preserve_omitted_country_and_order_locks_other_preferences(self):
        response=self.client.post('/api/bookings/automatic/',self.body(),format='json')
        b=Booking.objects.get(pk=response.data['booking_id']);b.razorpay_order_id='order_pref_locked';b.save()
        payload={key:value for key,value in self.body().items() if key in ['contact_email','contact_phone','gstin','preferred_coach']}
        payload['passengers']=[{**self.body()['passengers'][0],'booking_id':b.id}]
        self.assertEqual(self.client.put(f'/api/bookings/{b.id}/passengers/',payload,format='json').status_code,400)
        b.refresh_from_db();self.assertEqual(b.passenger_country,'Nepal')
