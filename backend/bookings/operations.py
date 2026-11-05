"""Permission-scoped operations snapshot and audited, non-financial email retry."""
import logging
from datetime import timedelta
from decimal import Decimal
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from .models import Booking, BookingEmail, PaymentAttempt, Refund, OperationAudit

VIEW_PERMISSIONS = tuple('bookings.view_'+name for name in ['booking','paymentattempt','refund','bookingemail','operationaudit'])
logger=logging.getLogger('railwise.operations')


def require_operator(user):
    if not user.is_active or not user.is_staff or not user.has_perms(VIEW_PERMISSIONS):
        raise PermissionDenied('Operations access requires the booking, payment, refund, email and audit view permissions.')


@transaction.atomic
def retry_failed_emails(actor, ids):
    if not actor.is_active or not actor.is_staff or not actor.has_perm('bookings.change_bookingemail'):
        raise PermissionDenied('Email retry permission required.')
    ids=sorted(set(ids))
    if len(ids)>200:
        raise ValidationError('Retry at most 200 notifications at a time.')
    # Match the worker's user-before-email lock order, including the audit actor FK.
    get_user_model().objects.select_for_update().get(pk=actor.pk)
    count=0
    for item in BookingEmail.objects.select_for_update().filter(pk__in=ids).order_by('pk'):
        outcome='SKIPPED'
        if item.state=='FAILED':
            item.state='RETRY';item.attempts=0;item.next_attempt_at=timezone.now();item.last_error=''
            item.save(update_fields=['state','attempts','next_attempt_at','last_error'])
            outcome='REQUEUED';count+=1
        OperationAudit.objects.create(actor=actor,action='EMAIL_RETRY',target_id=item.pk,outcome=outcome)
        transaction.on_commit(lambda pk=item.pk,result=outcome: logger.info('email_retry',extra={
            'actor_id':actor.pk,'notification_id':pk,'outcome':result}))
    return count


def counts(queryset, field):
    return {row[field]:row['count'] for row in queryset.values(field).annotate(count=Count('pk'))}


def operations_snapshot():
    now=timezone.now();cutoff=now-timedelta(minutes=15)
    emails=BookingEmail.objects.filter(Q(state='FAILED') | Q(state__in=['QUEUED','RETRY'],next_attempt_at__lt=now-timedelta(minutes=5)))
    payments=PaymentAttempt.objects.filter(Q(state='REVIEW') | Q(state__in=['CREATED','AUTHORIZED'],created_at__lt=cutoff))
    refunds=Refund.objects.filter(Q(state__in=['FAILED','UNKNOWN','REVIEW']) | Q(state__in=['REQUESTED','PROCESSING'],created_at__lt=cutoff))
    holds=Booking.objects.filter(group_parent__isnull=True,status='PENDING',expires_at__lte=now)
    def payment_row(item):
        return {'id':item.pk,'booking_id':item.booking_id,'state':item.state,
            'currency':item.currency,
            'amount':format(Decimal(item.amount_paise)/100,'.2f'),'updated_at':item.updated_at}
    return {'generated_at':now,'bookings':counts(Booking.objects.filter(group_parent__isnull=True),'status'),
        'payment_counts':counts(PaymentAttempt.objects.all(),'state'),
        'refund_counts':counts(Refund.objects.all(),'state'),'email_counts':counts(BookingEmail.objects.all(),'state'),
        'alerts':{'emails':emails.count(),'payments':payments.count(),'refunds':refunds.count(),'holds':holds.count()},
        'emails':list(emails.order_by('next_attempt_at','id').values('id','booking_id','kind','state','attempts','created_at')[:25]),
        'payments':[payment_row(item) for item in payments.order_by('created_at','id')[:25]],
        'refunds':[{'id':item.pk,'booking_id':item.attempt.booking_id,'state':item.state,
            'currency':item.attempt.currency,
            'amount':format(Decimal(item.amount_paise)/100,'.2f'),'created_at':item.created_at}
            for item in refunds.select_related('attempt').order_by('created_at','id')[:25]],
        'audits':list(OperationAudit.objects.order_by('-created_at','-id').values('actor_id','action','target_id','outcome','created_at')[:25])}


@require_GET
def operations_dashboard(request):
    require_operator(request.user)
    context={**admin.site.each_context(request),'title':'Railwise operations','snapshot':operations_snapshot(),
        'can_retry':request.user.has_perm('bookings.change_bookingemail')}
    return TemplateResponse(request,'bookings/operations.html',context)


@require_POST
def retry_email_view(request, notification_id):
    require_operator(request.user)
    if not BookingEmail.objects.filter(pk=notification_id).exists():
        raise Http404
    count=retry_failed_emails(request.user,[notification_id])
    messages.success(request,'Email queued for retry.' if count else 'No change: only failed notifications can be retried.')
    return redirect('railwise-operations')
