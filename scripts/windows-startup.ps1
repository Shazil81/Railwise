param([ValidateSet('install','status','uninstall')][string]$Action='status')
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
$startupFolder=[Environment]::GetFolderPath('Startup')
$shortcutPath=Join-Path $startupFolder 'Railwise Email Services.lnk'
$targetScript=Join-Path $PSScriptRoot 'startup-notifications.ps1'
$hostExe=Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/powershell.exe'
$expectedArguments='-NoProfile -NonInteractive -WindowStyle Hidden -File "'+$targetScript+'"'
$shell=New-Object -ComObject WScript.Shell
if ($Action -eq 'status') {
    if (-not (Test-Path -LiteralPath $shortcutPath)) { Write-Output 'Railwise Windows startup is not installed.'; exit }
    $shortcut=$shell.CreateShortcut($shortcutPath)
    @{installed=$true;shortcut=$shortcutPath;target=$shortcut.TargetPath;arguments=$shortcut.Arguments;matches_project=($shortcut.Arguments -eq $expectedArguments)} | ConvertTo-Json
    exit
}
if ($Action -eq 'uninstall') {
    if (Test-Path -LiteralPath $shortcutPath) {
        $shortcut=$shell.CreateShortcut($shortcutPath)
        if ($shortcut.Arguments -ne $expectedArguments) { throw 'Shortcut belongs to a different configuration; removal stopped.' }
        Remove-Item -LiteralPath $shortcutPath
    }
    Write-Output 'Railwise Windows startup removed. Current background processes were not stopped.'
    exit
}
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot '.runtime/notification-services/config.json'))) { throw 'Set up notification services before installing Windows startup.' }
if (Test-Path -LiteralPath $shortcutPath) {
    $existing=$shell.CreateShortcut($shortcutPath)
    if ($existing.Arguments -ne $expectedArguments) { throw 'An unrelated startup shortcut has the same name; installation stopped.' }
}
$shortcut=$shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath=$hostExe
$shortcut.Arguments=$expectedArguments
$shortcut.WorkingDirectory=$projectRoot
$shortcut.WindowStyle=7
$shortcut.Description='Start Railwise Docker/Redis, project database and email-only Celery worker/beat after sign-in.'
$shortcut.Save()
Write-Output 'Railwise email services installed for this Windows user at sign-in.'
