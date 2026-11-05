from django.contrib import admin
from .models import Train, Station, TrainStop, Seat, Journey, Booking


@admin.register(Train)
class TrainAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "in_catalogue", "valid_from", "valid_until")
    search_fields = ("number", "name")


@admin.register(Station)
class StationAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")


@admin.register(TrainStop)
class TrainStopAdmin(admin.ModelAdmin):
    list_display = ("train", "station", "sequence", "distance_km", "day")
    list_filter = ("train",)


@admin.register(Seat)
class SeatAdmin(admin.ModelAdmin):
    list_display = ("train", "coach", "number", "travel_class")
    list_filter = ("train", "travel_class", "coach")


@admin.register(Journey)
class JourneyAdmin(admin.ModelAdmin):
    list_display = ("train", "date")
    list_filter = ("date",)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "journey", "seat", "status", "from_seq", "to_seq", "created_at")
    list_filter = ("status", "journey")
    search_fields = ("user__username",)
    readonly_fields = ("created_at",)


from .models import PaymentAttempt, Refund, WebhookEvent
from .models import BookingEmail, OperationAudit
from .operations import retry_failed_emails
admin.site.site_header='Railwise administration'
admin.site.index_template='bookings/operations_index.html'

class ReadOnlyLedgerAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(BookingEmail)
class BookingEmailAdmin(admin.ModelAdmin):
    list_display = ('id','booking','kind','state','attempts','created_at','sent_at')
    list_filter = ('kind','state')
    readonly_fields = ('booking','event_key','kind','recipient','subject','body','state','attempts','next_attempt_at','last_error','created_at','sent_at')
    actions = ['retry_failed']

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description='Retry selected failed email notifications', permissions=['change'])
    def retry_failed(self, request, queryset):
        from django.core.exceptions import ValidationError
        try:
            count=retry_failed_emails(request.user,list(queryset.values_list('pk',flat=True)[:201]))
        except ValidationError:
            self.message_user(request,'Select at most 200 notifications.',level='error')
            return
        self.message_user(request,f'{count} failed email notifications queued for retry.')

@admin.register(OperationAudit)
class OperationAuditAdmin(ReadOnlyLedgerAdmin):
    list_display=('created_at','actor_id','action','target_id','outcome')
    list_filter=('action','outcome')
@admin.register(PaymentAttempt)
class PaymentAttemptAdmin(ReadOnlyLedgerAdmin):
    list_display = ('payment_id', 'booking', 'state', 'amount_paise', 'updated_at')
    list_filter = ('state',)
    search_fields = ('payment_id', 'order_id')

@admin.register(Refund)
class RefundAdmin(ReadOnlyLedgerAdmin):
    list_display = ('id', 'provider_id', 'state', 'amount_paise', 'attempts', 'next_check_at')
    list_filter = ('state',)
    search_fields = ('provider_id', 'attempt__payment_id')

@admin.register(WebhookEvent)
class WebhookEventAdmin(ReadOnlyLedgerAdmin):
    list_display = ('event_id', 'kind', 'outcome', 'received_at', 'processed_at')
    list_filter = ('kind', 'outcome')
    search_fields = ('event_id',)
