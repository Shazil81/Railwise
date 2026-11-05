from io import BytesIO
from datetime import timedelta
from unittest.mock import patch
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from pypdf import PdfReader
from . import tests as fixtures
from .models import Booking, PaymentAttempt, Refund, Seat
from .services import book_group, cancel_booking
from .payments import confirm_payment

@override_settings(RAZORPAY_KEY_ID='rzp_test_unit', RAZORPAY_KEY_SECRET='unit-test-secret',
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class TicketTests(TransactionTestCase):
    setUp = fixtures.BookingTests.setUp
    group = fixtures.GroupCheckoutTests.group
    details = fixtures.GroupCheckoutTests.details
    ready = fixtures.GroupCheckoutTests.ready

    def confirmed(self, six=False):
        if six:
            seats=[self.seat]+[Seat.objects.create(train=self.train,coach='C1',number=n) for n in range(2,7)]
            b=book_group(self.user,self.journey.id,[s.id for s in seats],1,5)
        else:
            b=self.group()
        self.ready(b)
        data=fixtures.BookingTests.evidence(self,b)
        amount=int(sum(m.amount for m in [b,*b.companions.all()])*100)
        with patch('bookings.payments.payment_client') as client:
            client.return_value.payment.fetch.return_value=fixtures.BookingTests.payment_record(self,b,amount=amount)
            return confirm_payment(b.id,self.user,payment_id=data['razorpay_payment_id'],
                order_id=data['razorpay_order_id'],signature=data['razorpay_signature'])

    def test_confirmation_contains_all_passengers_journey_and_payment(self):
        b=self.confirmed()
        response=self.client.get(f'/api/bookings/{b.id}/confirmation/')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.data['reference'],f'RW-{b.id:08d}')
        self.assertEqual(len(response.data['passengers']),2)
        self.assertEqual(response.data['passengers'][1]['coach'],'C1')
        self.assertEqual(response.data['passengers'][1]['country'],'India')
        self.assertEqual(response.data['passengers'][1]['seat_number'],2)
        self.assertEqual(response.data['fare']['total'],'560.00')
        self.assertEqual(response.data['payment']['status'],'CAPTURED')
        self.assertEqual(response.data['contact']['email'],'group@example.com')
        self.assertNotIn('razorpay_signature',str(response.data))
        self.assertNotIn('unit-test-secret',str(response.data))
        self.assertIn('no-store',response['Cache-Control'])

    def test_pdf_download_contains_complete_ticket_and_private_headers(self):
        b=self.confirmed()
        response=self.client.get(f'/api/bookings/{b.id}/ticket.pdf')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response['Content-Type'],'application/pdf')
        self.assertIn('attachment;',response['Content-Disposition'])
        self.assertIn(f'RW-{b.id:08d}',response['Content-Disposition'])
        self.assertIn('no-store',response['Cache-Control'])
        self.assertEqual(response['X-Content-Type-Options'],'nosniff')
        self.assertTrue(response.content.startswith(b'%PDF'))
        reader=PdfReader(BytesIO(response.content))
        text='\n'.join(page.extract_text() for page in reader.pages)
        for value in ['Test Traveller A','Test Traveller B','C1','560.00','pay_unit','order_unit','group@example.com','NOT VALID FOR TRAVEL','COACH','SEAT','BERTH TYPE','TOTAL PAID','CAPTURED - verified']:
            self.assertIn(value,text)
        self.assertEqual(len(reader.pages),1)

    def test_pdf_and_booking_page_use_same_overnight_schedule_and_class(self):
        b = self.confirmed()
        self.train.stops.filter(sequence=1).update(day=2, departure='23:30')
        self.train.stops.filter(sequence=5).update(day=3, arrival='07:15')
        booked = timezone.now() - timedelta(days=2)
        Booking.objects.filter(pk=b.pk).update(created_at=booked)
        page = self.client.get(f'/api/bookings/{b.id}/').data
        snapshot = self.client.get(f'/api/bookings/{b.id}/confirmation/').data
        for field in ['departure_at', 'arrival_at', 'duration_minutes', 'class_name']:
            self.assertEqual(snapshot[field], page[field])
        self.assertEqual(snapshot['duration_minutes'], 465)
        response = self.client.get(f'/api/bookings/{b.id}/ticket.pdf')
        self.assertEqual(response.status_code, 200)
        text = ' '.join(p.extract_text() for p in PdfReader(BytesIO(response.content)).pages)
        for value in ['DEPARTURE / FROM', 'ARRIVAL / TO', '23:30 IST', '07:15 IST',
                      'Duration: 7h 45m', page['class_name'], 'Booked on:', 'JOURNEY DATE',
                      (self.journey.date + timedelta(days=1)).strftime('%d %B %Y'),
                      (self.journey.date + timedelta(days=2)).strftime('%d %b %Y'),
                      timezone.localtime(booked).strftime('%d %b %Y %H:%M IST')]:
            self.assertIn(value, text)

    def test_pdf_does_not_invent_missing_departure_arrival_or_duration(self):
        b = self.confirmed()
        response = self.client.get(f'/api/bookings/{b.id}/ticket.pdf')
        self.assertEqual(response.status_code, 200)
        text = ' '.join(p.extract_text() for p in PdfReader(BytesIO(response.content)).pages)
        self.assertEqual(text.count('Time not recorded'), 2)
        self.assertIn('Duration: Not recorded', text)
        self.assertNotIn('23:59', text)

    def test_six_long_passenger_names_wrap_and_continue_without_loss(self):
        b=self.confirmed(six=True)
        members=[b,*b.companions.order_by('id')]
        for index,member in enumerate(members):
            member.passenger_name='Alexandria '*8+chr(65+index)
            member.save(update_fields=['passenger_name'])
        response=self.client.get(f'/api/bookings/{b.id}/ticket.pdf')
        self.assertEqual(response.status_code,200)
        reader=PdfReader(BytesIO(response.content))
        text=' '.join(' '.join(page.extract_text().split()) for page in reader.pages)
        for member in members:
            self.assertIn(member.passenger_name,text)
        self.assertIn('1680.00',text)
        self.assertGreaterEqual(len(reader.pages),2)
        self.assertLessEqual(len(reader.pages),3)

    def test_anonymous_and_other_users_cannot_access_ticket(self):
        b=self.confirmed()
        self.client.force_authenticate(self.other)
        for suffix in ['confirmation/','ticket.pdf']:
            self.assertEqual(self.client.get(f'/api/bookings/{b.id}/{suffix}').status_code,404)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(f'/api/bookings/{b.id}/ticket.pdf').status_code,401)

    def test_unconfirmed_cancelled_expired_waitlisted_have_no_ticket(self):
        b=self.confirmed()
        for state in ['PENDING','CANCELLED','EXPIRED','WL']:
            Booking.objects.filter(pk=b.id).update(status=state)
            for suffix in ['confirmation/','ticket.pdf']:
                self.assertEqual(self.client.get(f'/api/bookings/{b.id}/{suffix}').status_code,409)

    def test_status_alone_is_not_payment_evidence(self):
        b=self.confirmed()
        PaymentAttempt.objects.filter(booking=b).update(state='AUTHORIZED')
        self.assertEqual(self.client.get(f'/api/bookings/{b.id}/ticket.pdf').status_code,409)
        self.assertFalse(self.client.get(f'/api/bookings/{b.id}/').data['ticket_available'])

    def test_ticket_denied_when_refund_is_pending_or_processed(self):
        b=self.confirmed();attempt=PaymentAttempt.objects.get(booking=b)
        Refund.objects.create(attempt=attempt,amount_paise=56000,state='PROCESSING',reason='Provider refund started')
        self.assertEqual(self.client.get(f'/api/bookings/{b.id}/ticket.pdf').status_code,409)

    def test_cancellation_revokes_new_downloads(self):
        b=self.confirmed()
        self.assertEqual(self.client.get(f'/api/bookings/{b.id}/ticket.pdf').status_code,200)
        cancel_booking(b.id,self.user)
        self.assertEqual(self.client.get(f'/api/bookings/{b.id}/ticket.pdf').status_code,409)

    def test_incomplete_group_or_missing_route_cannot_generate_ticket(self):
        b=self.confirmed()
        b.companions.update(passenger_name='')
        self.assertEqual(self.client.get(f'/api/bookings/{b.id}/confirmation/').status_code,409)
        b.companions.update(passenger_name='Test Traveller B')
        self.train.stops.filter(sequence=5).delete()
        self.assertEqual(self.client.get(f'/api/bookings/{b.id}/ticket.pdf').status_code,409)

    def test_companion_cannot_download_a_partial_ticket(self):
        b=self.confirmed();child=b.companions.get()
        self.assertEqual(self.client.get(f'/api/bookings/{child.id}/ticket.pdf').status_code,404)

    def test_train_name_is_escaped_in_pdf(self):
        b=self.confirmed();self.train.name='Rail <Demo> & Partners';self.train.save()
        response=self.client.get(f'/api/bookings/{b.id}/ticket.pdf')
        text=' '.join(p.extract_text() for p in PdfReader(BytesIO(response.content)).pages)
        self.assertIn('Rail <Demo> & Partners',text)
