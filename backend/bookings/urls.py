from django.urls import path
from . import views
from .discovery import StationSearchView, TrainSearchView, JourneyQuoteView
from .inventory_stream import InventoryStreamView

urlpatterns = [
    path('inventory/stream/',InventoryStreamView.as_view()),
    path('stations/search/', StationSearchView.as_view()),
    path('trains/search/', TrainSearchView.as_view()),
    path('journeys/<int:journey_id>/quote/', JourneyQuoteView.as_view()),
    path('journeys/', views.JourneyView.as_view()),
    path('journeys/<int:journey_id>/', views.JourneyDetailView.as_view()),
    path('bookings/automatic/', views.AutomaticBookingView.as_view()),
    path('journeys/<int:journey_id>/availability/', views.AvailabilityView.as_view()),
    path('bookings/', views.BookView.as_view()),
    path('bookings/<int:booking_id>/pay/', views.PayView.as_view()),
    path('bookings/<int:booking_id>/create-order/', views.RazorpayCreateOrderView.as_view()),
    path('bookings/<int:booking_id>/verify-payment/', views.RazorpayVerifyPaymentView.as_view()),
    path('bookings/<int:booking_id>/cancel/', views.CancelView.as_view()),
    path('bookings/<int:booking_id>/cancel-preview/', views.CancellationPreviewView.as_view()),
    path('bookings/<int:booking_id>/', views.BookingDetailView.as_view()),
    path('bookings/<int:booking_id>/passengers/', views.PassengerDetailsView.as_view()),
    path('bookings/<int:booking_id>/review/', views.ReviewView.as_view()),
    path('bookings/<int:booking_id>/recover-payment/', views.PaymentRecoveryView.as_view()),
    path('bookings/<int:booking_id>/confirmation/', views.ConfirmationView.as_view()),
    path('bookings/<int:booking_id>/ticket.pdf', views.TicketDownloadView.as_view()),
    path('webhooks/razorpay/', views.RazorpayWebhookView.as_view()),
    path('waitlist/', views.WaitlistView.as_view()),
]
