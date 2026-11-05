# PC-hosted jobs for the deployed app

The public frontend/API remain on Vercel/Render. PostgreSQL records live in Neon.
Three containers on the owner's PC run Celery worker, exactly one beat scheduler,
and private Redis. No Redis port is published to the host/internet. The worker
image runs as a non-root user; secrets and database backups are outside its build
context. No paid Render worker is provisioned.

The API stores pending work in durable database rows. Beat schedules email dispatch
every 30 seconds and hold/payment/refund recovery every 60 seconds. The worker
reads those Neon rows. It uses Docker Redis for its own queue, leaving Upstash for
the API's shared cache. This setup does not support arbitrary API-side `.delay()`
calls to the private broker; the current request paths do not use those calls.

## Controls (PowerShell, repository root)

```powershell
.\scripts\cloud-worker.ps1 -Action start
.\scripts\cloud-worker.ps1 -Action status
.\scripts\cloud-worker.ps1 -Action stop
docker compose -f compose.worker.yml logs --tail 50 worker beat
```

`start` builds the image if needed and starts/reuses the services. Named volumes
preserve the local broker and beat schedule. Do not run `down -v` unless intentionally
discarding that local state. Do not start another beat for the same job/database.

Private configuration is `.runtime/cloud-worker/worker.env`. For a fresh setup,
copy `deploy/cloud-worker.env.example` there and enter secrets locally. This file
is ignored by Git; never paste it into a chat or publish `docker compose config`
output (it can expand secrets). Use the same deployed Razorpay **test** account.

With `.runtime/cloud-worker/enabled` present, the existing Railwise Windows sign-in
shortcut starts these Docker services instead of the old native worker. The legacy
`notifications.ps1` command also routes to Docker, preventing a second native beat.
`restart: unless-stopped` handles container restarts after Docker starts; it cannot
run while the computer is off or asleep. Internet and Docker Desktop must be available.

## Migration performed — 5 November 2026

- Local `irctc`: 4 accounts, 12 booking rows, 112 trains, 97 journeys.
- Backed up local PostgreSQL and the previous Neon database as custom-format dumps.
- Restored to a **new** Neon database, `railwise_local_20261105`, over an unpooled
  TLS connection. All **24 public table counts matched**; the seat exclusion
  constraint was present. IDs, password hashes, payments and refund references
  were preserved. The restore was atomic and never used `--clean`.
- Backups/manifest: `.runtime/neon-migration/20261105T161630Z/`. These contain
  private data and stay on this computer, excluded from Git and Docker builds.
- Original local PostgreSQL and previous Neon `neondb` were preserved. Render's
  connection now points at the imported database. The previous Neon database's
  three cancelled deployment-test bookings remain there, not merged into local IDs.
- Verified public API cutover using a newly created temporary fictional account in
  the imported database; removed only that test account/token afterwards.
- Docker verified the imported database, private Redis and SMTP authentication
  without sending a test email. Logs confirmed scheduled jobs were received and
  successfully completed, including payment/refund recovery.
- The imported pending refund advanced automatically; all three refund records
  subsequently showed provider `PROCESSED`. This does not independently confirm bank credit.

The original `backend/.env` was not changed: native local Django still uses the
original local database. Writes there after the snapshot are not synced to Neon.
Do not switch Render back to the old database after new cloud writes without a
reconciliation plan. The two copies are not automatic replicas.

## Email delivery limits

Signup, verification and password-reset emails are now encrypted in a durable
account outbox and sent by this Docker worker, alongside booking notifications.
Booking notifications still require a verified account email. Both API and worker
need the same `SECRET_KEY` to encrypt/decrypt queued account tokens. SMTP
authentication/acceptance is not proof of inbox delivery. The PC must remain awake
with network access; otherwise messages wait and expired account links must be resent.

## GitHub instead of Celery?

GitHub Actions is appropriate for tests, builds and publishing Docker images. It
can also trigger coarse periodic maintenance, but scheduled workflows have a
five-minute minimum interval and can be delayed. It is not an always-on Celery
worker. Do not enable a second scheduler while this beat is running.

References: [GitHub schedule limitations](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule),
[Celery periodic tasks](https://docs.celeryq.dev/en/stable/userguide/periodic-tasks.html).
