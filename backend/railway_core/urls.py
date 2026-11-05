"""
URL configuration for railway_core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from bookings.accounts import LoginView, SignupView, LogoutView
from bookings.account_links import RequestLinkView, RequestResetView, ConsumeLinkView, ResetPasswordView, AccountStatusView
from bookings.operations import operations_dashboard, retry_email_view
from .health import health

urlpatterns = [
    path('api/health/', health),
    path('admin/operations/', admin.site.admin_view(operations_dashboard), name='railwise-operations'),
    path('admin/operations/emails/<int:notification_id>/retry/', admin.site.admin_view(retry_email_view), name='railwise-email-retry'),
    path("admin/", admin.site.urls),
    path("api/token/", LoginView.as_view()),
    path("api/accounts/signup/", SignupView.as_view()),
    path("api/accounts/logout/", LogoutView.as_view()),
    path("api/accounts/me/", AccountStatusView.as_view()),
    path("api/accounts/request-verification/", RequestLinkView.as_view()),
    path("api/accounts/verify-email/", ConsumeLinkView.as_view()),
    path("api/accounts/forgot-password/", RequestResetView.as_view()),
    path("api/accounts/reset-password/", ResetPasswordView.as_view()),
    path("api/", include("bookings.urls")),
]
