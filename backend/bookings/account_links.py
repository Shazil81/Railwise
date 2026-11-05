"""Single-use hashed email links. No bearer link is returned in an API response."""
import hashlib
import secrets
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from .accounts import LoginThrottle
from .models import AccountEmail, AccountLink, AccountLinkDelivery

GENERIC = 'If the account is eligible, an email will arrive shortly. Check spam or request another link if needed.'


def private(data, status=200):
    response = Response(data, status=status)
    response['Cache-Control'] = 'no-store'
    response['Referrer-Policy'] = 'no-referrer'
    return response


class LinkThrottle(LoginThrottle):
    scope = 'account_links'
    rate = '5/hour'


class LinkInput(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField(max_length=254)


def issue_link(user, purpose):
    raw = secrets.token_urlsafe(32)
    with transaction.atomic():
        user = get_user_model().objects.select_for_update().get(pk=user.pk)
        if not user.is_active or not user.email:
            return
        state, _ = AccountEmail.objects.get_or_create(user=user)
        verified = state.verified_email.casefold() == user.email.casefold()
        if (purpose == 'reset' and (not verified or not user.has_usable_password())) or (purpose == 'verify' and verified):
            return
        AccountLink.objects.filter(user=user, purpose=purpose, used_at__isnull=True).update(used_at=timezone.now())
        AccountLinkDelivery.objects.filter(link__user=user,link__purpose=purpose,state__in=['QUEUED','RETRY']).update(state='SKIPPED',token_ciphertext='')
        link=AccountLink.objects.create(user=user, purpose=purpose, email=user.email,
            password_digest=hashlib.sha256(user.password.encode()).hexdigest(),
            digest=hashlib.sha256(raw.encode()).hexdigest(),
            expires_at=timezone.now()+timedelta(seconds=settings.ACCOUNT_LINK_TIMEOUT))
        from .account_mail import token_cipher
        AccountLinkDelivery.objects.create(link=link,token_ciphertext=token_cipher().encrypt(raw.encode()).decode())


class RequestLinkView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [LinkThrottle]
    purpose = 'verify'

    def post(self, request):
        serializer = LinkInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        user = get_user_model().objects.filter(username=values['username'], email__iexact=values['email'], is_active=True).first()
        if user:
            issue_link(user, self.purpose)
        return private({'detail': GENERIC}, 202)


class RequestResetView(RequestLinkView):
    purpose = 'reset'


class ConsumeInput(serializers.Serializer):
    token = serializers.CharField(max_length=100)
    password = serializers.CharField(required=False, max_length=128, trim_whitespace=False)
    password_confirm = serializers.CharField(required=False, max_length=128, trim_whitespace=False)


class ConsumeLinkView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [LoginThrottle]
    purpose = 'verify'

    def post(self, request):
        serializer = ConsumeInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        digest = hashlib.sha256(data['token'].encode()).hexdigest()
        candidate = AccountLink.objects.filter(digest=digest, purpose=self.purpose).first()
        invalid = {'token': 'This link is invalid, expired or already used. Request a new link.'}
        if not candidate:
            raise serializers.ValidationError(invalid)
        with transaction.atomic():
            user = get_user_model().objects.select_for_update().get(pk=candidate.user_id)
            link = AccountLink.objects.select_for_update().get(pk=candidate.pk)
            if link.used_at or link.expires_at <= timezone.now() or not user.is_active or link.email.casefold() != user.email.casefold() or link.password_digest != hashlib.sha256(user.password.encode()).hexdigest():
                raise serializers.ValidationError(invalid)
            state, _ = AccountEmail.objects.get_or_create(user=user)
            if self.purpose == 'reset':
                if state.verified_email.casefold() != user.email.casefold():
                    raise serializers.ValidationError(invalid)
                password = data.get('password', '')
                if not password or password != data.get('password_confirm'):
                    raise serializers.ValidationError({'password_confirm': 'Enter matching passwords.'})
                try:
                    validate_password(password, user=user)
                except ValidationError as exc:
                    raise serializers.ValidationError({'password': exc.messages})
                user.set_password(password)
                user.save(update_fields=['password'])
                Token.objects.filter(user=user).delete()
                AccountLink.objects.filter(user=user, used_at__isnull=True).update(used_at=timezone.now())
            else:
                state.verified_email = user.email
                state.save(update_fields=['verified_email'])
                from .models import BookingEmail
                BookingEmail.objects.filter(booking__user=user, state='WAITING_VERIFICATION').update(state='QUEUED', next_attempt_at=timezone.now())
            link.used_at = timezone.now()
            link.save(update_fields=['used_at'])
            AccountLinkDelivery.objects.filter(link__user=user,link__used_at__isnull=False).exclude(state='SENT').update(state='SKIPPED',token_ciphertext='')
        return private({'detail': 'Email verified. You can sign in.' if self.purpose == 'verify' else 'Password reset. Sign in with your new password.'})


class ResetPasswordView(ConsumeLinkView):
    purpose = 'reset'


class AccountStatusView(APIView):
    def get(self, request):
        state = AccountEmail.objects.filter(user=request.user).first()
        return private({'username': request.user.username, 'email': request.user.email,
            'email_verified': bool(state and state.verified_email and state.verified_email.casefold() == request.user.email.casefold())})
