# Engineering notes and interview guide

## What changed and why

The original design had PostgreSQL exclusion constraints and a Redis seat lock, but important paths bypassed validation or presented misleading success. An API failure could become a fake seat hold and payment success in the UI. Manual journey IDs obscured the booking flow. Invalid payloads could raise 500 errors, a seat from another train could be allocated, cancellation and booking history were missing, and a delayed task could expire a live hold. Waitlist promotion only searched requests contained inside the just-freed segment and marked unpaid passengers confirmed.

The revised implementation provides serializer validation, public inventory browsing, owner-scoped history/cancellation, idempotent confirmation, deadline-aware reconciliation, and FIFO promotion into a new payment hold. It preserves PostgreSQL's existing exclusion constraint and uses a single lock order for every allocation mutation.

## Seat occupancy

A route segment is a half-open interval `[from_seq, to_seq)`. Two bookings conflict when `a.from < b.to` and `a.to > b.from`, on the same seat and journey, while PENDING or CONFIRMED. Adjacent bookings `[1,3)` and `[3,5)` can reuse the same seat. A PostgreSQL GiST exclusion constraint independently enforces this invariant even for writes that bypass the service.

## Transaction strategy

All allocation changes lock the journey row first, and then any booking rows. Allocation, expiry, waitlist join, cancellation and payment use the same order. This serializes mutations for one journey and avoids the original mixture of booking-first and seat-first workflows. There is no distributed Redis lock to expire while a slow database transaction is still running. Redis remains the Celery broker.

Tradeoff: requests for separate seats on the same journey contend on one row. This is deliberate for this prototype. A production optimization would partition allocation locks by journey/seat, retain the exclusion constraint, and use a consistent lock protocol for promotion. That change needs contention benchmarks and additional deadlock tests; adding Redis alone does not prove correctness or performance.

## Expiry and fair promotion

Every deadline comparison uses server time. Read reconciliation and the background sweep acquire the same journey lock before releasing holds. A task fired early is a no-op. A confirmation retry on a confirmed booking is idempotent. Expired holds cannot become confirmed.

After release, promotion evaluates the **whole requested route** against every seat, oldest request first (`created_at`, `id`). Older requests that cannot fit do not prevent a younger non-conflicting request from using available capacity. Adjacent waitlisted segments can both occupy the same seat. A promoted booking receives a new ten-minute PENDING hold; it is not treated as paid. Duplicate active waitlist requests for the same user and segment are returned rather than added again.

Availability is a snapshot, not a reservation. Another request may win after the UI displays a seat. The hold endpoint rechecks under lock and returns 409 for that conflict; the frontend shows the error and lets the user refresh. UI errors never become synthetic ticket confirmations.

## Tests and evidence

The regression suite exercises overlap, adjacent reuse, database enforcement, route validation, foreign-train seats, early tasks, read-driven expiry, expired-payment persistence, payment retries, full-inventory waitlisting, duplicate requests, FIFO promotion, cross-boundary promotion, compatible segments, worker expiry, invalid API payloads, ownership and public-read/private-write access. One test dispatches 50 attempts through a pool of 10 threads and asserts exactly one active booking. Unexpected thread exceptions fail the test through `executor.map`.

This provides a reproducible local correctness argument. It does not measure peak requests per second, latency percentiles, distributed deployment availability, or real IRCTC behavior. Celery worker/broker integration is not covered by these tests; task logic and fallback reconciliation are covered.

## Resume wording

Built Railwise, a React/TypeScript and Django/PostgreSQL railway booking prototype with segment-based seat reuse, transactional holds, cancellation, and FIFO waitlist promotion. Added regression tests, including 50 competing booking attempts with one successful allocation, and designed a responsive booking dashboard with persisted booking management.

## Useful interview discussion

- Explain why `[1,3)` and `[3,5)` do not overlap and why a UI availability result cannot reserve a seat.
- Explain the distinct roles of transaction locks, database constraints and background workers.
- Discuss the journey-lock throughput tradeoff rather than claiming unmeasured scalability.
- Explain why an unpaid promoted booking is a hold and why real payment confirmation requires verified gateway evidence.
- Describe what happens if the Celery worker stops: expired state is reconciled on the next relevant request; completely idle expiry waits for a working scheduler.


Payment confirmation is now gateway-verified rather than simulated by the server. See [payment security notes](PAYMENTS.md) for the Phase 1 trust boundary and remaining recovery work.


Current measured results and release checks: [validation report](VALIDATION.md). The active Windows launcher uses operations mode; email-only notes describe the explicitly selected legacy profile.
