#Requires -Version 7.4
[CmdletBinding()]
param(
    [switch] $Upgrade
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot 'Bootstrap.Common.ps1')
$packages = Import-PowerShellDataFile (Join-Path $repoRoot 'config\packages.psd1')

function Update-ProcessPath {
    [CmdletBinding()]
    param()

    $machinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = @($machinePath, $userPath) |
        Where-Object { $_ } |
        Join-String -Separator ([IO.Path]::PathSeparator)
}

function Invoke-PublisherPowerShellInstaller {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string] $Name,

        [Parameter(Mandatory)]
        [uri] $Uri,

        [Parameter(Mandatory)]
        [string] $ExpectedHost
    )

    if ($Uri.Scheme -ne 'https' -or $Uri.Host -ne $ExpectedHost) {
        throw "Refusing the unexpected $Name installer URL: $Uri"
    }

    $temporaryPath = Join-Path ([IO.Path]::GetTempPath()) "repro-dev-shell-$([guid]::NewGuid().ToString('N')).ps1"
    try {
        Write-Host "Downloading the official $Name installer..." -ForegroundColor Cyan
        Invoke-WebRequest -Uri $Uri -OutFile $temporaryPath -UseBasicParsing

        $installer = Get-Item -LiteralPath $temporaryPath
        if ($installer.Length -lt 100) {
            throw "The downloaded $Name installer is unexpectedly small."
        }

        $installerText = Get-Content -LiteralPath $temporaryPath -Raw
        if ($installerText -match '^\s*<(?:!doctype|html)') {
            throw "The $Name download returned HTML instead of a PowerShell installer."
        }

        $hash = (Get-FileHash -LiteralPath $temporaryPath -Algorithm SHA256).Hash
        Write-Host "$Name installer SHA256: $hash"

        & (Join-Path $PSHOME 'pwsh.exe') -NoLogo -NoProfile -ExecutionPolicy Bypass -File $temporaryPath
        if ($LASTEXITCODE -ne 0) {
            throw "$Name installer failed with exit code $LASTEXITCODE."
        }
    }
    finally {
        Remove-Item -LiteralPath $temporaryPath -Force -ErrorAction SilentlyContinue
    }
}

if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) {
    throw 'WinGet is required to install Claude Code.'
}

foreach ($package in $packages.AgentPackages) {
    Install-WingetPackage -Package $package -Upgrade:$Upgrade
}

$codex = Get-Command codex -ErrorAction SilentlyContinue
if (-not $codex -or $Upgrade) {
    Invoke-PublisherPowerShellInstaller `
        -Name 'OpenAI Codex CLI' `
        -Uri 'https://chatgpt.com/codex/install.ps1' `
        -ExpectedHost 'chatgpt.com'
}

$cursorAgent = Get-Command agent -ErrorAction SilentlyContinue
if (-not $cursorAgent) {
    Invoke-PublisherPowerShellInstaller `
        -Name 'Cursor CLI' `
        -Uri 'https://cursor.com/install?win32=true' `
        -ExpectedHost 'cursor.com'
}
elseif ($Upgrade) {
    & $cursorAgent.Source update
    if ($LASTEXITCODE -ne 0) {
        throw "Cursor CLI update failed with exit code $LASTEXITCODE."
    }
}

Update-ProcessPath

$verificationCommands = @(
    @{ Name = 'Codex CLI'; Command = 'codex'; Arguments = @('--version') }
    @{ Name = 'Claude Code'; Command = 'claude'; Arguments = @('--version') }
    @{ Name = 'Cursor CLI'; Command = 'agent'; Arguments = @('--version') }
)

foreach ($verification in $verificationCommands) {
    $command = Get-Command $verification.Command -ErrorAction SilentlyContinue
    if (-not $command) {
        throw "$($verification.Name) was installed, but '$($verification.Command)' is not available on PATH. Open a new PowerShell 7 window and verify it manually."
    }

    $version = & $command.Source @($verification.Arguments)
    if ($LASTEXITCODE -ne 0) {
        throw "$($verification.Name) verification failed with exit code $LASTEXITCODE."
    }
    Write-Host "$($verification.Name): $($version -join ' ')" -ForegroundColor Green
}
