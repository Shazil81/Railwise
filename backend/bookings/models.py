import uuid
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import IntegerRangeField, RangeOperators
from django.db import models
from django.db.models import F, Func, Q


class Train(models.Model):
    number = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=120)
    in_catalogue = models.BooleanField(default=False)
    run_days = models.JSONField(default=list, blank=True)
    valid_from = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.number} – {self.name}"


class Station(models.Model):
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.code


class TrainStop(models.Model):
    train = models.ForeignKey(Train, on_delete=models.CASCADE, related_name="stops")
    station = models.ForeignKey(Station, on_delete=models.CASCADE)
    sequence = models.PositiveIntegerField()
    distance_km = models.PositiveIntegerField(null=True, blank=True)
    arrival = models.CharField(max_length=8, blank=True, default='')
    departure = models.CharField(max_length=8, blank=True, default='')
    day = models.PositiveSmallIntegerField(default=1)

    class Meta:
        unique_together = [("train", "sequence"), ("train", "station")]
        ordering = ["sequence"]

    def __str__(self):
        return f"{self.train} → {self.station} (seq {self.sequence})"


class Seat(models.Model):
    berth_type = models.CharField(max_length=3,blank=True,default='',choices=[('','Automatic demo layout'),('LB','Lower'),('MB','Middle'),('UB','Upper'),('SL','Side Lower'),('SU','Side Upper'),('NA','Seat')])
    train = models.ForeignKey(Train, on_delete=models.CASCADE, related_name="seats")
    coach = models.CharField(max_length=5)   # B1
    number = models.PositiveIntegerField()   # 24
    travel_class = models.CharField(max_length=3, default='SL', choices=[('SL','Sleeper'),('3A','AC 3 Tier'),('2A','AC 2 Tier'),('1A','AC First'),('CC','AC Chair Car'),('EC','Executive Chair Car')])

    class Meta:
        unique_together = [("train", "coach", "number")]

    def __str__(self):
        return f"{self.coach}-{self.number}"

    @property
    def allocated_berth(self):
        from .berths import inferred_berth
        return self.berth_type or inferred_berth(self.travel_class,self.number)


class Journey(models.Model):
    train = models.ForeignKey(Train, on_delete=models.CASCADE)
    date = models.DateField()

    class Meta:
        unique_together = [("train", "date")]

    def __str__(self):
        return f"{self.train} on {self.date}"


class Booking(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING"        # seat hold, payment baaki
        CONFIRMED = "CONFIRMED"
        WL = "WL"                  # waiting list
        EXPIRED = "EXPIRED"        # payment nahi hua
        CANCELLED = "CANCELLED"

    ACTIVE = ["PENDING", "CONFIRMED"]

    group_parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='companions')
    passenger_name = models.CharField(max_length=100, blank=True, default='')
    passenger_age = models.PositiveSmallIntegerField(null=True, blank=True)
    passenger_gender = models.CharField(max_length=20, blank=True, default='')
    passenger_country = models.CharField(max_length=80, default='India')
    preferred_coach = models.CharField(max_length=5, blank=True, default='')
    gstin = models.CharField(max_length=15, blank=True, default='')
    berth_preference = models.CharField(max_length=3,default='ANY',choices=[('ANY','No preference'),('LB','Lower'),('MB','Middle'),('UB','Upper'),('SL','Side Lower'),('SU','Side Upper')])
    contact_email = models.EmailField(blank=True, default='')
    contact_phone = models.CharField(max_length=10, blank=True, default='')
    payment_checked_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    confirmed_berths_only = models.BooleanField(default=False)
    consider_auto_upgrade = models.BooleanField(default=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    journey = models.ForeignKey(Journey, on_delete=models.CASCADE)
    seat = models.ForeignKey(Seat, null=True, blank=True, on_delete=models.SET_NULL)
    from_seq = models.PositiveIntegerField()
    to_seq = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=Status.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=450.00)
    travel_class = models.CharField(max_length=3, default='SL')
    quota = models.CharField(max_length=2, default='GN', choices=[('GN','General'),('TQ','Tatkal')])
    fare_details = models.JSONField(default=dict, blank=True)
    razorpay_order_id = models.CharField(max_length=100, null=True, blank=True, unique=True)
    razorpay_payment_id = models.CharField(max_length=100, null=True, blank=True, unique=True)
    razorpay_signature = models.CharField(max_length=255, null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(from_seq__lt=F("to_seq")), name="from_lt_to"
            ),
            # DB level guarantee: same seat + same journey par overlapping range nahi
            ExclusionConstraint(
                name="no_overlapping_seat_segments",
                expressions=[
                    ("seat", RangeOperators.EQUAL),
                    ("journey", RangeOperators.EQUAL),
                    (
                        Func(F("from_seq"), F("to_seq"),
                             function="int4range",
                             output_field=IntegerRangeField()),
                        RangeOperators.OVERLAPS,
                    ),
                ],
                condition=Q(status__in=["PENDING", "CONFIRMED"]),
            ),
        ]
        indexes = [models.Index(fields=["journey", "status", "created_at"])]

    def __str__(self):
        return f"Booking #{self.pk} [{self.status}]"

    @property
    def boarding_date(self):
        day=self.journey.train.stops.get(sequence=self.from_seq).day
        return self.journey.date+timedelta(days=day-1)


