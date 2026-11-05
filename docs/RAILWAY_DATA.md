# Local railway booking engine

The product has one route-search flow. It uses no live railway API. The About section,
external fares, live tracking and live/demo mode switches have been removed.

## Reference data

`backend/bookings/data/route_catalogue.json` bundles 112 static route snapshots, including
12566 Bihar S Kranti, 12306 Kolkata Rajdhani, 22348 Vande Bharat, 22436 Vande Bharat,
and 12004 Shatabdi; the full regional list is in [LOCAL_ROUTES.md](LOCAL_ROUTES.md). The recorded names, stop order, cumulative distances, timings and
running days are references captured on 2026-10-19 and 2026-10-22, not a promise of current railway service.
`seed_data` imports them without network access and creates 12 local seats per demo class.
Its repeat runs do not duplicate seats or reset users, bookings or journey inventory.
Conflicting booked routes are skipped instead of rewriting bookings. Unbooked legacy
references can be replaced; journey locks protect the booking check and replacement.

The historical national station directory supports name/code autocomplete; seeded route
names override it, and verified Kolkata is KOAA (the obsolete CP alias is excluded).
Only seeded services appear in results. The catalogue can be extended by importing
another reviewed snapshot, without changing runtime code or adding external calls.

The reviewed PNBE–HWH corridor contains 10 regular services and 2 specials. Specials
02024 and 04052 have explicit `valid_from`/`valid_until` origin-date bounds. Search
and booking/payment validation reject them outside those windows. The selected
boarding date can fall on day 2; validity always refers to the service origin date.
See `route_coverage.json` for the source and exact station/terminal scope.

Automatic [nearby city terminal search](NEARBY_TERMINALS.md) expands a selected city
or station through the bundled city alias groups. Both city terminal groups are included by default.
Alternative results retain the actual boarding/arrival codes and quote/booking stop
sequences; no railway API lookup or geographic service is involved.

Search takes a **boarding date**. The origin date is boarding date minus boarding-stop
journey day offset. Service instances are unique by train/origin date and lazily created
inside the next 60-day search window. Running days apply at the train origin. Returning
users can manage old bookings even when the route is outside the current catalogue.

## Fare rules v1

All currency arithmetic uses Decimal and rounds components to two places before summing.

| Class | Rate/km | Minimum base | Reservation | Tatkal minimum / maximum |
|---|---:|---:|---:|---:|
| SL | 0.65 | 100 | 20 | 50 / 200 |
| 3A | 1.50 | 250 | 40 | 150 / 400 |
| 2A | 2.20 | 350 | 50 | 200 / 500 |
| 1A | 3.50 | 600 | 60 | 300 / 750 |
| CC | 1.20 | 180 | 40 | 100 / 300 |
| EC | 2.70 | 450 | 60 | 250 / 600 |

Base is max(minimum, distance * rate). Tatkal adds 30% of base clamped to the class
bounds. At least 80% occupancy on the requested **class and segment** adds 10% of base.
General has no Tatkal surcharge. These are simplified project rules, including demo
Tatkal pricing; official Tatkal timing, quota pools, discounts and railway taxes are not
modeled. This is disclosed as project pricing in the UI.

A single journey row lock protects the allocation and price calculation. A group gets
one common quote before its seats are written; it cannot cross its own demand threshold
halfway through pricing. Each passenger's amount, class, quota and fare snapshot are
stored. Later demand/refreshes do not reprice that hold. The API never accepts a client
amount as payment authority; Razorpay uses the saved group sum.

## Inventory and contention

PostgreSQL journey row locks coordinate allocations across processes; an exclusion
constraint independently rejects overlapping active seat ranges. Segment bounds are
half-open [from,to), allowing a seat to be reused after the previous passenger's stop.
Group seats must belong to one train/class and are reserved all-or-nothing.

Holds expire after 10 minutes. Availability/search/quote/booking requests reconcile
expiry, so the interview demo does not require a worker to run at the right instant.
Cancellation/expiry promotes the oldest feasible waitlisted passenger in that class;
free seats from another class cannot silently upgrade or misprice a passenger.
Redis remains a background-job broker; no Redis distributed-seat-lock claim is made.

## API

- `/api/stations/search/?q=Patna`: local station suggestions.
- `/api/trains/search/?from=PNBE&to=HWH&date=YYYY-MM-DD&quota=GN`: local service/class quotes.
- `/api/journeys/{id}/quote/?from=1&to=3&travel_class=SL&quota=TQ`: internal fare components.
- `/api/journeys/{id}/availability/?from=1&to=3&travel_class=SL`: free local seats.
- `/api/bookings/`: authenticated group hold, with optional quota.
- `/api/waitlist/`: authenticated single-passenger waitlist, class and quota.

The removed `/api/trains/{number}/live/` and `/fares/` endpoints return 404. Existing
payment, cancellation, refund, account recovery, email and PDF endpoints remain intact.
Secrets in the user's .env were preserved, but railway provider keys are no longer read.

## Expanded regional coverage

The catalogue now has 112 trains, 486 unique stations and 2,299 route-stop records. See [complete route list](LOCAL_ROUTES.md). City aliases such as Mumbai/Bombay, Bengaluru/Bangalore and Trivandrum/Thiruvananthapuram work offline. City names and station codes automatically include the saved terminals at both ends; actual matched stations remain labelled.
