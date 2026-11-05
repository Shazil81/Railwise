param([string]$Python = "$PSScriptRoot\..\backend\venv\Scripts\python.exe")
$ErrorActionPreference = 'Stop'
Push-Location "$PSScriptRoot\..\backend"
try {
    Write-Host 'PostgreSQL demo: 50 requests, 10 concurrent workers, one seat.'
    Write-Host 'Uses an isolated test database. No payments or real emails are sent.'
    & $Python manage.py test bookings.tests.BookingTests.test_fifty_concurrent_attempts_have_one_winner --noinput --verbosity 2
    if ($LASTEXITCODE -ne 0) { throw 'Concurrency demonstration failed.' }
    Write-Host 'PASS: 1 successful hold, 49 rejected contenders; exactly 1 active booking.'
} finally { Pop-Location }
