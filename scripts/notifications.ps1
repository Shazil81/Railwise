param(
    [ValidateSet('start','status','stop')][string]$Action = 'status',
    [string]$PythonPath,
    [string]$DbHost,
    [string]$DbPort,
    [string]$DbName,
    [string]$DbUser
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (Test-Path -LiteralPath (Join-Path $projectRoot '.runtime/cloud-worker/enabled')) {
    & (Join-Path $PSScriptRoot 'cloud-worker.ps1') -Action $Action
    exit 0
}
$runtime = Join-Path $projectRoot '.runtime/notification-services'
$statusPath = Join-Path $runtime 'status.json'
$configPath = Join-Path $runtime 'config.json'
function Read-ServiceStatus {
    if (Test-Path -LiteralPath $statusPath) {
        try {
            $state = Get-Content -LiteralPath $statusPath -Raw | ConvertFrom-Json
            if ([DateTimeOffset]::UtcNow.ToUnixTimeSeconds() - $state.updated_at -lt 10) { return $state }
        } catch { }
    }
    return $null
}
$state = Read-ServiceStatus
if ($Action -eq 'status') {
    if ($state) { $state | ConvertTo-Json -Depth 5 } else { Write-Output 'Notification services are stopped or unhealthy.' }
    exit
}
if ($Action -eq 'stop') {
    if (-not $state) { Write-Output 'Notification services are already stopped or unhealthy.'; exit }
    Set-Content -LiteralPath (Join-Path $runtime 'stop.request') -Value 'stop' -Encoding utf8
    for ($i=0; $i -lt 25; $i++) {
        Start-Sleep -Seconds 1
        if (-not (Test-Path -LiteralPath $statusPath)) { Write-Output 'Notification worker and beat stopped.'; exit }
    }
    throw 'Shutdown is still pending. Inspect supervisor.log; no unrelated process was terminated.'
}
if ($state) { Write-Output 'Notification services are already running.'; $state | ConvertTo-Json -Depth 5; exit }
New-Item -ItemType Directory -Path $runtime -Force | Out-Null
if (Test-Path -LiteralPath $configPath) {
    $saved = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
    if (-not $PythonPath) { $PythonPath = $saved.python }
    if (-not $DbHost) { $DbHost = $saved.db_host }
    if (-not $DbPort) { $DbPort = $saved.db_port }
    if (-not $DbName) { $DbName = $saved.db_name }
    if (-not $DbUser) { $DbUser = $saved.db_user }
}
if (-not $PythonPath) { $PythonPath = Join-Path $projectRoot 'backend/venv/Scripts/python.exe' }
if (-not (Test-Path -LiteralPath $PythonPath)) { throw 'Pass -PythonPath with the Python interpreter containing backend dependencies.' }
$pythonPackages = Join-Path $projectRoot 'backend/venv/Lib/site-packages'
if (Test-Path -LiteralPath $pythonPackages) { $env:PYTHONPATH = $pythonPackages }
$env:PYTHONUTF8 = '1'
$env:RAILWISE_BACKGROUND_MODE = 'operations'
# Native psycopg fallback for this Windows development installation.
$pgBin = 'C:/Program Files/PostgreSQL/18/bin'
if (Test-Path -LiteralPath $pgBin) { $env:PATH = $pgBin + ';' + $env:PATH; $env:PSYCOPG_IMPL = 'python' }
if ($DbHost) { $env:DB_HOST = $DbHost }
if ($DbPort) { $env:DB_PORT = $DbPort }
if ($DbName) { $env:DB_NAME = $DbName }
if ($DbUser) { $env:DB_USER = $DbUser }
& $PythonPath -c 'import django, celery, redis'
if ($LASTEXITCODE -ne 0) { throw 'Python dependencies unavailable. Check -PythonPath and backend requirements.' }
# Start only Redis; do not replace the running app database or process gateway jobs.
$savedPreference=$ErrorActionPreference
try {
    $ErrorActionPreference='Continue'
    & docker compose -f (Join-Path $projectRoot 'docker-compose.yml') up -d --wait redis
    $dockerExit=$LASTEXITCODE
} finally { $ErrorActionPreference=$savedPreference }
if ($dockerExit -ne 0) { throw 'Redis did not start. Start Docker Desktop first.' }
@{python=$PythonPath;db_host=$DbHost;db_port=$DbPort;db_name=$DbName;db_user=$DbUser} | ConvertTo-Json | Set-Content -LiteralPath $configPath -Encoding utf8
$arguments = @('"'+(Join-Path $projectRoot 'backend/manage.py')+'"','run_notification_services')
Start-Process -FilePath $PythonPath -ArgumentList $arguments -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtime 'supervisor.log') -RedirectStandardError (Join-Path $runtime 'supervisor-error.log') | Out-Null
for ($i=0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 1
    $state = Read-ServiceStatus
    if ($state) { Write-Output 'Email and payment recovery worker and beat started.'; $state | ConvertTo-Json -Depth 5; exit }
}
throw 'Startup not confirmed. Inspect .runtime/notification-services/supervisor-error.log.'
