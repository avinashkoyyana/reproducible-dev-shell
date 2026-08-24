#Requires -Version 5.1
[CmdletBinding()]
param(
    [string] $Distro = 'Ubuntu',
    [switch] $SkipWindowsPackages,
    [switch] $SkipPowerShellConfig,
    [switch] $SkipWSL,
    [switch] $SkipNerdFont,
    [switch] $SkipAgentClis,
    [switch] $IncludeWslAgentClis,
    [switch] $IncludeCloudTools,
    [switch] $Upgrade,
    [switch] $RemoveStorePowerShell
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$repoRoot = $PSScriptRoot
. (Join-Path $repoRoot 'scripts\Bootstrap.Common.ps1')
$packages = Import-PowerShellDataFile (Join-Path $repoRoot 'config\packages.psd1')

if (-not (Test-IsAdministrator)) {
    throw 'Run this script from an elevated PowerShell window (Run as administrator).'
}

if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) {
    throw 'WinGet is required. Install or update Microsoft App Installer, then rerun this script.'
}

Write-Host 'Reproducible developer shell bootstrap' -ForegroundColor Magenta
Write-Host "Source: $repoRoot"

if ($RemoveStorePowerShell -and -not (Test-Path "$env:ProgramFiles\PowerShell\7\pwsh.exe")) {
    $storePackage = Get-AppxPackage -Name Microsoft.PowerShell -ErrorAction SilentlyContinue
    if ($storePackage) {
        Write-Host 'Removing the per-user Store/MSIX PowerShell package...' -ForegroundColor Yellow
        $storePackage | Remove-AppxPackage
    }
}

if (-not $SkipWindowsPackages) {
    $failures = New-Object System.Collections.Generic.List[string]
    foreach ($package in $packages.WindowsPackages) {
        try {
            Install-WingetPackage -Package $package -Upgrade:$Upgrade
        }
        catch {
            $failures.Add($package.Id)
            Write-Warning $_.Exception.Message
        }
    }

    $requiredFailures = @($packages.WindowsPackages | Where-Object { $_['Required'] -and $failures.Contains($_.Id) })
    if ($requiredFailures.Count -gt 0) {
        throw "Required package installation failed: $($requiredFailures.Id -join ', ')"
    }

    if ($failures.Count -gt 0) {
        Write-Warning "Optional packages that did not install: $($failures -join ', ')"
    }
}

if ($IncludeCloudTools) {
    $cloudFailures = New-Object System.Collections.Generic.List[string]
    foreach ($package in $packages.CloudPackages) {
        try {
            Install-WingetPackage -Package $package -Upgrade:$Upgrade
        }
        catch {
            $cloudFailures.Add($package.Id)
            Write-Warning $_.Exception.Message
        }
    }

    if ($cloudFailures.Count -gt 0) {
        throw "Cloud tool installation failed: $($cloudFailures -join ', ')"
    }
}

$pwshPath = "$env:ProgramFiles\PowerShell\7\pwsh.exe"
if (-not (Test-Path -LiteralPath $pwshPath)) {
    $pwshCommand = Get-Command pwsh.exe -ErrorAction SilentlyContinue
    if ($pwshCommand) {
        $pwshPath = $pwshCommand.Source
    }
    else {
        throw 'PowerShell 7 was not found after package installation.'
    }
}

if (-not $SkipPowerShellConfig) {
    $configureArguments = @(
        '-NoLogo', '-NoProfile', '-ExecutionPolicy', 'Bypass',
        '-File', (Join-Path $repoRoot 'scripts\Configure-PowerShell.ps1')
    )
    if ($Upgrade) { $configureArguments += '-UpgradeModules' }
    if ($SkipNerdFont) { $configureArguments += '-SkipNerdFont' }

    & $pwshPath @configureArguments
    if ($LASTEXITCODE -ne 0) {
        throw "PowerShell configuration failed with exit code $LASTEXITCODE."
    }
}

if (-not $SkipAgentClis) {
    $agentArguments = @(
        '-NoLogo', '-NoProfile', '-ExecutionPolicy', 'Bypass',
        '-File', (Join-Path $repoRoot 'scripts\Install-AgentClis.ps1')
    )
    if ($Upgrade) { $agentArguments += '-Upgrade' }

    & $pwshPath @agentArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Developer agent CLI installation failed with exit code $LASTEXITCODE."
    }
}

