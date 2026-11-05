# Razorpay webhooks, recovery and refund tracking

## Configure Test Mode

Keep regenerated Razorpay Test Mode API credentials in backend/.env or injected environment variables. The webhook signing secret is separate from the API key secret:

```dotenv
RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=
RAZORPAY_WEBHOOK_SECRET=
RAZORPAY_WEBHOOK_PREVIOUS_SECRET=
```

In Razorpay's Test Mode webhook settings, use your deployed **public HTTPS** endpoint ending in `/api/webhooks/razorpay/` and the same webhook signing secret. Localhost is not publicly deliverable; configuring a public endpoint or tunnel is a separate deployment action. This implementation does not expose your machine automatically. Never paste secret values into source code or chat.

Subscribe to:

- payment.authorized, payment.captured, payment.failed, payment.refunded
- order.paid
- refund.created, refund.processed, refund.failed

The optional previous secret accepts older deliveries during signing-secret rotation. Remove it when the old-delivery retry window is over.

## Background worker and durable queues

Apply migrations, start Redis, then run the worker and scheduler in separate terminals using the same backend environment:

```powershell
python backend/manage.py migrate
cd backend
celery -A railway_core worker --pool=solo -l info
```

```powershell
cd backend
celery -A railway_core beat -l info
```

A recovery sweep runs every minute. It checks up to 100 stored orders and 100 due refunds per sweep. Automatic order recovery covers pending, expired and cancelled bookings created within the last seven days, plus unresolved attempts in that window. Older bookings can still be checked through the owner-scoped recovery API. Provider polling is limited to once per booking every 30 seconds. Refund polling has bounded exponential backoff and is not restricted to seven days.

For a manual one-shot recovery run:

```powershell
python backend/manage.py reconcile_payments
```

**This command makes gateway requests and submits queued refunds using the configured account. Use Test Mode credentials for this prototype.** It was not run against a payment account during implementation. Without a worker/sweep, refund requests remain durably queued, and the UI says so; cancellation does not pretend money was refunded.

## Payment and booking states

`PaymentAttempt` records the provider payment ID, stored order, amount, currency and observed state. Multiple failed attempts can belong to one booking/order. A failed attempt does not cancel the seat hold; a retry can succeed while the shared deadline is active. Authorized or created payments do not confirm tickets and block another checkout until reconciled.

Captured payments must match the complete backend-calculated group fare, currency and order. Valid live holds with completed passenger review are confirmed atomically for the entire group. Captured payments received after hold expiry or cancellation are queued for a full refund; an expired seat is never resurrected. Additional captures do not replace the payment that confirmed a ticket and are queued for refund instead. Mismatched amounts are quarantined for administrator review.

The checkout callback still requires its own API-secret HMAC signature and a provider payment fetch. Webhooks use a different, raw-body signature. Both paths record captured payments through the same lifecycle handler. A missed browser callback is recoverable through webhooks, the background sweep, or **Check payment status** in checkout/history.

## Webhook trust and idempotency

`POST /api/webhooks/razorpay/` has no user/session authentication; it requires a valid `X-Razorpay-Signature` over the exact raw bytes and a bounded `X-Razorpay-Event-Id`. Body size is limited. Missing configuration fails closed with HTTP 503; invalid signatures return 403.

A unique `WebhookEvent` receipt stores only event ID, kind, body digest and processing outcome, not the full customer/card payload. Receipt creation and state transitions commit in one transaction. Identical replay returns DUPLICATE. Reusing an event ID with a changed body is rejected. Unsupported events and unknown orders are acknowledged as IGNORED; recovery can discover a missed payment later. State transitions reject stale events that would undo a capture or processed refund. Gateway calls are not made inside the webhook handler.

## Refund safety and policy

This demo uses **full-group refunds without cancellation fees**; this is a project policy, not an IRCTC refund policy. Partial cancellation/refunds require administrator review and are not automatically issued.

Cancelling a paid group releases all seats and creates one durable Refund row per captured payment. A request starts as REQUESTED, progresses through PROCESSING, and becomes PROCESSED only after provider evidence. FAILED is a provider-reported failure; UNKNOWN means a response was unavailable. REVIEW means inconsistent/partial/multiple refund evidence needs intervention.

Every request has a saved UUID idempotency key sent as `X-Refund-Idempotency`, with an immutable amount/receipt. Before creating a refund, the worker looks for an existing provider refund. This recovers a lost create response or a dashboard-initiated refund. Once a provider refund ID is known, the worker polls that ID and never issues a new request. Concurrent workers serialize using the existing journey/booking lock order. A stale pending/failed webhook cannot downgrade a processed refund.

Read-only Django admin ledgers show payment attempts, refunds and webhook receipts. Provider-reported failed refunds are polled by ID for resolution; this version does not automatically create a second refund after a terminal failure.

## API and UI

- `POST /api/bookings/:id/recover-payment/`: authenticated owner only; ignores client-supplied payment/order IDs and polls the stored order. Also discovers provider refunds. This endpoint does not submit new refunds.
- Existing booking list/detail responses include payment_attempts, refunds and payment_checked_at.
- Checkout and history display failed/pending/received/refunded states, refund reference, amount, reason and provider status.
- Ticket cancellation and refund processing are shown independently. Bank posting time is not presented as guaranteed.

## Verification

48 existing booking/group/payment tests plus 32 lifecycle tests passed against PostgreSQL (80 distinct tests). The lifecycle suite covers raw-body signatures, separate/rotated secrets, invalid signatures, duplicate/reordered events, concurrent webhook delivery, failed-to-successful retry, authorized holds, late capture, cancellation refunds, extra captures, full-group totals, wrong-amount quarantine, owner-scoped recovery, provider outages, timeout/idempotency retries, discovering a lost refund response, concurrent refund workers, refund status reconciliation and read-only recovery behavior.

Frontend production build and lint passed. Browser visual checks use a clearly labelled temporary synthetic fixture, removed afterward. No real payment or refund was executed, and no provider dashboard webhook was configured automatically.

Official references:

- https://razorpay.com/docs/webhooks/validate-test/
- https://razorpay.com/docs/api/refunds/normal-refunds-idempotent
