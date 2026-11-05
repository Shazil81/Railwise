# Live local inventory and booking preferences

Train results open one same-origin EventSource connection for their actual matched
journey/segment list. `/api/inventory/stream/?segments=[[id,from,to],...]` returns SSE
`inventory` events containing class counts/capacity and a timestamp. Passenger,
account and payment information is never streamed. No railway API is involved.

The server checks the local PostgreSQL inventory every 3 seconds, reconciles expired
holds/waitlists, and emits a snapshot only when counts change. Unchanged snapshots
produce heartbeat comments. Connections rotate after 60 seconds; the client reconnects
with backoff, closes streams on unmount/new search, and labels connection loss. This
is SSE delivery with database polling on the server, not a PostgreSQL NOTIFY/Redis
pub-sub pipeline. Each streaming connection occupies a development-server thread;
production hosting must support streaming and disable response buffering.

Available-seat numbers update without page reload and flash subtly for 900 ms.
`prefers-reduced-motion` disables the animation. Counts use polite live-region updates.
The open seat map reconciles count changes while retaining still-available selections.
Loaded fare previews remain unchanged by count messages so filters do not unexpectedly
remove an active checkout. The server recalculates authoritative fare when holding seats.

## Preferences

Both checkboxes appear before holding seats and on the passenger-details page. They
are stored on all group members and remain visible on fare review. Editing preferences
resets review; once a Razorpay order exists, passenger/preferences editing is locked.

- **Book only if confirm berths are allotted** forbids joining the waitlist on the
  backend and disables that action in the UI. A group hold still requires all selected
  seats atomically. This option does not bypass verified payment or instantly issue a
  confirmed ticket. Payment is rejected if any passenger lacks an allocated seat.
- **Consider for Auto-Upgradation** permits a higher class during this project's
  waitlist promotion, subject to inventory. Same-class queues are allocated first.
  Supported ladders are SL → 3A → 2A → 1A and CC → EC; no downgrade or cross-family
  move occurs. The nearest available higher class is preferred. The original quoted
  fare and requested class remain stored, while `allocated_class` records the seat's
  actual class. The upgrade does not add a charge. Promotion creates an unpaid hold
  and requires passenger details/review/payment; it is never automatic payment.

This is a local project allocation policy, not Indian Railways chart preparation or
an upgrade guarantee for already confirmed passengers. Checking both boxes is allowed:
confirmed-only blocks waitlisting, so there is no waitlist upgrade to consider.

## Verification

Migration `0011_booking_preferences` was applied to both existing local databases.
Browser verification used a dedicated unpaid local demo hold: an already-open result
changed 12 → 11 → 12 over SSE without reloading. The hold was released; no payment was
made and no inbox email was sent. Both preference checkboxes were verified in-browser.
See `screenshots/live-seats-preferences.png`.

Tests cover stream snapshots/heartbeats, browser `Accept: text/event-stream` negotiation,
bounded segment validation, no private data in events, group preference persistence,
confirmed-only rejection, upgrade consent/class priority, original-fare preservation,
actual-class inventory accounting and checkout locking/missing-seat rejection.

Final validation: 127 targeted PostgreSQL backend tests (99 allocation/payment/rules/
SSE checks plus 28 notification/ticket checks) passed. All 20 frontend tests,
production build and lint passed. No railway provider, real payment or inbox send
was used in the browser pulse demonstration.
