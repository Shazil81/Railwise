# Background services

The Windows launcher now uses `RAILWISE_BACKGROUND_MODE=operations`.
It supervises one worker consuming both `celery` and `railwise_notifications`, and
one beat scheduling email delivery (30 seconds), payment/refund recovery (60 seconds)
and expired-hold sweeps. PostgreSQL durable records allow the next sweep to resume work.
The explicitly selected `notifications` profile remains email-only for isolated use.

```powershell
./scripts/notifications.ps1 -Action start
./scripts/notifications.ps1 -Action status
./scripts/notifications.ps1 -Action stop
./scripts/windows-startup.ps1 -Action status
./scripts/windows-startup.ps1 -Action install
./scripts/test-windows-startup.ps1
```

First setup can pass `-PythonPath`, `-DbHost`, `-DbPort`, `-DbName`, `-DbUser`.
Use the SAME DB as the API. No password belongs in these command arguments;
backend/.env supplies credentials. The ignored config.json records only paths and DB identifiers.
Start Docker Desktop and PostgreSQL first. The launcher starts Compose Redis only.

The per-user Windows Startup shortcut runs after sign-in. It waits for Docker and
configured PostgreSQL, then launches the singleton supervisor hidden. It can start
only the existing workspace-owned PostgreSQL cluster on 55432; other DB targets
must already have a running service. It does not create/replace databases.

The supervisor owns child lifecycles and restarts crashed worker/beat processes.
Beat uses no standalone PID file, avoiding stale PID files after Windows shutdown;
the OS supervisor file lock prevents duplicate local supervisors. Do not run an
additional manual beat against the same database/broker.

Logs and heartbeats are under `.runtime/notification-services/`: worker.log, beat.log,
status.json, windows-startup-status.json and supervisor-error.log. `READY` plus a
fresh heartbeat is required; process creation alone does not establish task health.

Refund states advance only from provider evidence. Requested means a durable local
request; Processing includes a provider refund reference; Processed means provider
processing completed. Bank credit remains independently unconfirmed. In Razorpay
Test Mode no real bank movement occurs.

Actual Windows reboot/sign-in must still be checked on the user's machine.
A launcher smoke test with already-running dependencies is not a cold-boot test.
Linux systemd/TLS/backup templates and instructions are in DEPLOYMENT.md.
