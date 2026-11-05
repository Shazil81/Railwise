# Account onboarding

New visitors can create a Railwise account from the sign-in dialog. Username, contact email, password and confirmation are validated on the server. Django password validators reject weak passwords; create_user stores a password hash. Signup cannot set staff or superuser flags. Account email starts unverified; completing its email link establishes mailbox access, not passenger identity.

POST `/api/accounts/signup/` creates an account and token. POST `/api/token/` retains existing username/password login. POST `/api/accounts/logout/` revokes the current token; with DRF's one-token-per-user model, this signs out other clients sharing that token. Login/signup responses disable caching. Failed logout keeps the local login so the user can retry revocation; an already-invalid token is cleared locally.

Login is limited to 10 requests per minute per IP, signup to 5 per hour per IP. These DRF cache-based limits are basic usage controls, not a brute-force guarantee: the default local-memory cache is process-local and checks are not atomic. Production requires shared cache and edge/proxy limits with trusted proxy configuration. See [DRF throttling](https://www.django-rest-framework.org/api-guide/throttling/).

Password validation follows [Django's password validation API](https://docs.djangoproject.com/en/6.0/topics/auth/passwords/). Browser tokens now stay only in memory for the current loaded page. Fresh loads/refreshes start as a guest; legacy localStorage token/username entries are removed. Search, station suggestions and class comparisons are public. BOOK asks for explicit sign-in, retains the selected train/class, then opens terminal confirmation. Direct passenger/booking URLs also require sign-in. Deploy over HTTPS and plan a reviewed session/cookie strategy before public use. Email verification and password reset support console emails locally; real delivery requires SMTP configuration. Booking notifications remain a separate phase.

Account regressions cover password hashing, private access, invalid inputs, duplicate usernames, forbidden privilege assignment, token revocation/re-login, inactive users and both throttle limits. Email verification and password recovery are now implemented; see [current email flow and setup](EMAIL_ACCOUNTS.md).

Validation on 19 October 2026: the full PostgreSQL suite passed 98 tests; frontend lint and production build passed. Browser visual verification was blocked by the browser URL security policy, so no new account UI screenshot is claimed.
