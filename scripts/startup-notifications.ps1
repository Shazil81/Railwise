param([int]$DependencyTimeoutSeconds = 300)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtime = Join-Path $projectRoot '.runtime/notification-services'
New-Item -ItemType Directory -Path $runtime -Force | Out-Null
$logPath = Join-Path $runtime 'windows-startup.log'
$bootStatusPath = Join-Path $runtime 'windows-startup-status.json'
$lock = $null
$stage = 'initializing'
function Write-StartupLog([string]$Message) {
    Add-Content -LiteralPath $logPath -Value ('{0:o} {1}' -f [DateTimeOffset]::Now, $Message) -Encoding utf8
}
function Write-BootStatus([string]$State) {
    @{state=$State;stage=$stage;updated_at=[DateTimeOffset]::Now.ToString('o');pid=$PID} | ConvertTo-Json | Set-Content -LiteralPath $bootStatusPath -Encoding utf8
}
function Invoke-StartupNative([string]$Executable, [string[]]$Arguments) {
    # Windows PowerShell otherwise treats native stderr as a terminating error,
    # even for expected readiness failures or Docker's normal progress output.
    $savedPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & $Executable @Arguments *> $null
        return [int]$LASTEXITCODE
    } finally { $ErrorActionPreference = $savedPreference }
}
function Wait-Dependency([scriptblock]$Probe, [string]$Name) {
    $deadline = [DateTime]::UtcNow.AddSeconds($DependencyTimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        if (& $Probe) { Write-StartupLog "$Name ready."; return }
        Start-Sleep -Seconds 5
    }
    throw "$Name did not become ready before the startup timeout."
}
try {
    try {
        $lock = [IO.File]::Open((Join-Path $runtime 'windows-startup.lock'),[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
    } catch [IO.IOException] {
        Write-StartupLog 'Another startup invocation is already running; duplicate skipped.'
        exit 0
    }
    Write-StartupLog 'Starting Railwise email dependencies after Windows sign-in.'
    if (Test-Path -LiteralPath (Join-Path $projectRoot '.runtime/cloud-worker/enabled')) {
        $stage='docker-cloud-worker'; Write-BootStatus 'STARTING'
        & (Join-Path $PSScriptRoot 'cloud-worker.ps1') -Action start
        $stage='ready'; Write-BootStatus 'READY'
        Write-StartupLog 'Docker worker/beat started for the deployed Neon database.'
        exit 0
    }
    $configPath = Join-Path $runtime 'config.json'
    if (-not (Test-Path -LiteralPath $configPath)) { throw 'Run notification setup once to save the interpreter/database configuration.' }
    $config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
    if (-not (Test-Path -LiteralPath $config.python)) { throw 'Configured Python interpreter is missing.' }
    $stage = 'docker'; Write-BootStatus 'STARTING'
    $dockerCommand=Get-Command docker.exe -ErrorAction SilentlyContinue
    if ($dockerCommand) { $dockerExe=$dockerCommand.Source } else {
        $dockerExe=Join-Path $env:LOCALAPPDATA 'Programs/DockerDesktop/resources/bin/docker.exe'
        if (-not (Test-Path -LiteralPath $dockerExe)) { $dockerExe=Join-Path $env:ProgramFiles 'Docker/Docker/resources/bin/docker.exe' }
        if (-not (Test-Path -LiteralPath $dockerExe)) { throw 'Installed Docker CLI was not found.' }
    }
    $env:PATH=(Split-Path -Parent $dockerExe)+';'+$env:PATH
    if ((Invoke-StartupNative $dockerExe @('info','--format','{{.ServerVersion}}')) -ne 0) {
        Write-StartupLog 'Starting installed Docker Desktop.'
        $null=Invoke-StartupNative $dockerExe @('desktop','start','--detach')
    }
    Wait-Dependency { return ((Invoke-StartupNative $dockerExe @('info','--format','{{.ServerVersion}}')) -eq 0) } 'Docker Desktop'
    $stage = 'database'; Write-BootStatus 'STARTING'
    $dbHost = [string]$config.db_host
    $dbPort = [string]$config.db_port
    $dbName = [string]$config.db_name
    $dbUser = [string]$config.db_user
    if (-not $dbHost -or -not $dbName -or -not $dbUser -or $dbPort -notmatch '^\d{1,5}$' -or [int]$dbPort -notin 1..65535) {
        throw 'Explicit database host, port, name and user are required in the saved notification config.'
    }
    $pgBin = 'C:/Program Files/PostgreSQL/18/bin'
    $pgReady = Join-Path $pgBin 'pg_isready.exe'
    if (-not (Test-Path -LiteralPath $pgReady)) { throw 'PostgreSQL readiness utility is missing; update the installation path.' }
    $dbReadyCode=Invoke-StartupNative $pgReady @('-h',$dbHost,'-p',$dbPort,'-U',$dbUser,'-d',$dbName,'-t','3')
    if ($dbReadyCode -ne 0 -and $dbHost -in @('127.0.0.1','localhost') -and $dbPort -eq '55432') {
        # Only this workspace's existing isolated cluster is eligible for automatic startup.
        $pgData = Join-Path $projectRoot '.runtime/postgres'
        if (-not (Test-Path -LiteralPath (Join-Path $pgData 'PG_VERSION'))) { throw 'Workspace PostgreSQL cluster is missing; no database was created.' }
        Write-StartupLog 'Starting the existing workspace PostgreSQL cluster on loopback port 55432.'
        $null=Invoke-StartupNative (Join-Path $pgBin 'pg_ctl.exe') @('-D',$pgData,'-l',(Join-Path $projectRoot '.runtime/postgres.log'),'-o','-h 127.0.0.1 -p 55432','-w','-t','30','start')
    }
    Wait-Dependency { return ((Invoke-StartupNative $pgReady @('-h',$dbHost,'-p',$dbPort,'-U',$dbUser,'-d',$dbName,'-t','3')) -eq 0) } 'Project PostgreSQL'
    $stage = 'redis-worker-beat'; Write-BootStatus 'STARTING'
    $hostExe = (Get-Process -Id $PID).Path
    $launcherPath = Join-Path $PSScriptRoot 'notifications.ps1'
    $childArguments = '-NoProfile -NonInteractive -File "{0}" -Action start' -f $launcherPath
    $child=Start-Process -FilePath $hostExe -ArgumentList $childArguments -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtime 'windows-startup-services.log') -RedirectStandardError (Join-Path $runtime 'windows-startup-services-error.log')
    # Wait only for the launcher; its detached supervisor must keep running.
    $null=$child.Handle
    $child.WaitForExit()
    if ($child.ExitCode -ne 0) { throw 'Notification startup failed; inspect windows-startup-services logs.' }
    $serviceState=Get-Content -LiteralPath (Join-Path $runtime 'status.json') -Raw | ConvertFrom-Json
    if (-not $serviceState.children.worker.running -or -not $serviceState.children.beat.running -or [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()-$serviceState.updated_at -ge 10) {
        throw 'Worker and beat readiness heartbeat was not confirmed.'
    }
    $stage = 'ready'; Write-BootStatus 'READY'
    Write-StartupLog 'Redis, email worker and beat are running. Payment and refund recovery is enabled.'
} catch {
    Write-BootStatus 'FAILED'
    Write-StartupLog "Startup failed at stage $stage. Inspect local startup/service logs and dependency configuration."
    exit 1
} finally {
    if ($lock) { $lock.Dispose() }
}
