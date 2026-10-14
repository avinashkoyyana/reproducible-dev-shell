#Requires -Version 7.4
[CmdletBinding(SupportsShouldProcess)]
param(
    [string] $PythonPath,
    [string] $ArchivePath,
    [switch] $SkipSchedule
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (-not $IsWindows -or [Runtime.InteropServices.RuntimeInformation]::OSArchitecture -ne 'X64') {
    throw 'This graph package currently supports Windows x64. See docs/graph-tools.md for WSL boundaries.'
}
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if ($principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this per-user installer from a non-elevated PowerShell 7 window.'
}
$taskName = 'ReproDevShell Graph Freshness'
$stateDirectory = Join-Path $HOME '.local\share\repro-graph'
$runner = Join-Path $stateDirectory 'run.ps1'
$pwshPath = Join-Path $PSHOME 'pwsh.exe'
if (-not $SkipSchedule) {
    $legacy = Get-ScheduledTask -TaskName 'ATS Local Graph Freshness' -ErrorAction SilentlyContinue
    if ($legacy -and $legacy.State -ne 'Disabled') {
        throw 'The existing ATS graph task is active. Keep it, or explicitly migrate using docs/graph-tools.md; do not run duplicate sweep tasks.'
    }
    $existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($existing -and (@($existing.Actions).Count -ne 1 -or $existing.Actions.Arguments -notlike "*$runner*")) {
        throw "An unrelated task already uses '$taskName'. It was preserved."
    }
}
if (-not $PSCmdlet.ShouldProcess($HOME, 'Install pinned graph tools, merge Codex/Cursor configuration and configure per-user refresh')) {
    return
}
if (-not $PythonPath) {
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        throw 'Install the base developer shell (includes uv), or supply -PythonPath for Python 3.11+.'
    }
    & uv python install 3.11
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 installation failed.' }
    $PythonPath = (& uv python find 3.11 | Select-Object -Last 1).Trim()
    if ($LASTEXITCODE -ne 0) { throw 'Could not locate Python 3.11.' }
}
& $PythonPath -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)'
if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 or newer is required.' }
$setupArguments = @((Join-Path $PSScriptRoot 'graph\setup_graph.py'))
if ($ArchivePath) { $setupArguments += @('--archive', (Resolve-Path -LiteralPath $ArchivePath).Path) }
& $PythonPath @setupArguments
if ($LASTEXITCODE -ne 0) { throw 'Graph setup failed. No scheduled task was registered.' }
if (-not $SkipSchedule) {
    $action = New-ScheduledTaskAction -Execute $pwshPath -Argument ('-NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -File "' + $runner + '"') -WorkingDirectory $stateDirectory
    $triggers = @(
        (New-ScheduledTaskTrigger -AtLogOn -User $identity.Name)
        (New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5))
    )
    $taskPrincipal = New-ScheduledTaskPrincipal -UserId $identity.Name -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 1)
    if ($existing) {
        Export-ScheduledTask -TaskName $taskName | Set-Content -LiteralPath (Join-Path $stateDirectory ('task-backup-' + (Get-Date -Format 'yyyyMMddHHmmss') + '.xml'))
    }
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $triggers -Principal $taskPrincipal -Settings $settings -Description 'Local graph refresh; no model calls or credentials.' -Force | Out-Null
    Start-ScheduledTask -TaskName $taskName
    Write-Host 'Refresh scheduled every five minutes and at sign-in. The first sweep is running; check last-run.json before claiming success.'
}
Write-Host "Machine-local configuration: $stateDirectory"
Write-Host 'Restart Codex/Cursor. Follow docs/graph-tools.md to verify graph retrieval and edit freshness.'
