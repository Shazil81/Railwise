# Passenger berth preferences

Each passenger can request No preference, Lower, Middle, Upper, Side Lower or Side Upper. Options reflect the actual allocated class: Sleeper/3A support all five, 2A excludes Middle, 1A offers Lower/Upper, and CC/EC offer No preference. BOOK now opens a separate passenger page and the backend allots seats automatically; see [the current booking flow](AUTOMATIC_BOOKING_FLOW.md).

Saving passenger details plans allocations in the same class under the existing atomic journey lock. Specific requests are handled before passengers with no preference. Occupied seats on overlapping journey segments are excluded; group seat swaps are committed together. The held fare and expiry remain unchanged. Checkout locks passenger and berth changes after a payment order is created.

A preference is subject to availability. If no matching berth is free, an available alternate is allotted and fare review explicitly shows the requested and actual berth. Confirmation, PDF tickets and booking emails include the actual berth.

Seat numbering uses local demonstration layouts, not official rolling-stock coach charts. An explicit `Seat.berth_type` overrides the default numbering pattern. No runtime railway API is involved.

Availability cards use local Arial/Helvetica fonts, horizontal scrolling, class refresh controls, live counts, fares and BOOK buttons. Existing SSE count updates and reduced-motion behavior remain active.

Verification: 128 backend tests, 22 frontend tests, production build and lint. Browser verified an Upper seat S1-3 being reassigned to requested Lower S1-1 at the same fare; the disposable hold was released without payment.
