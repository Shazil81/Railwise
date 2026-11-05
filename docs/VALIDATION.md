# Validation report — 5 November 2026

## Measured contention

See [raw results](contention-results.json). PostgreSQL isolated test DB, 100 service
calls through 10 threads competing for one seat: **1 successful hold, 99 conflicts**.
Elapsed 6.854 seconds; p50 663.47 ms; p95 762.70 ms; 14.59 attempts/second.
These include DB connection/service overhead and were measured during local testing.
They are not HTTP load measurements or production capacity claims.

## Checks on this checkout

- Frontend: 36 tests passed; lint passed; production build passed.
- Windows: six startup regression checks passed; installed shortcut matches this project.
- Running supervisor heartbeat: operations mode; worker and beat running.
- Startup launcher smoke test: reached READY after fixing child script path quoting.
- Production settings: Django `check --deploy` passed with synthetic HTTPS/domain/secret inputs.
- Backend full regression: all 238 tests passed in 169.929 seconds using isolated test settings and PostgreSQL.
- Cloud settings: TLS-only Redis, required PostgreSQL URL, pooled-connection cursor safety,
  explicit CORS origin and production `check --deploy` passed with synthetic inputs.
- Public health endpoint returns a safe 503 on database failure without leaking connection details.

The test settings isolate email/cache/Celery broker and use a fast test-only hasher.
Inventory/constraints still use PostgreSQL. Never serve using test_settings.

## Earlier browser evidence — 1 November 2026

Razorpay Test Mode captured INR 678.40; booking confirmation included actual coach
and seat; browser PDF download completed and its single page was rendered/reviewed.
Refund records subsequently advanced to provider PROCESSED. Failed attempts did not
confirm unpaid bookings. These are dated checks, not a claim that external providers
were re-tested during this documentation/release run.

## Checks still requiring environment/user action

- Physical Windows reboot/sign-in (the launcher smoke test does not reproduce a cold boot).
- Public webhook delivery and a fresh hosted captured-payment/PDF/refund check.
- Scheduled encrypted backup and restore rehearsal into a separate DB.
- Fresh phone-browser smoke check and a sanitized video recording.
- CI status on GitHub after this push; local passing tests do not imply CI has run.

## Focused usability and lifecycle improvements — 5 November 2026

- The earlier UI regression run passed all 233 backend tests and 35 frontend tests.
- Public browsing no longer loads Razorpay; the payment action loads the SDK once,
  with timeout/error cleanup and retry. A browser smoke check opened Test Mode
  checkout using the lazy loader. It made no payment; the unpaid hold was cancelled.
- Passenger drafts are copied into tab memory, isolated by username/route and available
  for 30 minutes. They clear on successful reservation, logout or password reset.
  Reload/close warns while dirty; drafts never enter localStorage/sessionStorage.
- Browser check: returning to results and reopening the same train restored passengers.
- Results subscribe to inventory only while their route and browser tab are active;
  booking polling also pauses in background tabs. Public SSE snapshots are briefly
  shared through the configured Django cache (2 seconds, below the 3-second tick).
  Server allocation remains authoritative; the cache never reserves seats.
- Mobile filters expand/collapse; small text is at least 12px; shared tokens/fonts
  are centralized. Browser inspection at 375px found no horizontal overflow.
- Missing routes display a 404 screen with Home recovery.

Physical touch/screen-reader testing and production capacity remain unverified.
The later cloud deployment is recorded in [the cloud runbook](CLOUD_DEPLOYMENT.md).
Earlier successful gateway capture/PDF/refund evidence remains the separate dated
integration check above, not a claim that it was repeated on the free hosted environment.