if (-not $SkipWSL) {
    Write-Host 'Updating WSL and selecting WSL 2...' -ForegroundColor Cyan
    & wsl.exe --update
    & wsl.exe --set-default-version 2

    $installedDistros = @(& wsl.exe --list --quiet 2>$null | ForEach-Object { ($_ -replace "`0", '').Trim() } | Where-Object { $_ })
    if ($installedDistros -notcontains $Distro) {
        Write-Host "Installing $Distro without launching it..." -ForegroundColor Cyan
        & wsl.exe --install --distribution $Distro --no-launch
        Write-Warning "WSL installed $Distro. Restart Windows if requested, launch '$Distro' once to create your Linux user, then rerun install.ps1."
        exit 3010
    }

    $verboseDistroList = @(& wsl.exe --list --verbose 2>$null | ForEach-Object { ($_ -replace "`0", '').TrimEnd() })
    $distroVersionPattern = '^\s*\*?\s*' + [regex]::Escape($Distro) + '\s+.+\s+2\s*$'
    if (-not ($verboseDistroList -match $distroVersionPattern)) {
        & wsl.exe --set-version $Distro 2
        if ($LASTEXITCODE -ne 0) {
            throw "Could not convert '$Distro' to WSL 2. Close programs using the distro, run 'wsl --shutdown', and rerun install.ps1."
        }
    }

    $linuxUserOutput = @(& wsl.exe --distribution $Distro -- sh -lc 'id -un' 2>$null | Select-Object -Last 1)
    $linuxUser = if ($linuxUserOutput.Count -gt 0 -and $null -ne $linuxUserOutput[0]) {
        $linuxUserOutput[0].Trim()
    }
    else {
        ''
    }
    if (-not $linuxUser -or $linuxUser -eq 'root') {
        throw "Launch '$Distro' once and create its normal Linux user, then rerun install.ps1."
    }

    $previousRepoPath = [Environment]::GetEnvironmentVariable('REPRO_DEV_SHELL_ROOT', 'Process')
    $previousWslEnv = [Environment]::GetEnvironmentVariable('WSLENV', 'Process')
    try {
        $env:REPRO_DEV_SHELL_ROOT = $repoRoot
        $env:WSLENV = if ($previousWslEnv) {
            "REPRO_DEV_SHELL_ROOT/p:$previousWslEnv"
        }
        else {
            'REPRO_DEV_SHELL_ROOT/p'
        }

        $linuxPathOutput = @(& wsl.exe --distribution $Distro -- printenv REPRO_DEV_SHELL_ROOT | Select-Object -Last 1)
    }
    finally {
        if ($null -eq $previousRepoPath) {
            Remove-Item Env:REPRO_DEV_SHELL_ROOT -ErrorAction SilentlyContinue
        }
        else {
            $env:REPRO_DEV_SHELL_ROOT = $previousRepoPath
        }

        if ($null -eq $previousWslEnv) {
            Remove-Item Env:WSLENV -ErrorAction SilentlyContinue
        }
        else {
            $env:WSLENV = $previousWslEnv
        }
    }

    $linuxRepoRoot = if ($linuxPathOutput.Count -gt 0 -and $null -ne $linuxPathOutput[0]) {
        $linuxPathOutput[0].Trim()
    }
    else {
        ''
    }
    if (-not $linuxRepoRoot) {
        throw 'Could not translate the repository path for WSL.'
    }

    $linuxBootstrap = "$linuxRepoRoot/linux/bootstrap.sh"
    $linuxTheme = "$linuxRepoRoot/config/oh-my-posh.omp.json"
    $installWslAgentClis = if ($IncludeWslAgentClis) { '1' } else { '0' }
    $upgradeWslAgentClis = if ($Upgrade) { '1' } else { '0' }
    & wsl.exe --distribution $Distro -- bash $linuxBootstrap $linuxTheme $installWslAgentClis $upgradeWslAgentClis
    if ($LASTEXITCODE -ne 0) {
        throw "WSL bootstrap failed with exit code $LASTEXITCODE."
    }
}

Write-Host ''
Write-Host 'Bootstrap complete.' -ForegroundColor Green
Write-Host "PowerShell executable: $pwshPath"
Write-Host 'Restart Windows Terminal and choose PowerShell 7 - Repro under Settings > Startup > Default profile.'
