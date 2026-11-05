# Booking email notifications

Payment-verified booking confirmation, cancellation and refund updates now create durable `BookingEmail` outbox rows in the same database transaction as the change. Rollback removes the event; SMTP is never called by booking/payment/webhook transactions. The group lead owns one notification containing all passengers and assigned seats, route/date/train, total and relevant payment/refund reference. No PDF attachment or public ticket URL is included.

Events have a unique booking/type or refund/state key. Duplicate webhooks and repeated cancellation therefore do not create duplicate rows. Queued confirmations are skipped after cancellation, and old pending refund updates are skipped when a newer refund state arrives. Emails are snapshots; sign in for the current state. Provider-processed refund does not promise immediate bank credit.

## Verified recipients

Only the booking owner's verified **account email** receives passenger information. The separately entered booking contact email is not a delivery destination. Unverified owners see **Verify account email to receive this update**; successful verification wakes their waiting notifications. A worker rechecks verification and active status before sending. An event already addressed to a mailbox is skipped if the account switches to a different mailbox, rather than redirecting its contents.

## Running delivery

Apply migrations, then either run the Celery worker/beat described in [payment lifecycle setup](PAYMENT_LIFECYCLE.md), or process notifications alone:

```powershell
python backend/manage.py migrate
python backend/manage.py send_booking_notifications --limit 100
```

The management command only sends booking emails; it never submits payments/refunds. Beat schedules the notification task every 30 seconds. Queue insertion works without Redis; delivery requires this command or a running worker/beat. No worker processing real payment/refund queues was started during this change.

Follow-up: the dedicated email-only worker and beat are now running locally. See [background service controls](BACKGROUND_SERVICES.md). They do not schedule gateway/refund recovery jobs; the broader worker setup in PAYMENT_LIFECYCLE.md is separate.

Locally, the console backend prints email text. Real email needs the [SMTP configuration](EMAIL_ACCOUNTS.md). SMTP host, username, password and sender were not configured at verification time; no real inbox delivery is claimed.

Gmail setup follow-up on 19 October 2026: the user configured SMTP credentials in the ignored backend environment file. STARTTLS and authentication succeeded, and Gmail accepted one plain test message to the user-authorized recipient. The API was restarted to load the configuration. Inbox receipt was not independently verified, and no queued booking emails or payment/refund jobs were bulk-dispatched during this check.

## Retries and operations

Backend errors or a zero-send result schedule retries with exponential delay from 60 seconds up to one hour. `BOOKING_EMAIL_MAX_ATTEMPTS` defaults to 5. After exhaustion, the row becomes FAILED. Django admin offers **Retry selected failed email notifications** to users with BookingEmail change permission. Notification fields are read-only; payment/refund ledger permissions remain read-only.

Workers lock the user then outbox row, serializing overlapping workers. SMTP acceptance is recorded as SENT; this means backend acceptance, not inbox delivery or a read receipt. SMTP cannot guarantee exactly-once delivery: a crash after provider acceptance but before database commit can lead to a retry. A stable Message-ID is provided, but recipient deduplication is not guaranteed. Backend failure details are redacted to avoid exposing credentials or recipients.

Booking API responses include owner-only metadata (kind, state, attempts, recipient and timestamps), never email bodies. History and confirmation show email statuses. These outbox rows contain passenger snapshots: restrict database/admin access and set a retention policy before deployment.

## Verification

The full 126-test regression suite passed before the final notification refinements. The final 17 notification regressions separately cover those refinements, including full-group content, console output, superseded unverified emails, concurrent workers, rollback, deduplication, verified-only delivery, changed email addresses, redacted retries and terminal failures. Frontend build/lint and its four tests passed. Migration consistency check passed.

Browser verification used an isolated synthetic booking/refund, checked history status and verification/forgot-password form navigation, then removed the fixture. No gateway refund or real email delivery was performed. [Notification preview](screenshots/email-notifications.png) uses synthetic data.

References: [Django email backend semantics](https://docs.djangoproject.com/en/6.0/topics/email/), [Celery overlapping periodic tasks](https://docs.celeryq.dev/en/main/userguide/periodic-tasks.html).
