# Train selection controls

Source and destination city terminal groups are searched automatically, even when
station codes such as PNBE and HWH are entered. Actual matched terminals remain
visible and determine booking/seat/quote stop sequences. No nearby checkbox is needed.

After Search trains, the results panel offers:

- Departure window: any, midnight–06:00, 06:00–12:00, 12:00–18:00 or 18:00–midnight, in IST.
- Coach class: all, SL, 3A, 2A, 1A, CC or EC.
- Maximum fare per passenger and maximum journey duration in hours.
- Earliest/latest departure, lowest/highest fare, shortest/longest journey sorting.
- Shown/total counts, Reset filters, and a dedicated empty-filter-results state.

Filters combine. Only matching class tiles are shown: a cheap SL fare cannot make
an expensive 3A tile pass a selected-3A budget. Fare sorting compares the lowest
fare among currently displayed classes. Waitlisted/closed classes remain clearly
labelled; this is not an available-seats-only filter.

Duration uses the actual boarding departure and destination arrival, including route
day offsets. This supports overnight and multi-day journeys without converting through
the browser timezone. Missing or inconsistent timetable times are not guessed: duration
is labelled unavailable, sorts last and does not pass a restrictive time/duration filter.

Filtering and sorting use the loaded local results without further provider/network
requests. A new route/date search resets filters; refreshing results retains them.
Server pricing is still rechecked when holding seats. Filtering never reserves seats.

Verified with actual PNBE–HWH results for 23 October 2026: the default request returns
8 trains, including RJPB–HWH and PNBE–KOAA. The shortest-duration ordering places 22348
first. Fare/departure orders and combined class/budget limits are regression-tested.

Final validation: 19 backend tests and 17 frontend tests passed; production build and
lint passed. Browser verification confirmed automatic 8-result terminal expansion,
shortest-duration sorting, and 3A plus INR 835 maximum fare producing only train
12352 (RJPB–HWH) at INR 833.50. Screenshot: `screenshots/train-filters.png`.
