# Staff operations dashboard

Open `/admin/operations/` on the API host (locally `http://127.0.0.1:8001/admin/operations/`). The Django admin home also links to the dashboard. It uses the existing Django admin session, not the customer frontend token.

## Access

An active staff user needs all five model view permissions: Booking, Payment attempt, Refund, Booking email and Operation audit. A superuser already has them. Grant permissions through the existing admin account; no existing customer was promoted and no privileged account was created in the live database during implementation. If no administrator exists, the project owner can create one interactively with `python backend/manage.py createsuperuser`.

Email retry additionally requires `bookings.change_bookingemail`. View-only operators can inspect alerts but have no retry button and cannot call its endpoint. Anonymous/non-staff users are redirected to admin login; staff missing model permissions receive 403. POST requests require CSRF validation. Dashboard responses disable caching.

## Alerts and counts

- Lead bookings are counted by status; companions do not inflate booking-group counts.
- Email alerts: FAILED, or QUEUED/RETRY whose next scheduled attempt is over five minutes late. WAITING_VERIFICATION is counted separately, not treated as delivery failure.
- Payment alerts: REVIEW, or CREATED/AUTHORIZED older than 15 minutes from creation. Regular provider polling cannot reset the age and hide a stuck payment.
- Refund alerts: FAILED/UNKNOWN/REVIEW, or REQUESTED/PROCESSING older than 15 minutes from creation.
- Overdue hold count: pending lead bookings past their hold deadline.

Counts cover all recorded data. Each attention table shows at most the oldest 25 relevant rows, plus the latest 25 audit records. Refresh is manual; these are on-screen alerts, not outbound staff alert emails or a real-time monitoring service. Dashboard reads never call Razorpay, send mail, expire holds or mutate booking/payment state. Amount rows include their ledger currency.

The summary omits passenger names, contact addresses, email bodies, signatures and provider error text. Ledger links lead to separately permission-protected Django admin detail views. An overdue hold should be reconciled through existing booking/expiry workflows; viewing this dashboard does not free inventory.

## Audited email retry

The retry POST and existing bulk admin retry action use the same transactional service. Only FAILED rows become RETRY with an immediate next-attempt time. The worker rechecks verification, mailbox changes and superseded events before delivery. The request itself never sends mail or submits a payment/refund.

Each existing selected notification records actor ID, action, target ID, outcome and time in `OperationAudit`, including skipped non-failed rows. Repeating a retry cannot reset an already-queued notification. Bulk retry is capped at 200 distinct rows. Audit and state update roll back together. The audit model is read-only in admin; this is not a cryptographically tamper-proof ledger against database administrators.

After commit, the `railwise.operations` logger emits allowlisted JSON containing only event, actor ID, notification ID and outcome. Freeform messages, request data, exception text and credentials are excluded. Logs go to the API process output; this phase does not configure a remote log collector or external paging.

## Verification

The complete backend suite passed 146 tests. Fourteen operations regressions cover access, view-only roles, CSRF, side-effect-free reads, thresholds/group counts, retry permission/idempotency, missing targets, batch limits, transactional rollback, audit immutability in admin and structured-log redaction. Final operations tests passed again after pending-payment age and template refinements. Migration consistency check passed.

Visual QA used a static synthetic render of the same Django template, with no live data, privileged account or functional retry controls. Desktop and narrow-screen layouts were checked; see [preview](screenshots/operations-dashboard.png). The actual authenticated staff page is covered by Django client tests; no real staff browser login or production recovery action was performed.

Reference: [Django custom admin views and permissions](https://docs.djangoproject.com/en/dev/ref/contrib/admin/).
