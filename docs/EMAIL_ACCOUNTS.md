# Email verification and password recovery

Signup sends a verification email after the account transaction commits. Existing users can request verification from the account banner or sign-in dialog. Email links open a dedicated Railwise screen; verification requires pressing **Verify email**, so simply opening a link does not consume it. The banner shows the verified state for the user's current account email. Booking checkout remains available while unverified; password recovery requires verification.

**Forgot password?** asks for the username and verified account email. Both must match, avoiding ambiguous resets where legacy accounts share an address. Unknown, inactive, unverified and mismatched accounts receive the same generic 202 response. The response does not promise delivery or reveal a token. Email delivery is synchronous, so this is not a constant-time anti-enumeration guarantee. Delivery exceptions are redacted and receive the same generic response; retry through resend after checking SMTP health. There is no durable email retry outbox in this phase.

## Link security

- Cryptographically random 256-bit tokens; only their SHA-256 digest is stored.
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

The default DEBUG email backend prints emails to the API terminal; it does not send mail to an inbox. Open the generated verification/reset link yourself to exercise the flow. Treat terminal email links as credentials and do not share logs containing them. Automated tests use Django's in-memory email backend and never send real mail.

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

Use a provider-approved sender, HTTPS frontend and authenticated SMTP. The provider credentials and actual delivery have not been configured or verified. `EMAIL_TIMEOUT` is 10 seconds. DEBUG=False defaults to SMTP instead of console. See [Django email configuration](https://docs.djangoproject.com/en/6.0/topics/email/) and [password validation](https://docs.djangoproject.com/en/6.0/topics/auth/passwords/).

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