class PaymentAttempt(models.Model):
    class State(models.TextChoices):
        CREATED = 'CREATED'
        AUTHORIZED = 'AUTHORIZED'
        CAPTURED = 'CAPTURED'
        FAILED = 'FAILED'
        REFUNDED = 'REFUNDED'
        REVIEW = 'REVIEW'
    booking = models.ForeignKey(Booking, on_delete=models.PROTECT, related_name='payment_attempts')
    payment_id = models.CharField(max_length=100, unique=True)
    order_id = models.CharField(max_length=100)
    amount_paise = models.PositiveBigIntegerField()
    currency = models.CharField(max_length=3, default='INR')
    state = models.CharField(max_length=20, choices=State.choices, default=State.CREATED)
    failure_message = models.CharField(max_length=200, blank=True, default='')
    method = models.CharField(max_length=20, blank=True, default='')
    provider_created_at = models.DateTimeField(null=True, blank=True)
    captured_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Refund(models.Model):
    class State(models.TextChoices):
        REQUESTED = 'REQUESTED'
        PROCESSING = 'PROCESSING'
        PROCESSED = 'PROCESSED'
        FAILED = 'FAILED'
        UNKNOWN = 'UNKNOWN'
        REVIEW = 'REVIEW'
    attempt = models.OneToOneField(PaymentAttempt, on_delete=models.PROTECT, related_name='refund')
    provider_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    idempotency_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    amount_paise = models.PositiveBigIntegerField()
    state = models.CharField(max_length=20, choices=State.choices, default=State.REQUESTED)
    reason = models.CharField(max_length=100)
    message = models.CharField(max_length=200, blank=True, default='')
    attempts = models.PositiveIntegerField(default=0)
    next_check_at = models.DateTimeField(default=timezone.now)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class WebhookEvent(models.Model):
    event_id = models.CharField(max_length=128, unique=True)
    kind = models.CharField(max_length=80)
    body_hash = models.CharField(max_length=64)
    outcome = models.CharField(max_length=30, default='RECEIVED')
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)


class AccountEmail(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    verified_email = models.EmailField(blank=True, default='')


class AccountLink(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    purpose = models.CharField(max_length=10, choices=[('verify', 'Verify'), ('reset', 'Reset')])
    digest = models.CharField(max_length=64, unique=True)
    password_digest = models.CharField(max_length=64)
    email = models.EmailField()
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)


class AccountLinkDelivery(models.Model):
    link = models.OneToOneField(AccountLink, on_delete=models.CASCADE, related_name='delivery')
    token_ciphertext = models.TextField()
    state = models.CharField(max_length=10, default='QUEUED', choices=[
        ('QUEUED','Queued'),('RETRY','Retry scheduled'),('SENT','SMTP accepted'),
        ('FAILED','Needs attention'),('SKIPPED','Link no longer valid')])
    attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['state','next_attempt_at'], name='account_mail_due_idx')]


class BookingEmail(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='email_notifications')
    event_key = models.CharField(max_length=150, unique=True)
    kind = models.CharField(max_length=30)
    recipient = models.EmailField(blank=True, default='')
    subject = models.CharField(max_length=200)
    body = models.TextField()
    state = models.CharField(max_length=25, default='QUEUED', choices=[
        ('QUEUED','Queued'),('WAITING_VERIFICATION','Verify email first'),('RETRY','Retry scheduled'),
        ('SENT','Accepted by email backend'),('FAILED','Needs attention'),('SKIPPED','Superseded')])
    attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    last_error = models.CharField(max_length=200, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivery_channel = models.CharField(max_length=20, default='unknown')

    class Meta:
        indexes = [models.Index(fields=['state','next_attempt_at'])]


class OperationAudit(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=40)
    target_id = models.PositiveBigIntegerField()
    outcome = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)
