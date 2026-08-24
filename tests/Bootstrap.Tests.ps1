BeforeAll {
    $repoRoot = Split-Path -Parent $PSScriptRoot
    . (Join-Path $repoRoot 'scripts\Bootstrap.Common.ps1')
}

Describe 'PowerShell source' {
    It 'parses every PowerShell file without errors' {
        $errors = @()
        Get-ChildItem -Path $repoRoot -Filter '*.ps1' -Recurse | ForEach-Object {
            $tokens = $null
            $fileErrors = $null
            [void][System.Management.Automation.Language.Parser]::ParseFile($_.FullName, [ref]$tokens, [ref]$fileErrors)
            $errors += $fileErrors
        }
        $errors | Should -BeNullOrEmpty
    }
}

Describe 'Package manifest' {
    It 'contains unique WinGet package IDs' {
        $manifest = Import-PowerShellDataFile (Join-Path $repoRoot 'config\packages.psd1')
        $ids = @(
            $manifest.WindowsPackages.Id
            $manifest.AgentPackages.Id
            $manifest.CloudPackages.Id
        )
        @($ids | Sort-Object -Unique).Count | Should -Be $ids.Count
    }

    It 'keeps deferred cloud tools outside the base package group' {
        $manifest = Import-PowerShellDataFile (Join-Path $repoRoot 'config\packages.psd1')
        $manifest.WindowsPackages.Id | Should -Contain 'Docker.DockerDesktop'
        $manifest.AgentPackages.Id | Should -Contain 'Anthropic.ClaudeCode'
        $manifest.CloudPackages.Id | Should -Contain 'Hashicorp.Terraform'
        $manifest.WindowsPackages.Id | Should -Not -Contain 'Hashicorp.Terraform'
    }
}

Describe 'Set-ManagedBlock' {
    It 'is idempotent and preserves unmanaged content' {
        $path = Join-Path $TestDrive 'profile.ps1'
        Set-Content -LiteralPath $path -Value '# user content'

        Set-ManagedBlock -Path $path -Name 'test' -Content 'Write-Host first'
        Set-ManagedBlock -Path $path -Name 'test' -Content 'Write-Host second'

        $result = Get-Content -LiteralPath $path -Raw
        $result | Should -Match '# user content'
        $result | Should -Not -Match 'Write-Host first'
        ([regex]::Matches($result, '# >>> test >>>')).Count | Should -Be 1
        $result | Should -Match 'Write-Host second'
    }
}
