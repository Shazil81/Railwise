# Email verification and password recovery

Signup atomically queues a verification email with the account/link transaction. The Docker Celery worker sends it using Gmail SMTP, independently of Render's blocked SMTP ports. Existing users can request verification from the account banner or sign-in dialog. Email links open a dedicated Railwise screen; verification requires pressing **Verify email**, so simply opening a link does not consume it. Booking checkout remains available while unverified; password recovery requires verification.

**Forgot password?** asks for the username and verified account email. Both must match, avoiding ambiguous resets where legacy accounts share an address. Unknown, inactive, unverified and mismatched accounts receive the same generic 202 response. The response never reveals a token. Requests do not contact SMTP and are not claimed to be constant-time; eligible requests create durable outbox rows. Worker failures retry with bounded backoff (up to five attempts), without logging provider exception details.

## Link security

- Cryptographically random 256-bit tokens; validation stores their SHA-256 digest. The outbox temporarily stores a Fernet-encrypted token, with a purpose-separated key derived from `SECRET_KEY`. No plaintext link/token is stored in its payload.
- API and worker must share `SECRET_KEY`. A key change makes pending payloads fail closed; request a fresh link after rotation. Payloads are erased after SMTP acceptance, supersession, consumption, expiry or terminal failure.
- Separate verification/reset purposes; links expire after 30 minutes by default.
- Resending invalidates previous unused links of that purpose.
- Atomic user/link row locks enforce single use, including concurrent reset attempts.
- Current email, active status and password fingerprint are checked. A password change invalidates outstanding links.
- Password validators and confirmation are checked before consuming a reset link. Successful reset invalidates all other links and revokes existing API tokens. Django session password hashes also invalidate old sessions.
- Links use configured `FRONTEND_URL`, never the request Host header. Bearer tokens are carried in the URL fragment, then removed from the address bar by the frontend. No action is performed via GET. API responses use no-store.
- Request/resend is limited to 5 per hour per IP, shared across verification/reset. Consumption uses the login limit of 10 per minute per IP. These are basic cache-based application limits, not production brute-force protection.

Verified account email is distinct from a booking's contact email. This phase does not send passenger tickets to arbitrary booking contact addresses.

## Local setup

Apply migrations: `python backend/manage.py migrate`.

Run the worker/beat for the database used by the API. The deployed setup uses [the PC-hosted Docker worker](DOCKER_WORKER.md), which scans the account outbox every 30 seconds before booking notifications. If the PC is off/asleep, messages wait; expired links are skipped and must be requested again. The API does not enqueue through a remote Redis broker: both ends share durable Neon records.

The default DEBUG console email backend prints mail from the **worker**, not the API, and never delivers to an inbox. Treat those links as credentials. Automated tests use an in-memory backend and never send real mail.

## SMTP setup

Configure these backend environment variables without committing credentials:

```dotenv
FRONTEND_URL=https://your-railwise-host.example
ACCOUNT_LINK_TIMEOUT=1800
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
DEFAULT_FROM_EMAIL=Railwise <verified-sender@your-domain.example>
EMAIL_HOST=smtp.your-provider.example
EMAIL_PORT=587
EMAIL_HOST_USER=your-provider-username
EMAIL_HOST_PASSWORD=your-provider-secret
EMAIL_USE_TLS=True
```

Set SMTP credentials on the Docker worker only; do not put Gmail credentials on Vercel or commit them. Use the configured Gmail sender and app password, an HTTPS frontend, and matching API/worker `SECRET_KEY`. `EMAIL_TIMEOUT` is 10 seconds. SMTP acceptance is recorded as `SENT`; inbox/spam delivery is verified separately. A process crash after SMTP acceptance but before the DB commit can cause a duplicate email with the same single-use link; this is not an exactly-once delivery guarantee.

## API

| Method | Path | Body |
| --- | --- | --- |
| GET | `/api/accounts/me/` | Authenticated; current email and verified state |
| POST | `/api/accounts/request-verification/` | username, email |
| POST | `/api/accounts/verify-email/` | token |
| POST | `/api/accounts/forgot-password/` | username, email |
| POST | `/api/accounts/reset-password/` | token, password, password_confirm |

Tests cover hashed tokens, expiry, wrong-purpose/tampered links, replay, resend invalidation, password/email changes, inactive users, generic unknown-account responses, provider failure redaction, signup email, owner-only status, shared-address handling, weak passwords, revoked login tokens and two competing reset requests.

Validation on 19 October 2026: all 112 PostgreSQL backend tests and 4 frontend URL-handling tests passed. Frontend production build and lint passed; migration consistency check reported no changes. `npm test --prefix frontend` requires Node 22.18+ or Node 24 for native TypeScript type stripping. Browser visual verification remains unavailable because the browser security policy blocked preview access in the account phase; no new screenshot or browser end-to-end claim is made.

Follow-up during the booking-notification phase: the local browser preview was restored after starting Vite. Verification-request and forgot-password forms were visually checked, including modal focus/scroll behavior. Screenshots: [verification](screenshots/email-verification-form.png), [forgot password](screenshots/forgot-password-form.png). Actual SMTP delivery and browser password submission were not performed.

Gmail configuration follow-up: SMTP STARTTLS/authentication and submission of one user-authorized plain test email succeeded. The local API was restarted with the new environment settings. This confirms Gmail acceptance, not inbox placement; real verification/reset links were not sent as part of that test.
