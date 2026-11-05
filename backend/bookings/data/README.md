# Station directory

`stations.json` contains 8,965 distinct code/name records derived from
https://github.com/datameet/railways/blob/master/stations.json (CC0), downloaded 2026-10-19.
Only code, name and state were retained; blank names and invalid codes were excluded.
This is a historical snapshot, not proof of current operation or express service.
Names used by seeded route snapshots override historical names. No runtime provider lookup is performed.
DataMeet train schedules are not imported. Bundled timetable snapshots are static
references and are never represented as live tracking.

## Bundled route references

`route_catalogue.json` contains 112 real timetable snapshots: 35 captured from the selected
RapidAPI provider on 2026-10-19 and 77 from public etrain.info timetable pages on 2026-10-22.
Each new entry records its `snapshot_source` and capture date. Train numbers/names, stops,
distances, running days and times are static reference facts. No source fare, platform,
passenger data or live railway inventory is imported. `demo_classes` is the supported
subset of reference classes; the 12-seat capacities are our own demo inventory.
The runtime never calls either source.
`seed_data` imports this reviewed file into PostgreSQL without needing an API key.

`route_coverage.json` lists the 10 regular exact-station PNBE–HWH services reviewed
against the saved source listing. Daily and weekly trains remain date-filtered.
Nearby-terminal services and special trains are not silently mixed into this list.
Temporary services 02024 and 04052 are included with explicit origin-date windows:
2026-03-08 through 2026-12-13 and 2026-10-02 through 2026-11-29, respectively.
Search and direct booking/payment validation enforce those dates. Day-2 boarding
uses the service origin date for validity, rather than shifting the special window.
This is not a guarantee of current operations or every announced special train.

The one-time expansion rejected unavailable schedules 12311/12312 (404) and 12810
(a halt crossing midnight, which the current single stop-day model cannot encode
without losing an arrival/departure day). No timetable facts were guessed.
