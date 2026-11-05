# Railwise: Phase 1 payment security

## Configuration

Generate fresh Razorpay Test Mode credentials after rotating the key previously shared in chat. Rotation must be completed in the account dashboard; changing this source code does not revoke a key. Put the new values in backend/.env (ignored by version control), or inject environment variables:

```dotenv
RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=
```

Settings have no credential defaults. Missing either value produces HTTP 503 for payment operations. The secret is never included in API responses or frontend bundles. Apply `python backend/manage.py migrate` to install the order/payment uniqueness constraints. Existing duplicate references need investigation before migration; no user payment data is automatically deleted.

## Confirmation boundary

- `/pay/` is a compatibility alias for `/verify-payment/`, with identical required input validation. Empty or partial payloads cannot confirm a booking.
- The booking owner must authenticate. The supplied order ID must match the saved order ID.
- HMAC-SHA256 uses the saved order ID and server-only secret. A constant-time comparison rejects a forged signature before fetching a payment.
- Razorpay's payment fetch must return the same payment ID, saved order ID, booking amount in paise, INR currency, captured status and captured flag. Refunded payments are rejected.
- Confirmation checks hold expiry both before and after gateway fetch. Expired and cancelled bookings cannot be restored by a callback.
- Verified retries of the same confirmed payment return the existing booking. Different payment IDs cannot replace an existing confirmation.
- Unique database fields prevent order/payment references from being attached to multiple bookings.
- Create-order reuses a saved order and validates its amount/currency/ID. Journey and booking locks serialize competing operations using the existing lock order.
- Gateway calls have a timeout and return sanitized service errors. External requests occur while holding the journey lock, favoring consistency over throughput in this prototype.

Razorpay's official flow requires server-side signature verification using the stored order ID and fulfillment only after capture: https://razorpay.com/docs/payments/payment-gateway/web-integration/standard/integration-steps/

## Validation

34 regression tests passed against real PostgreSQL. Payment tests use real HMAC generation and mocked gateway fetches, covering missing payload/configuration, forged signatures, wrong orders, reused payments, mismatching payment fields, expiry/cancellation, retries, owner isolation, database uniqueness and provider outages. No real or test gateway transaction was submitted during this validation. Frontend lint and production build passed.

## Remaining work

Passenger details, atomic multi-passenger holds and fare review are implemented; see [checkout notes](CHECKOUT.md). Verified webhooks, payment-attempt history and refund recovery are now implemented; see the lifecycle setup notes below. A timeout can leave a provider-created order whose response was never saved; saved-order reuse does not resolve that ambiguity. A captured payment after hold expiry does not fulfill the ticket and is queued for a tracked refund. Cancellation releases inventory and records a durable full-group refund request for background processing. Keep this as a Test Mode prototype until those flows are implemented and tested.


Update: webhook verification, payment-attempt history, pending/failed recovery and cancellation refund tracking are now implemented. See [payment lifecycle setup and limitations](PAYMENT_LIFECYCLE.md).
