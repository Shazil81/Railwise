$ErrorActionPreference='Stop'
$testRoot=Split-Path -Parent $PSScriptRoot
$source=Join-Path $PSScriptRoot 'startup-notifications.ps1'
$tokens=$null;$errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile($source,[ref]$tokens,[ref]$errors)
if($errors){throw 'Startup script parse errors.'}
foreach($definition in $ast.FindAll({param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst]},$true)) {
    . ([scriptblock]::Create($definition.Extent.Text))
}
$passed=0
function Assert-Startup([bool]$Condition,[string]$Message){if(-not $Condition){throw $Message}}
$exitCode=Invoke-StartupNative $env:ComSpec @('/c','echo expected-not-ready 1>&2 & exit 7')
Assert-Startup ($exitCode -eq 7) 'Native stderr/nonzero code must not terminate startup.'
Assert-Startup ($ErrorActionPreference -eq 'Stop') 'Native helper must restore error policy.'
$passed++
$exitCode=Invoke-StartupNative $env:ComSpec @('/c','exit 0')
Assert-Startup ($exitCode -eq 0) 'Ready probe must preserve successful exit code.'
$passed++
$DependencyTimeoutSeconds=0
$failed=$false
try{Wait-Dependency {return $false} 'Test dependency'}catch{$failed=$_.Exception.Message -match 'startup timeout'}
Assert-Startup $failed 'Unavailable dependencies must time out.'
$passed++
$DependencyTimeoutSeconds=1
$testLog=Join-Path $testRoot '.runtime/notification-services/startup-test.log'
$logPath=$testLog
Wait-Dependency {return $true} 'Ready test dependency'
Assert-Startup ((Get-Content -LiteralPath $testLog -Tail 1) -match 'Ready test dependency ready') 'Ready dependencies should proceed immediately.'
$passed++
$lockPath=Join-Path $testRoot '.runtime/notification-services/windows-startup.lock'
$lock=[IO.File]::Open($lockPath,[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
try {
    & (Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/powershell.exe') -NoProfile -NonInteractive -File $source
    Assert-Startup ($LASTEXITCODE -eq 0) 'Duplicate startup must exit successfully without launching more services.'
}finally{$lock.Dispose()}
$passed++
$child=Start-Process -FilePath (Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/powershell.exe') -ArgumentList @('-NoProfile','-NonInteractive','-Command','exit 0') -WindowStyle Hidden -PassThru
$null=$child.Handle
$child.WaitForExit()
Assert-Startup ($child.ExitCode -eq 0) 'Hidden launcher exit status must be captured after waiting.'
$passed++
Write-Output "$passed Windows startup regression checks passed."
