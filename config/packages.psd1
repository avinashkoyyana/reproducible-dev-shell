@{
    WindowsPackages  = @(
        @{ Id = 'Microsoft.PowerShell'; Name = 'PowerShell 7 (MSI)'; InstallerType = 'wix'; Required = $true }
        @{ Id = 'Microsoft.WindowsTerminal'; Name = 'Windows Terminal'; Required = $true }
        @{ Id = 'Git.Git'; Name = 'Git' }
        @{ Id = 'GitHub.cli'; Name = 'GitHub CLI' }
        @{ Id = 'Microsoft.VisualStudioCode'; Name = 'Visual Studio Code' }
        @{ Id = 'JanDeDobbeleer.OhMyPosh'; Name = 'Oh My Posh' }
        @{ Id = 'junegunn.fzf'; Name = 'fzf' }
        @{ Id = 'BurntSushi.ripgrep.MSVC'; Name = 'ripgrep' }
        @{ Id = 'sharkdp.fd'; Name = 'fd' }
        @{ Id = 'sharkdp.bat'; Name = 'bat' }
        @{ Id = 'ajeetdsouza.zoxide'; Name = 'zoxide' }
        @{ Id = 'rsteube.Carapace'; Name = 'Carapace' }
        @{ Id = 'dandavison.delta'; Name = 'delta' }
        @{ Id = 'jqlang.jq'; Name = 'jq' }
        @{ Id = 'MikeFarah.yq'; Name = 'yq' }
        @{ Id = 'astral-sh.uv'; Name = 'uv' }
    )

    PowerShellModules = @(
        'PSReadLine'
        'posh-git'
        'PSFzf'
        'Terminal-Icons'
        'PSScriptAnalyzer'
        'Pester'
        'InvokeBuild'
        'Microsoft.PowerShell.PlatyPS'
        'NerdFonts'
    )
}
