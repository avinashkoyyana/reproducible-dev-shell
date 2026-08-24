#Requires -Version 7.4
[CmdletBinding()]
param(
    [switch] $UpgradeModules,
    [switch] $SkipNerdFont
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot 'Bootstrap.Common.ps1')
$packages = Import-PowerShellDataFile (Join-Path $repoRoot 'config\packages.psd1')

if (-not (Get-Command Install-PSResource -ErrorAction SilentlyContinue)) {
    Write-Host 'Installing Microsoft.PowerShell.PSResourceGet...' -ForegroundColor Cyan
    Install-Module Microsoft.PowerShell.PSResourceGet -Scope CurrentUser -Force -AllowClobber
    Import-Module Microsoft.PowerShell.PSResourceGet
}

Initialize-PSGalleryRepository
foreach ($moduleName in $packages.PowerShellModules) {
    $installed = Get-InstalledPSResource -Name $moduleName -ErrorAction SilentlyContinue
    if (-not $installed) {
        Write-Host "Installing PowerShell module $moduleName..." -ForegroundColor Cyan
        Install-PSResource -Name $moduleName -Scope CurrentUser -TrustRepository -Quiet -ErrorAction Continue
    }
    elseif ($UpgradeModules) {
        Write-Host "Updating PowerShell module $moduleName..." -ForegroundColor Cyan
        Update-PSResource -Name $moduleName -ErrorAction Continue
    }
}

$configRoot = Join-Path $HOME '.config\repro-dev-shell'
$profileConfigRoot = Join-Path $configRoot 'powershell'
New-Item -ItemType Directory -Path $profileConfigRoot -Force | Out-Null

Copy-Item -LiteralPath (Join-Path $repoRoot 'config\oh-my-posh.omp.json') -Destination (Join-Path $configRoot 'oh-my-posh.omp.json') -Force
Copy-Item -LiteralPath (Join-Path $repoRoot 'profiles\Microsoft.PowerShell_profile.ps1') -Destination (Join-Path $profileConfigRoot 'profile.ps1') -Force

$loader = '. "$env:USERPROFILE\.config\repro-dev-shell\powershell\profile.ps1"'
Set-ManagedBlock -Path $PROFILE.CurrentUserAllHosts -Name 'reproducible-dev-shell' -Content $loader

$fragmentDirectory = Join-Path $env:LOCALAPPDATA 'Microsoft\Windows Terminal\Fragments\ReproDevShell'
New-Item -ItemType Directory -Path $fragmentDirectory -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $repoRoot 'config\windows-terminal.fragment.json') -Destination (Join-Path $fragmentDirectory 'profiles.json') -Force

if (-not $SkipNerdFont) {
    try {
        Import-Module NerdFonts -ErrorAction Stop
        Write-Host 'Ensuring FiraCode Nerd Font is installed...' -ForegroundColor Cyan
        Install-NerdFont -Name 'Fira Code' -Confirm:$false -ErrorAction Stop
    }
    catch {
        Write-Warning "Nerd Font installation did not complete: $($_.Exception.Message)"
    }
}

Write-Host "PowerShell profile configured at $($PROFILE.CurrentUserAllHosts)." -ForegroundColor Green
Write-Host 'Restart Windows Terminal, then select PowerShell 7 - Repro as the default profile.' -ForegroundColor Green
