param([ValidateSet('start','status','stop')][string]$Action='status')
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
$composeFile=Join-Path $projectRoot 'compose.worker.yml'
$privateEnv=Join-Path $projectRoot '.runtime/cloud-worker/worker.env'
if(-not (Test-Path -LiteralPath $privateEnv)){throw 'Private worker configuration is missing. Follow docs/DOCKER_WORKER.md.'}

function Invoke-Docker([string[]]$DockerArgs) {
    & docker @DockerArgs
    if($LASTEXITCODE -ne 0){throw 'Docker command failed. Check Docker Desktop and the service logs.'}
}
if($Action -eq 'start') {
    & docker info --format '{{.ServerVersion}}' *> $null
    if($LASTEXITCODE -ne 0) {
        Invoke-Docker @('desktop','start','--detach')
        $deadline=[DateTime]::UtcNow.AddSeconds(120)
        do {
            & docker info --format '{{.ServerVersion}}' *> $null
            if($LASTEXITCODE -eq 0){break}
            if([DateTime]::UtcNow -ge $deadline){throw 'Docker Desktop startup timed out.'}
            Start-Sleep -Seconds 3
        } while($true)
    }
    Invoke-Docker @('compose','-f',$composeFile,'up','-d','--build','--wait','--wait-timeout','90')
} elseif($Action -eq 'stop') {
    Invoke-Docker @('compose','-f',$composeFile,'stop')
} else {
    Invoke-Docker @('compose','-f',$composeFile,'ps')
}
