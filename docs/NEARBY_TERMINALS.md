# Offline city terminal search

In Find trains, enter a city such as Patna and Kolkata (or choose PNBE and HWH),
then press Search trains. Both city terminal groups are included automatically;
there is no nearby checkbox. No search runs automatically on login.

- Patna: PNBE, RJPB and PPTA.
- Kolkata: HWH, KOAA, SDAH, SHM and SRC.
- Other curated city/alias groups are in `backend/bookings/data/city_aliases.json`.

These are curated city terminals, not an online distance-radius service. No station,
train or route API is called. Only stations and trains in the local DB participate.
This does not create connecting itineraries or transfers between terminals.

Each result shows actual boarding/destination names and codes. An alternative-terminal
notice calls out a changed station. Seat selection, price, waitlist and booking use
the **actual matched stop sequences**, never the typed city name or a different card's
segment. Check the actual terminal before booking.

A train stopping at several grouped terminals is listed once. It prefers the exact
station selected by the user, then the curated group order, subject to that boarding
date's timetable. Running days, date-bounded specials and day-2 boarding are evaluated
for each candidate pair. Same-city group searches are rejected. The API retains
`include_nearby=false` for an explicit exact-station query.

## API

```
GET /api/trains/search/?from=Patna&to=Kolkata&date=2026-10-23&include_nearby=true
GET /api/trains/search/?from=PNBE&to=HWH&date=2026-10-23&include_nearby=true
```

`include_nearby` accepts `true`/`1` or `false`/`0` and defaults to true. The response
includes `from_stations`, `to_stations`, and `include_nearby`. Each result includes
`origin_code`, `destination_code`, `boarding_date`, and `nearby_match`, alongside its
actual stop list and segment quotes. Autocomplete exposes `is_city` and a local
`terminal_group` so the frontend can distinguish a typed city from a station.

Verified through the running app API on 22 October 2026: the 23 October exact
PNBE–HWH search returned 6 trains; expansion returned 8, including RJPB–HWH and
PNBE–KOAA. Counts vary with origin operating days and special-service windows.

Current validation: 19 backend checks and 17 frontend tests passed, plus production
build and lint. Tests block external railway requests and verify actual matched-segment
booking, selected-station priority, deduplication, date offsets, special-service windows
and automatic city resolution. See [results controls](RESULT_FILTERS.md) for browser checks.
