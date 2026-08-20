# Reproducible Developer Shell

An idempotent bootstrap for a consistent Windows development shell: PowerShell 7 (MSI), Windows Terminal, modern CLI tools, PowerShell modules, WSL 2, Ubuntu, Zsh, Oh My Zsh, and Oh My Posh.

## What it configures

| Layer | Installed and configured |
|---|---|
| Windows | PowerShell 7 MSI, Windows Terminal, Git, GitHub CLI, VS Code, Oh My Posh, fzf, ripgrep, fd, bat, zoxide, Carapace, delta, jq, yq, uv |
| PowerShell | PSReadLine completion and history, posh-git, PSFzf, Terminal-Icons, Pester, PSScriptAnalyzer, InvokeBuild, PlatyPS, shared prompt |
| WSL | WSL 2 with Ubuntu by default, native Linux CLI packages, uv, and Oh My Posh |
| Zsh | Oh My Zsh, autosuggestions, syntax highlighting, fzf-tab, direnv, zoxide, aliases, shared prompt |
| Terminal | A discoverable `PowerShell 7 - Repro` profile using FiraCode Nerd Font |

The package identities and configuration are declarative. Package versions intentionally float to the latest stable release available from WinGet, apt, and upstream installers; this avoids stale version locks while keeping the resulting shell configuration consistent.

## Quick start

Clone this repository, open **Windows PowerShell as Administrator**, and run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install.ps1
```

On a machine where PowerShell came from the Microsoft Store and `C:\Program Files\PowerShell\7\pwsh.exe` is missing, use:

```powershell
.\install.ps1 -RemoveStorePowerShell
```

This explicitly removes the current user's Store/MSIX package and installs the WinGet `wix`/MSI package. Windows PowerShell 5.1 remains installed side by side because Windows components can depend on it.

### First WSL installation

WSL can require a restart. The bootstrap exits after installing Ubuntu when this happens:

1. Restart Windows if requested.
2. Launch **Ubuntu** once and create the normal Linux username and password.
3. Run `.\install.ps1` again. It will continue with Zsh and the Linux tools.

## Useful options

```powershell
# Update installed WinGet packages and PowerShell modules
.\install.ps1 -Upgrade

# Configure Windows/PowerShell only
.\install.ps1 -SkipWSL

# Use another installed or online WSL distribution
.\install.ps1 -Distro Debian

# Skip package installation and only reapply configuration
.\install.ps1 -SkipWindowsPackages

# Avoid installing FiraCode Nerd Font
.\install.ps1 -SkipNerdFont
```

## After setup

Restart Windows Terminal. Open **Settings > Startup > Default profile** and select **PowerShell 7 - Repro**. Terminal fragments can safely add the profile, but Windows Terminal intentionally does not allow fragments to change a user's global default.

Verify the result:

```powershell
$PSVersionTable.PSVersion
$PSHOME
where.exe pwsh
wsl --list --verbose
```

The expected MSI path is `C:\Program Files\PowerShell\7\pwsh.exe`.

## Safe customization

- Edit [`config/packages.psd1`](config/packages.psd1) to change Windows packages or PowerShell modules.
- Edit [`profiles/Microsoft.PowerShell_profile.ps1`](profiles/Microsoft.PowerShell_profile.ps1) for PowerShell behavior.
- Edit [`linux/bootstrap.sh`](linux/bootstrap.sh) for WSL/Zsh behavior.
- Edit [`config/oh-my-posh.omp.json`](config/oh-my-posh.omp.json) for the shared prompt.
- Rerun `install.ps1` after every change.

The installer only owns marked blocks in existing PowerShell and Zsh profiles. Before it first changes `.zshrc`, it creates `~/.zshrc.pre-repro-dev-shell`. It does not unregister WSL distributions or delete project data.

## Validation

GitHub Actions parses all PowerShell, runs Pester and PSScriptAnalyzer, validates Bash with `bash -n` and ShellCheck, and checks the JSON files with `jq`.

Local validation from PowerShell 7:

```powershell
Install-PSResource Pester,PSScriptAnalyzer -Scope CurrentUser -TrustRepository
Invoke-Pester .\tests
Invoke-ScriptAnalyzer -Path . -Recurse -Severity Error
```

## Security model

Review the scripts before running them as Administrator. Windows software comes from the WinGet community source. Oh My Zsh plugins are cloned from their upstream GitHub repositories. The Linux installers for Oh My Posh and uv are downloaded over HTTPS to temporary files before execution.

## License

MIT
