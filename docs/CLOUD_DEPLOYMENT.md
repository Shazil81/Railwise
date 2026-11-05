# Vercel + Render + Neon + Upstash

Deployment is not complete until the public URLs and payment flow are verified.
Use a new Neon database; do not upload local users, bookings or database dumps.

## Hosted resources — 5 November 2026

- Frontend: https://railwise-phi.vercel.app/ (Vercel Hobby, root `frontend`).
- API: https://railwise-api.onrender.com/ (Render Free, Singapore, root `backend`).
- Database: dedicated Neon `railwise` PostgreSQL 18 project in Singapore.
- Redis: existing authorized Upstash free instance, with `railwise-production`
  cache prefix and `railwise:` broker/result prefix for any future Celery processes.
  Existing applications' keys are not changed or flushed.
- No local user data/database dump was imported; only the bundled catalogue was seeded.
- A new synthetic account verified signup/login, two-passenger holds, fare review,
  creation of a real Razorpay **test order**, unpaid PDF denial, cancellation and logout.
  No test payment was captured in this deployment smoke check.
- Health, station lookup, nearby-terminal search (8 PNBE/HWH results on 6 November),
  and Redis-backed SSE class counts were verified over public HTTPS.
- Email, scheduled recovery, public webhook delivery and a fresh captured-payment/PDF
  flow remain unverified on this hosted environment. Do not infer them from local tests.

## Free plan limits

- Render Free API sleeps after inactivity and shares monthly free compute hours
  with other services in the workspace. Expect a cold start.
- No always-on Celery worker/beat is provisioned by this free blueprint.
  Scheduled email dispatch, hold sweeps and payment/refund recovery need an
  independently running worker/beat before claiming background automation.
  Webhook delivery and explicit payment-status checks are separate mechanisms.
- Render Free blocks SMTP ports 25/465/587. Gmail SMTP will not deliver there.
  Add an HTTPS email provider integration before promising verification,
  password-reset or booking emails. Do not use console logs as inbox delivery.
- Upstash's request allowance can be consumed by SSE and Celery polling. Use
  dedicated databases, monitor usage, and do not enable paid overages.

## Setup order

1. Neon: create a dedicated **Railwise** free PostgreSQL project/database in a
   region close to Render. Use its TLS connection URI as `DATABASE_URL`.
   The migration role must support `CREATE EXTENSION btree_gist`.
2. Upstash: create a dedicated **railwise** free Redis database nearby. Copy the
   **TCP** `rediss://...` URI, not the REST endpoint, to `REDIS_URL`.
3. Render: import `Shazil81/Railwise`, root `backend`, Python 3.13.9, **Free**.
   Build: `bash build.sh`.
   Start: use the exact `startCommand` in root `render.yaml`.
   Health check: `/api/health/`.
4. Set `DJANGO_SETTINGS_MODULE=railway_core.cloud`, `SECRET_KEY` (random 64+
   characters), `DATABASE_URL`, `REDIS_URL`, explicit backend `ALLOWED_HOSTS`,
   and the final HTTPS Vercel `FRONTEND_URL`. No wildcard origins/hosts.
   Set fresh Razorpay **test** credentials and separate webhook secret as protected
   Render environment variables. Never expose them through `VITE_*` variables.
5. Vercel: import only root `frontend`, Vite, `npm run build`, output `dist`.
   Set public `VITE_API_BASE_URL=https://<actual-render-host>/api` before building.
   `frontend/vercel.json` supports direct SPA links. API/SSE connect directly to
   Render so no Vercel proxy buffers the inventory stream.
6. Update Render `FRONTEND_URL` to the actual Vercel production origin and redeploy.
   Set Razorpay Test Mode webhook URL to
   `https://<actual-render-host>/api/webhooks/razorpay/` and configure matching
   signature secret/events. Do not change the local `.env` or migrate local data.

## Verification

- `/api/health/` returns `{"status":"ok"}` and admin static CSS loads.
- Guest city/station search works after cold start, with no runtime railway API.
- Open two search tabs; verify SSE counts update and disconnect when hidden.
- Register/login, complete synthetic passengers and Razorpay test checkout.
- Confirm the signed payment, ticket PDF, cancellation and refund provider state.
- Explicitly report background/email limitations until those services are enabled.

For a later paid deployment, start **one** beat process and a worker consuming
`celery,railwise_notifications` with the same cloud environment. Never run multiple
beat schedulers. Keep TLS verification enabled for Neon and Upstash.

Official references: [Render free limits](https://render.com/docs/free),
[Neon Django](https://neon.com/docs/guides/django),
[Upstash Celery](https://upstash.com/docs/redis/integrations/celery),
[Vercel Vite](https://vercel.com/docs/frameworks/frontend/vite).
