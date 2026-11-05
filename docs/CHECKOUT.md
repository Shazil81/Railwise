# Passenger details, group bookings and fare review

Railwise supports 1–6 passengers per reserved-seat booking. Each passenger occupies one selected seat; no infant-without-seat or concession pricing is implemented. This is a project limit and sample fare policy, not a claim about IRCTC rules.

## Flow

1. Choose passenger count and one seat per passenger.
2. Continue: the backend holds every seat atomically for a shared ten-minute window. A conflict on any seat rolls back the entire group.
3. Enter each passenger's name, age (1–120) and gender, plus booking contact email and Indian-format mobile number. Use fictional contact data for the demo. Nothing is emailed or texted.
4. Save and review route/date, passengers, seat assignments and the server-calculated fare breakdown.
5. Check the review acknowledgement and proceed to Razorpay Test Mode checkout. The backend also requires saved valid details and a recorded review before creating a payment order.
6. One captured, verified payment for the complete total confirms all passengers in the same database transaction.

Active tickets shows one item per group. Continue booking reopens the saved details/review, including after a refresh. Cancel booking or release all seats cancels the group together. Full-group cancellation queues a tracked refund; partial cancellation is not implemented.

## Storage and invariants

The existing Booking row remains the seat-allocation unit, preserving the PostgreSQL exclusion constraint. A nullable self-reference groups companion allocations under a main booking. Razorpay order/payment references live only on the main booking, keeping their uniqueness guarantees intact. Every companion gets the same hold deadline, user, journey and segment through the group allocation service.

Name/age/gender are stored per allocation; contact and review metadata belong to the main booking. Requests must contain exactly one passenger for every group allocation. Owner checks and passenger-ID membership validation block attaching another booking's passengers. Details are editable before order creation; edits invalidate the recorded review. After an order is created, details are locked.

Fare is calculated by the backend when seats are held: INR 250 + INR 150 per route segment, per passenger. The review explicitly labels this as an illustrative project fare. No concessions, extra tax or booking fee are charged. The sum across allocation rows is converted to paise for Razorpay and independently verified on confirmation. Client-supplied amounts cannot change it.

Single-person legacy holds can be completed through the same passenger/review flow. Waitlist remains one passenger per request; a promoted booking must complete passenger details and review before payment. Group waitlisting is intentionally unavailable in the UI.

## API additions

- POST /api/bookings/ with journey_id, seat_ids (1–6 distinct IDs), from_seq, to_seq. Legacy seat_id remains accepted, mutually exclusive with seat_ids.
- GET /api/bookings/:id/ returns group details, passengers, contact, reviewed_at and fare_breakdown.
- PUT /api/bookings/:id/passengers/ with passengers [{booking_id, name, age, gender}], contact_email, contact_phone.
- POST /api/bookings/:id/review/ records review after validating details and live holds.
- Existing create-order and verify-payment endpoints operate on the complete group total. Companion rows cannot be paid/cancelled independently.

## Verification

48 PostgreSQL regression tests passed, including 14 new group/passenger tests: atomic rollback, count/seat uniqueness, passenger/contact validation, exact passenger membership, persistence, review invalidation, required details/review, total fare integrity, details locking, whole-group confirmation, underpayment rejection, cancellation/expiry, child-operation rejection and owner privacy. Gateway calls are mocked; no provider transaction was executed.

Browser verification covered two selected seats, passenger entry, INR 850 + INR 850 = INR 1,700 review, disabled checkout before acknowledgement, and resuming from Active tickets. Screenshots: [passenger details](screenshots/passenger-details.png), [fare review](screenshots/fare-review.png).

Webhook verification, abandoned-checkout recovery, payment-attempt history and late-payment/refund reconciliation are now implemented; see the lifecycle notes below. Keep this prototype in Test Mode until staging delivery and account configuration have been verified.


Update: webhook verification, payment-attempt history, pending/failed recovery and cancellation refund tracking are now implemented. See [payment lifecycle setup and limitations](PAYMENT_LIFECYCLE.md).
