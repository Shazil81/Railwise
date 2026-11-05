# Automatic booking and separate pages

BOOK opens `/book/:journeyId?from=...&to=...&class=...&quota=...`. It shows passenger details, class-specific berth preferences, contact details and booking preferences. There is no seat map or seat-number selection. Up to six passengers can be added or removed before submission; filling the form does not hold seats.

Before navigation, every BOOK action opens a confirmation showing the searched stations and the actual train terminals. A changed source or destination is highlighted; Back or Escape returns to the results without holding inventory. The native modal traps keyboard focus and restores it on close.

Passengers are added or edited in a dialog with full name, age, gender, country and class-specific berth preference. Summary cards support editing/removal before allocation. The same editor is used when changing an existing hold's passenger details. Country defaults to India for existing clients; suggestions are local and typed country names are supported.

The collapsible Other Preferences section contains auto-upgradation and confirmed-berths-only, plus optional preferred coach and GSTIN. These fields are persisted and returned by the owner-only booking API. Berth matching takes priority, then the requested coach is preferred when free; unavailable requests fall back within the allocated class. GSTIN receives format validation only, is not externally verified, does not change the fare and does not generate a tax invoice. Passenger/other preference edits remain locked after payment checkout begins. Migration `0013_passenger_other_preferences` adds these fields with backward-compatible defaults.

`POST /api/bookings/automatic/` validates passengers and the actual boarding segment. A PostgreSQL journey lock protects the complete allocation: expired holds are reconciled, inventory is checked again, the group is held, and berth preferences are applied in the same transaction. Invalid preferences or insufficient group capacity leave no partial booking. Fares are computed by the backend. A single sold-out passenger may join the existing waitlist unless confirmed-berths-only is enabled; groups require capacity for everyone. Waitlist promotion also considers berth preference within the eligible class.

On success, the app moves to `/booking/:bookingId` for fare review and existing verified Razorpay checkout. Reloading this URL restores the server booking. Existing bookings and PDF tickets also open on this page. The old inline seat-picker component has been removed. When hosting the built frontend, configure the web server to serve `index.html` for frontend routes; Vite already does this locally.

Berth preference is subject to availability. The review shows the actual berth and any fallback. Timetable dates on the passenger page include the boarding stop's day offset.

## Local demo login

The configured development database was missing the `demo` account. A non-staff local account has now been created and browser login verified. No existing user's password was reset. Future fresh local databases can use `python manage.py setup_demo_user` with `DEMO_PASSWORD` set in the shell. This command requires `DEBUG=True` and refuses to overwrite an existing account. Normal account signup/recovery remains available; production does not receive a built-in demo password.

## Verification

Backend tests cover allocation without seat IDs, multiple preferences, group rollback, overlap and adjacent segments, concurrent allocation, waitlisting, authentication, public journey details, and development-only demo setup. Browser verification covered demo login, BOOK navigation, a two-passenger Lower/Side Upper allocation, reload restoration, and releasing all test seats without making a payment.
