# Deployment runbook

Templates in `deploy/` target a Linux host, same-origin React/Nginx + Django/Gunicorn,
PostgreSQL and Redis. For the hosted Vercel/Render/Neon/Upstash demo, use
[the cloud runbook](CLOUD_DEPLOYMENT.md); the Linux templates themselves are not installed there.
Keep Razorpay in Test Mode for this portfolio. No railway API is required.

## Prepare

1. Place the checkout under `/srv/railwise`, create a dedicated unprivileged
   `railwise` account and assign that checkout to it.
2. Install Python 3.13+, Node 22+, PostgreSQL, Redis and Nginx. Create an application
   database/user; allow `btree_gist` (used by migrations). Do not expose DB/Redis ports.
3. Create the virtualenv, install `backend/requirements-production.txt`, run
   `npm ci --prefix frontend` and `npm run build --prefix frontend`.
4. Copy the variable names from `backend/.env.example` into `/etc/railwise.env`.
   Use a random 50+ character SECRET_KEY, `DEBUG=False`, explicit ALLOWED_HOSTS,
   HTTPS FRONTEND_URL, DB/Redis credentials, separate Razorpay test and webhook
   secrets, and SMTP credentials. Restrict this file to the service account/root.
5. Set `DJANGO_SETTINGS_MODULE=railway_core.production` in the deployment shell.
   Export the environment securely; then run `manage.py migrate`, `seed_data`,
   `collectstatic --noinput` and `check --deploy`. Do not seed a shared demo password.

## Serve

Install the three systemd templates, `systemctl daemon-reload`, and enable/start
`railwise-api`, `railwise-worker`, `railwise-beat`. Run exactly one beat instance.
Replace the example domain/certificate paths in `nginx.conf`, obtain a valid TLS
certificate, validate with `nginx -t`, then enable the server block.
Trust forwarded HTTPS headers only from your loopback Nginx proxy.
SSE uses long-lived WSGI threads: the provided thread count is a starting point,
not a capacity guarantee. Measure concurrent streams before increasing traffic.

Configure Razorpay's public HTTPS webhook endpoint as `/api/webhooks/razorpay/`
with the matching webhook secret and payment/refund events. Verify signatures,
duplicate deliveries and out-of-order events in Test Mode before sharing the URL.
Set FRONTEND_URL before sending verification/reset emails.

## Monitor and recover

- `systemctl status railwise-api railwise-worker railwise-beat`
- `journalctl -u railwise-worker`: recovery tasks every 60 seconds and emails every 30.
- Staff-only `/admin/operations/`: payment/refund backlog and notification failures.
- Alert on service restart loops, stale recovery, overdue refunds, failed mail and DB errors.
- Never mark payments/refunds successful manually to clear an alert.

## Backups and rollback

Before migrations, run `pg_dump --format=custom --file=/secure-backups/railwise.dump`
with connection details provided through protected PostgreSQL configuration.
Encrypt/restrict backups; retain them outside the application host. Rehearse a
`pg_restore` into a separate empty database, then run integrity tests there.
Do not commit dumps or restore over the running database. Record the release SHA,
take a backup, and plan data-compatible rollback before each schema change.
Switch back to a prior release only after reviewing migration compatibility.

Actual hosting, DNS, certificates, backup scheduling and reboot verification require
the chosen deployment environment. These templates do not provision paid services.
