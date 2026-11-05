# Portfolio presentation

## A 2–3 minute recording script

Record with fictional passenger/contact details and a fresh test-only account.
Do not expose .env, provider dashboards with secrets, or real passenger history.

- 0:00–0:25: guest station autocomplete, nearby terminals and date search.
- 0:25–0:50: class fares/filtering, terminal confirmation and two passengers.
- 0:50–1:20: fare review; explain a temporary hold and preference vs allocation.
- 1:20–1:50: Razorpay Test Mode, successful server verification and PDF.
- 1:50–2:15: cancellation estimate, refund progression and operations dashboard.
- 2:15–2:45: show the architecture and contention report; explain one winner,
  segment reuse, transactional group allocation and recovery after lost callbacks.

A demo video is not recorded automatically; this is the shot list for a recording.

## Resume wording

Built a React/TypeScript and Django/PostgreSQL railway booking prototype with
segment-based seat reuse, atomic multi-passenger allocation and expiring holds.
Implemented verified Razorpay test payments, durable refund recovery, Celery email
outbox delivery, SSE inventory updates and downloadable PDF confirmations.
Validated overlapping-seat contention with a reproducible PostgreSQL benchmark.

Use the measured counts from docs/VALIDATION.md; do not claim production traffic,
official railway inventory or throughput numbers beyond the local test scope.

## Discussion questions

- Why is the journey row locked before booking rows? What is the throughput tradeoff?
- Why use a PostgreSQL exclusion constraint as well as application checks?
- How do adjacent half-open segments reuse the same seat?
- What happens when a captured payment arrives after a hold expires?
- How are duplicate webhooks/refund requests reconciled?
- Why does provider-processed refund differ from independently verified bank credit?
- How does the durable email outbox behave across worker crashes?

## Final release checks needing an environment

Actual PC reboot/sign-in; Linux deployment and HTTPS/webhook reachability;
backup/restore rehearsal on a separate DB; mobile browser regression after deployment;
and a sanitized demo recording. Do not describe these as completed until performed.
