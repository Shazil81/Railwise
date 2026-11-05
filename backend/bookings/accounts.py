"""Small account onboarding API; email is contact data, not a verified identity."""
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from rest_framework import serializers
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView


class LoginThrottle(SimpleRateThrottle):
    scope = 'account_login'
    rate = '10/min'

    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}


class SignupThrottle(LoginThrottle):
    scope = 'account_signup'
    rate = '5/hour'


class LoginView(ObtainAuthToken):
    authentication_classes = []
    throttle_classes = [LoginThrottle]

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        response['Cache-Control'] = 'no-store'
        return response


class SignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)
    password_confirm = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)
    email = serializers.EmailField(max_length=254)

    class Meta:
        model = get_user_model()
        fields = ['username', 'email', 'password', 'password_confirm']

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({'password_confirm': 'Passwords do not match.'})
        user = get_user_model()(username=attrs['username'], email=attrs['email'])
        try:
            validate_password(attrs['password'], user=user)
        except ValidationError as exc:
            raise serializers.ValidationError({'password': exc.messages})
        return attrs


class SignupView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [SignupThrottle]

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        values.pop('password_confirm')
        try:
            with transaction.atomic():
                user = get_user_model().objects.create_user(**values)
                token = Token.objects.create(user=user)
                from .account_links import issue_link
                transaction.on_commit(lambda: issue_link(user, 'verify'))
        except IntegrityError:
            raise serializers.ValidationError({'username': 'This username is unavailable.'})
        response = Response({'token': token.key, 'username': user.username}, status=201)
        response['Cache-Control'] = 'no-store'
        return response


class LogoutView(APIView):
    authentication_classes = [TokenAuthentication]

    def post(self, request):
        if isinstance(request.auth, Token):
            request.auth.delete()
        response = Response(status=204)
        response['Cache-Control'] = 'no-store'
        return response
