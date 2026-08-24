# Reproducible Developer Shell

An idempotent bootstrap for a consistent Windows development workstation: PowerShell 7 (MSI), Windows Terminal, Docker Desktop, AI coding agents, modern CLI tools, PowerShell modules, WSL 2, Ubuntu, Zsh, Oh My Zsh, and Oh My Posh.

## What it configures

| Layer | Installed and configured |
|---|---|
| Windows | PowerShell 7 MSI, Windows Terminal, Docker Desktop, Git, GitHub CLI, VS Code, Oh My Posh, fzf, ripgrep, fd, bat, zoxide, Carapace, delta, jq, yq, uv |
| PowerShell | PSReadLine completion and history, posh-git, PSFzf, Terminal-Icons, Pester, PSScriptAnalyzer, InvokeBuild, PlatyPS, shared prompt |
| Coding agents | OpenAI Codex CLI, Claude Code, and Cursor CLI (`agent`) on Windows; optional native WSL copies |
| WSL | WSL 2 with Ubuntu by default, native Linux CLI packages, uv, and Oh My Posh |
| Zsh | Oh My Zsh, autosuggestions, syntax highlighting, fzf-tab, direnv, zoxide, aliases, shared prompt |
| Terminal | A discoverable `PowerShell 7 - Repro` profile using FiraCode Nerd Font |
| Optional cloud tools | AWS CLI, Azure CLI, Google Cloud CLI, kubectl, Helm, and Terraform |

The package identities and configuration are declarative. Package versions intentionally float to the latest stable release available from WinGet, apt, and upstream installers; this avoids stale version locks while keeping the resulting shell configuration consistent.

## Quick start

Do not clone into `C:\Windows\System32`. Open **PowerShell 7 as Administrator** and run:

```powershell
New-Item -ItemType Directory -Path "$HOME\Projects" -Force | Out-Null
Set-Location "$HOME\Projects"
git clone https://github.com/avinashkoyyana/reproducible-dev-shell.git
Set-Location .\reproducible-dev-shell

Set-ExecutionPolicy -Scope Process Bypass
.\install.ps1
```

If the repository is already at `C:\Users\<you>\Projects\reproducible-dev-shell`, update it instead of cloning it again:

```powershell
Set-Location "$HOME\Projects\reproducible-dev-shell"
git pull --ff-only
.\install.ps1
```

`install.ps1` always runs in an elevated **Windows PowerShell/PowerShell 7 window**, never inside Ubuntu. The script invokes the Linux bootstrap inside WSL for you.

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

# Keep the Windows agent CLIs out of this run
.\install.ps1 -SkipAgentClis

# Also install native Codex, Claude, and Cursor CLIs inside Ubuntu
.\install.ps1 -IncludeWslAgentClis

# Install the deferred cloud/Kubernetes/IaC group when ready
.\install.ps1 -IncludeCloudTools
```

The cloud switch installs `Amazon.AWSCLI`, `Microsoft.AzureCLI`, `Google.CloudSDK`, `Kubernetes.kubectl`, `Helm.Helm`, and `Hashicorp.Terraform`. It is off by default.

## Coding-agent CLIs

The normal bootstrap installs Windows-native copies. To install or repair only these three tools from a **non-elevated PowerShell 7** window:

```powershell
Set-Location "$HOME\Projects\reproducible-dev-shell"
pwsh -NoProfile -File .\scripts\Install-AgentClis.ps1
```

To update all three:

```powershell
pwsh -NoProfile -File .\scripts\Install-AgentClis.ps1 -Upgrade
```

Open a new PowerShell 7 window, verify, and complete the browser sign-ins:

```powershell
codex --version
claude --version
agent --version

codex
claude
agent
```

- Codex: choose **Sign in with ChatGPT** on first run.
- Claude Code: follow the browser login for your Claude subscription, Console account, or configured cloud provider.
- Cursor CLI: run `agent` and follow its login flow.

For Linux-native copies, run the main bootstrap with `-IncludeWslAgentClis`, then open **Ubuntu/Zsh** and use the same verification and login commands. Windows and WSL installations intentionally have separate binaries and may require separate first-time sign-ins.

Installation sources: [OpenAI Codex CLI](https://learn.chatgpt.com/docs/codex/cli), [Claude Code](https://code.claude.com/docs/en/quickstart), and [Cursor CLI](https://cursor.com/docs/cli/installation).

## Docker and WSL

Docker Desktop is declarative in the base package list. After its first launch:

1. Open **Docker Desktop > Settings > General** and enable **Use the WSL 2 based engine**.
2. Open **Resources > WSL Integration** and enable your Ubuntu distribution.
3. Apply the changes and restart Docker Desktop.

Verify from **PowerShell 7**:

```powershell
docker version
docker context show
wsl --list --verbose
```

Verify integration from **Ubuntu/Zsh**:

```bash
docker version
docker run --rm hello-world
```

Do not also install Docker Engine with `apt` inside that Ubuntu distribution when it is using Docker Desktop integration; that creates two competing Docker installations. See [Docker Desktop WSL integration](https://docs.docker.com/desktop/features/wsl/).

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

For active Linux projects, keep files in `~/projects` inside WSL and open them from Windows through `\\wsl$\Ubuntu\home\<linux-user>\projects`. For Windows projects, keep files in `$HOME\Projects`; WSL sees that directory as `/mnt/c/Users/<windows-user>/Projects`. Git, Node, Python, virtual environments, and dependency folders should normally stay on the same side as the project to avoid path and performance problems.

## Safe customization

- Edit [`config/packages.psd1`](config/packages.psd1) to change base, agent, cloud, or PowerShell-module package groups.
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

Review the scripts before running them as Administrator. Windows software comes from the WinGet community source. Oh My Zsh plugins are cloned from their upstream GitHub repositories. Vendor installers are downloaded over HTTPS to explicit temporary files, checked for an expected publisher host and non-HTML content, and logged with SHA-256 before execution; the bootstrap does not use `irm URL | iex` or `curl URL | sh` pipelines.

## License

MIT
