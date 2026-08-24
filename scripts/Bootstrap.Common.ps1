Set-StrictMode -Version 2.0

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Set-ManagedBlock {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string] $Path,

        [Parameter(Mandatory)]
        [string] $Name,

        [Parameter(Mandatory)]
        [string] $Content
    )

    $begin = "# >>> $Name >>>"
    $end = "# <<< $Name <<<"
    $directory = Split-Path -Parent $Path
    if ($directory -and -not (Test-Path -LiteralPath $directory)) {
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }

    $existing = if (Test-Path -LiteralPath $Path) {
        [IO.File]::ReadAllText($Path)
    }
    else {
        ''
    }

    $pattern = '(?ms)^' + [regex]::Escape($begin) + '.*?^' + [regex]::Escape($end) + '\r?\n?'
    $withoutManagedBlock = [regex]::Replace($existing, $pattern, '').TrimEnd("`r", "`n")
    $managedBlock = "$begin`r`n$($Content.Trim())`r`n$end"

    if ($withoutManagedBlock) {
        $updated = "$withoutManagedBlock`r`n`r`n$managedBlock`r`n"
    }
    else {
        $updated = "$managedBlock`r`n"
    }

    [IO.File]::WriteAllText($Path, $updated, (New-Object Text.UTF8Encoding($false)))
}

function Initialize-PSGalleryRepository {
    [CmdletBinding()]
    param()

    try {
        $gallery = Get-PSResourceRepository -Name PSGallery -ErrorAction Stop
    }
    catch {
        Write-Verbose 'The PSResourceGet repository store is unavailable; recreating its default repositories.'
        if (Get-Command Reset-PSResourceRepository -ErrorAction SilentlyContinue) {
            Reset-PSResourceRepository -ErrorAction Stop
        }
        else {
            Register-PSResourceRepository -PSGallery -ErrorAction Stop
        }

        $gallery = Get-PSResourceRepository -Name PSGallery -ErrorAction Stop
    }

    if (-not $gallery.Trusted) {
        Set-PSResourceRepository -Name PSGallery -Trusted
    }
}

function Invoke-Winget {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string[]] $Arguments,

        [switch] $AllowNoUpgrade
    )

    & winget.exe @Arguments
    $exitCode = $LASTEXITCODE
    if ($exitCode -eq 0) {
        return
    }

    # WinGet uses this code when an upgrade was requested but none exists.
    if ($AllowNoUpgrade -and $exitCode -eq -1978335189) {
        return
    }

    throw "winget $($Arguments -join ' ') failed with exit code $exitCode."
}

function Install-WingetPackage {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [hashtable] $Package,

        [switch] $Upgrade
    )

    $arguments = @(
        'install', '--id', $Package.Id, '--exact', '--source', 'winget',
        '--accept-package-agreements', '--accept-source-agreements',
        '--disable-interactivity', '--silent'
    )

    if ($Package.InstallerType) {
        $arguments += @('--installer-type', $Package.InstallerType)
    }

    if ($Package.Id -eq 'Microsoft.PowerShell' -and -not (Test-Path "$env:ProgramFiles\PowerShell\7\pwsh.exe")) {
        $arguments += '--force'
    }

    Write-Host "Installing $($Package.Name)..." -ForegroundColor Cyan
    Invoke-Winget -Arguments $arguments -AllowNoUpgrade

    if ($Upgrade) {
        $upgradeArguments = @(
            'upgrade', '--id', $Package.Id, '--exact', '--source', 'winget',
            '--accept-package-agreements', '--accept-source-agreements',
            '--disable-interactivity', '--silent'
        )
        if ($Package.InstallerType) {
            $upgradeArguments += @('--installer-type', $Package.InstallerType)
        }
        Invoke-Winget -Arguments $upgradeArguments -AllowNoUpgrade
    }
}
