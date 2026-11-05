# Reservation rules and interview demo

These are portfolio rules, not a claim of official IRCTC policy. All comparisons use Asia/Kolkata, independent of the operating system timezone.

- General booking opens 60 days before the boarding date and closes at departure from the selected boarding station.
- Tatkal opens one day before the service's **origin date** at 10:00 IST for AC/chair classes and 11:00 IST for Sleeper. Downstream boarding on day 2 does not shift the origin opening date.
- Cancellation closes at the selected boarding departure. Already-cancelled requests remain idempotent. Existing project refund rules remain unchanged; there is no claim of official railway cancellation deductions.
- Passenger edits, fare review and payment creation/confirmation recheck booking validity. A hold lasts at most 10 minutes and never extends beyond boarding departure. A verified capture received after validity ends is handled through the refund recovery flow, not seat confirmation.
- Timetable-free legacy records use the end of their boarding day. Seeded catalogue services have saved timetable times.

## Waitlist

One passenger per waitlist request. The journey row lock serializes allocation. Feasible FIFO allocation checks the full requested segment and matching class; a blocked segment does not prevent a later compatible segment from using an otherwise idle seat. No class upgrades are implicit.

Cancellation and hold expiry promote eligible waiting passengers to an **unpaid hold**. They must add passenger details, review the stored fare and pay before expiry. Promotion queues an idempotent email to the verified account mailbox. Stale promotion emails are skipped after confirmation, cancellation or expiry. Closed services expire waiting entries instead of promoting them.

The existing Windows notification worker now sweeps expired holds before each email batch (normally every 30 seconds). This performs local DB work only, without invoking payment recovery or railway APIs. Searches also reconcile expired holds.

## Repeatable concurrency demo

From the project root, with PostgreSQL available and the backend virtual environment installed:

```powershell
.\scripts\demo-concurrency.ps1
```

This runs the actual booking service against an isolated PostgreSQL test database: 50 contenders, 10 concurrent threads, one seat. Assertions require exactly one successful hold, 49 rejected contenders, and one active booking. The runner creates and destroys test data; it does not alter normal bookings or call payment/email providers. The DB user needs permission to create a test database. Use a development database configuration, never production credentials.

Regression coverage also checks group rollback, PostgreSQL overlap constraints, adjacent segment reuse, class-specific waitlists, expiry, payment verification, lifecycle/refund events, PDF contents and email outbox delivery.

## Browser verification — 19 October 2026

Verified with a dedicated non-staff account and fictional passengers: empty results after sign-in, Mumbai Central–New Delhi local search, two-seat atomic hold, both passenger forms, INR 4,232 fare review, Razorpay Test Mode checkout opening, reload with persisted pending order, provider status check, whole-group cancellation, and cancelled history/email status. Both seats were released; no money was paid and no test email was delivered to an inbox.

Razorpay rejected the fictional contact number in its hosted form. Successful payment, ticket/PDF and paid cancellation/refund paths remain covered by mocked-provider backend regression tests; they were not fully verified through the hosted browser checkout during this pass. A successful sandbox checkout and refund walkthrough still need valid provider test inputs.

Final validation: 172 backend tests passed on PostgreSQL; 8 frontend tests passed; frontend production build and lint passed. The standalone concurrency script also passed (1 winner / 49 rejections). Browser-verified departure restrictions disable all closed class buttons with a readable reason. Existing notification worker and beat were restarted and reported healthy.
