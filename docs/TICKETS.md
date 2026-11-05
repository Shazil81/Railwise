# Booking confirmation and PDF tickets

After verified capture, checkout displays the booking confirmation. Booking history's **View ticket & PDF** action reopens it. Both the screen and PDF include every passenger's name, age, gender, coach, seat, individual fare, journey route/date/train, booking contact, group total and Razorpay order/payment references. Payment time is labelled **Payment recorded** because it is the local attempt creation timestamp, not a gateway settlement timestamp.

Authenticated owner-only endpoints:

| Method | Endpoint | Result |
| --- | --- | --- |
| GET | `/api/bookings/:id/confirmation/` | Verified group snapshot |
| GET | `/api/bookings/:id/ticket.pdf` | Downloadable PDF attachment |

Both endpoints recheck the lead booking, every passenger, assigned seats, route, full captured INR payment and refund ledger. Unpaid, incomplete, cancelled or refunded bookings cannot download a fresh ticket. Other users receive 404; unauthenticated requests are rejected. Responses disable caching. No public ticket links or payment signatures are exposed. Previously downloaded PDFs remain snapshots and cannot be recalled after cancellation.

PDFs use ReportLab (`pip install -r backend/requirements.txt`). For deployment, optionally set `TICKET_FONT_PATH` to a Unicode TrueType font supporting your passengers' names. Windows Arial is used when available, otherwise bundled Vera. Unsupported glyphs produce a useful error rather than an unreadable ticket.

Tickets are explicitly labelled portfolio demos, not valid for travel. The Railwise reference is not a real railway PNR. No timetable or official tariff is invented.

Install `backend/requirements-dev.txt` for PDF text assertions using pypdf. The 11 ticket regressions cover complete snapshots, PDF content, six long passenger names, owner access, missing payment evidence, missing passenger/route data, refunds, cancellation and escaped text. The full PostgreSQL suite passed 91 tests; frontend lint and production build passed. Browser testing verified the confirmation and PDF download success state. PDF layout was visually inspected for a two-passenger ticket and a two-page six-passenger stress fixture. No live gateway transaction was performed.

## Readable PDF design

The PDF uses a blue journey/reference header, green verified-payment and total-paid highlights, and lavender passenger allocation cards. Each passenger card includes name, age, gender, country, coach, seat, berth type and individual fare. The ordinary two-passenger fixture fits one A4 page; six long passenger names continue across pages without truncation. All display text is escaped, payment references wrap, and unsupported font glyphs fail explicitly. A fictional design sample is available in `output/pdf/railwise-ticket-design-sample.pdf`.

## Booking list and confirmation clarity

My bookings shows separately labelled booking and journey dates, saved local departure/arrival timestamps (including overnight day offsets), duration, full coach class, passenger preferences and consistently formatted INR amounts. View ticket and Download PDF are separate owner-only actions. Calendar exports use UTC instants from the saved timetable, escape/fold ICS content, and omit passenger/payment information. Journey sharing likewise omits private passenger/payment data. No official railway PNR is generated.

Cancellation requires a read-only owner-only `/api/bookings/:id/cancel-preview/` check and explicit confirmation. The preview returns zero refund when cancellation is closed; the cancellation service rechecks eligibility under its existing transaction lock. A processed provider refund does not prove bank credit. Payment method and timestamps are retained only from verified provider observations; older records can have no method. Email delivery channel is persisted, so local previews and unknown legacy deliveries are not shown as inbox-sent messages. Test-mode labels in the booking list are development-only.

The PDF now renders the same `departure_at`, `arrival_at`, `duration_minutes` and full `class_name` as the booking/confirmation response. The blue header labels **Booked on** in IST, separately from the highlighted **Journey date**. Both station panels show local departure/arrival time and date, including overnight day changes. Missing timetable times are labelled as not recorded. Payment metadata is arranged in two columns to keep a standard two-passenger ticket on one A4 page without reducing body font sizes. All 13 ticket tests pass, including PDF/page schedule consistency and six-passenger pagination; the updated normal and long-name samples were visually rendered and checked.
