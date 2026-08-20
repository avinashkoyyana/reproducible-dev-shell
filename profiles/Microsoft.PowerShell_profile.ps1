# Managed source file. Re-run install.ps1 after changing it.

$configRoot = Join-Path $HOME '.config\repro-dev-shell'
$promptConfig = Join-Path $configRoot 'oh-my-posh.omp.json'

$env:FZF_DEFAULT_OPTS = '--height 45% --layout=reverse --border --info=inline'
$env:FZF_DEFAULT_COMMAND = 'fd --type f --hidden --exclude .git'

if (Get-Module -ListAvailable -Name PSReadLine) {
    Import-Module PSReadLine -ErrorAction SilentlyContinue
    Set-PSReadLineOption -EditMode Windows
    Set-PSReadLineOption -BellStyle None
    Set-PSReadLineOption -HistorySearchCursorMovesToEnd
    Set-PSReadLineKeyHandler -Key Tab -Function MenuComplete
    Set-PSReadLineKeyHandler -Key UpArrow -Function HistorySearchBackward
    Set-PSReadLineKeyHandler -Key DownArrow -Function HistorySearchForward

    if ((Get-Module PSReadLine).Version -ge [version]'2.2.0') {
        Set-PSReadLineOption -PredictionSource History
        Set-PSReadLineOption -PredictionViewStyle ListView
    }
}

foreach ($module in @('posh-git', 'Terminal-Icons', 'PSFzf')) {
    if (Get-Module -ListAvailable -Name $module) {
        Import-Module $module -ErrorAction SilentlyContinue
    }
}

if (Get-Command Set-PsFzfOption -ErrorAction SilentlyContinue) {
    Set-PsFzfOption -PSReadlineChordProvider 'Ctrl+f' -PSReadlineChordReverseHistory 'Ctrl+r'
}

if (Get-Command zoxide -ErrorAction SilentlyContinue) {
    zoxide init powershell | Out-String | Invoke-Expression
}

if (Get-Command carapace -ErrorAction SilentlyContinue) {
    $env:CARAPACE_BRIDGES = 'zsh,fish,bash,inshellisense'
    carapace _carapace | Out-String | Invoke-Expression
}

if ((Get-Command oh-my-posh -ErrorAction SilentlyContinue) -and (Test-Path -LiteralPath $promptConfig)) {
    oh-my-posh init pwsh --config $promptConfig | Invoke-Expression
}

function ll { Get-ChildItem -Force @args }
function which { Get-Command @args }
function mkcd {
    param([Parameter(Mandatory, Position = 0)][string] $Path)
    New-Item -ItemType Directory -Path $Path -Force | Out-Null
    Set-Location -LiteralPath $Path
}

if (Get-Command bat -ErrorAction SilentlyContinue) {
    Set-Alias -Name cat -Value bat -Option AllScope
}
