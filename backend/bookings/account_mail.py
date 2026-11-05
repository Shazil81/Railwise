"""Durable account mail. Tokens stay encrypted until SMTP acceptance or expiry."""
import base64
import hashlib
import hmac
import logging
from datetime import timedelta
from urllib.parse import urlencode
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from .models import AccountEmail, AccountLink, AccountLinkDelivery

logger = logging.getLogger(__name__)


def token_cipher():
    key = hmac.new(settings.SECRET_KEY.encode(), b'railwise:account-email-outbox:v1', hashlib.sha256).digest()
    return Fernet(base64.urlsafe_b64encode(key))


@transaction.atomic
def deliver_account_email(delivery_id):
    candidate = AccountLinkDelivery.objects.filter(pk=delivery_id).values('link_id','link__user_id').first()
    if not candidate:
        return 'MISSING'
    # Same user-first order as link issue/consume; concurrent dispatchers serialize.
    user = get_user_model().objects.select_for_update().get(pk=candidate['link__user_id'])
    link = AccountLink.objects.select_for_update().get(pk=candidate['link_id'])
    item = AccountLinkDelivery.objects.select_for_update().get(pk=delivery_id)
    if item.state not in ['QUEUED','RETRY']:
        return item.state
    now = timezone.now()
    verified = AccountEmail.objects.filter(user=user,verified_email__iexact=user.email).exists()
    stale = (not user.is_active or not user.has_usable_password() or link.used_at or link.expires_at <= now
             or link.email.casefold() != user.email.casefold()
             or link.password_digest != hashlib.sha256(user.password.encode()).hexdigest()
             or (link.purpose == 'verify' and verified) or (link.purpose == 'reset' and not verified))
    if stale:
        item.state='SKIPPED'
        item.token_ciphertext=''
        item.save(update_fields=['state','token_ciphertext'])
        return item.state
    if item.next_attempt_at > now:
        return item.state
    try:
        raw=token_cipher().decrypt(item.token_ciphertext.encode()).decode()
        if not hmac.compare_digest(hashlib.sha256(raw.encode()).hexdigest(),link.digest):
            raise InvalidToken()
    except (InvalidToken, ValueError, UnicodeError):
        item.state='FAILED'
        item.token_ciphertext=''
        item.save(update_fields=['state','token_ciphertext'])
        logger.warning('Account email payload unavailable; request a new link.')
        return item.state
    url=settings.FRONTEND_URL.rstrip('/')+'/#'+urlencode({'account_action':link.purpose,'token':raw})
    label='Verify your email' if link.purpose == 'verify' else 'Reset your password'
    item.attempts+=1
    try:
        sent=send_mail('Railwise - '+label,
            f'{label} for your Railwise account.\nAccount: {user.username}\n\n{url}\n\n'
            f'This link expires at {timezone.localtime(link.expires_at).strftime("%d %b %Y, %I:%M %p %Z")} and works once. '
            'Only continue if you requested this. Otherwise ignore this email.\nRailwise is a portfolio demo.',
            settings.DEFAULT_FROM_EMAIL,[link.email],fail_silently=False)
        if sent != 1:
            raise RuntimeError('Email was not accepted')
    except Exception:
        # Transport exceptions can contain recipient addresses, credentials or links.
        logger.warning('Account email delivery failed; retry scheduled or request a new link.')
        item.next_attempt_at=now+timedelta(seconds=min(60*2**(item.attempts-1),300))
        item.state='RETRY' if item.attempts < 5 and item.next_attempt_at < link.expires_at else 'FAILED'
        if item.state == 'FAILED':
            item.token_ciphertext=''
    else:
        item.state='SENT'
        item.sent_at=timezone.now()
        item.token_ciphertext=''
    item.save(update_fields=['state','attempts','next_attempt_at','sent_at','token_ciphertext'])
    return item.state


def dispatch_account_emails(limit=25):
    ids=list(AccountLinkDelivery.objects.filter(state__in=['QUEUED','RETRY'],next_attempt_at__lte=timezone.now())
             .order_by('next_attempt_at','pk').values_list('pk',flat=True)[:limit])
    result={}
    for delivery_id in ids:
        state=deliver_account_email(delivery_id)
        result[state]=result.get(state,0)+1
    return result
