# Portable local graph setup

This optional package reproduces the Codebase Memory configuration used on the
ATS workstation. The existing base bootstrap handles Windows/WSL, the shell and
coding CLIs. This package adds Codebase Memory 0.11.0, Codex and Cursor MCP entries,
graph-use instructions, and automatic local index refresh.

It does not copy credentials, graph databases, chat history, account subscriptions,
Paperclip/Buzz state, Ollama models, RAG documents or private project inventories.
It does not configure Graphify or Understand Anything. Those tools and the ATS
services need their own separately reviewed manifests. Sign in to coding clients
separately on each machine; the graph installation makes no model/API calls.

## New Windows 11 PC

1. Clone this repository's current `main` branch to the new PC, or update an
   existing checkout. The graph package is included in the repository. Run the
   base `install.ps1` as described in the main README.
2. Open a **non-elevated PowerShell 7** window as the user who will use Codex/Cursor.
3. Review and run:

   ```powershell
   Set-Location "$HOME\Projects\reproducible-dev-shell"
   .\scripts\Install-GraphTools.ps1 -WhatIf
   .\scripts\Install-GraphTools.ps1
   ```

   Requires Windows x64, PowerShell 7.4+, Git, and Python 3.11+. If Python is not
   supplied with `-PythonPath`, the script uses `uv` from the base installation to
   install/find Python 3.11. No Python packages are needed.
4. Restart Codex/Cursor. Review their graph MCP entry and complete any client tool
   approval yourself. The installer does not change approval policies or hooks.
5. Open your cloned project folders in the clients and verify the results below.

Only this optional graph binary is version-pinned; the base shell's package
versions still float. The Windows x64 ZIP URL and SHA-256 are in
[`config/graph-tools.json`](../config/graph-tools.json). A mismatch fails closed.
To use an offline copy of the official ZIP:

```powershell
.\scripts\Install-GraphTools.ps1 -ArchivePath 'D:\Installers\codebase-memory-mcp-windows-amd64.zip'
```

The verified binary and upstream notices are installed in a versioned per-user
directory under `%LOCALAPPDATA%\Programs\repro-dev-shell\codebase-memory-mcp`.
Existing installations are not uninstalled or overwritten.

## What persists on each machine

| Location | Purpose |
|---|---|
| `~/.local/share/repro-graph/settings.json` | Actual binary, cache and runtime paths |
| `~/.local/share/repro-graph/roots.json` | This machine's project roots and discovery preferences |
| `~/.local/share/repro-graph/state.json` | Last successful source fingerprints |
| `~/.local/share/repro-graph/last-run.json` | Last completed sweep and per-root status |
| `~/.local/share/repro-graph/active.json` | Current sweep progress |
| `~/.cursor/mcp.json` | Graph server entry; other servers preserved |
| `$CODEX_HOME/config.toml` (default `~/.codex`) | Graph server entry; unrelated configuration preserved |
| `$CODEX_HOME/AGENTS.md` | Marked graph-first instructions; other text preserved |
| Codex and Cursor `skills/repro-graph/SKILL.md` | Guidance for project selection, coverage checks and source fallback |
| `~/cbm-cache`, `~/cbm-runtime` | Local graph storage/runtime (existing `CBM_*` environment paths take precedence) |

Changed files receive adjacent `.pre-repro-graph-<timestamp>-<id>` backups. These
can contain your existing settings: keep them private. Unusual TOML layouts or
custom graph access controls are refused rather than silently rewritten. Review
and merge the graph entry manually if this occurs. Global Cursor JSON must be
valid JSON; comments/trailing commas are not rewritten automatically.

The installer merges configs, but **configuration is not proof of a working
integration**. The verification script tests actual stdio requests; an agent's
tool approval and choice to use the tool remain separate client behavior.

## Automatic refresh and scope

Native CBM auto-indexing and Git watchers are enabled. The limited, interactive
Windows task **ReproDevShell Graph Freshness** supplements them every five minutes
and at sign-in. It does not wake a sleeping PC or run while signed out. Startup
after a missed run is enabled. Two indexing workers are used, each with a 15-minute
timeout; the task has a one-hour limit. A local OS lock prevents overlapping sweeps.

The sweep discovers local roots from Codex's saved workspace metadata and Cursor's
workspace storage, including ordinary multi-folder workspace files. These local
metadata formats may change. Remote SSH/WSL workspace URIs, cloud-only ChatGPT
projects and repositories that have not been cloned locally are not discovered.
Opening a new client workspace makes it eligible for the next sweep. Moving a
folder may leave its old entry marked `missing`; inspect the inventory.

For other locations, edit the machine-local `roots.json`, for example:

```json
{
  "roots": ["~/Projects", "D:/Work/Recruitment", "D:/Work/Engineering"],
  "discover_clients": true,
  "exclude": ["D:/Work/PrivateClient"]
}
```

`~/Projects`, the home directory, Downloads and Documents are treated as broad
containers: only immediate Git children are expanded. Add specific non-Git
folders explicitly. Home/drive scans and credential/client-state directories are
rejected. The `exclude` array filters candidate roots; it is **not** a per-file
security boundary inside a selected parent. Use repository `.gitignore` and
Codebase Memory `.cbmignore` rules for source exclusions. The freshness scanner
skips common dependency folders and credential filenames, but it is not a secret
detector and does not replace the indexer's own exclusion rules.

The sweep compares supported source filenames, sizes and modification timestamps;
repeated edits to already-dirty files and deletions trigger reindexing. Failed
indexes are retried, never recorded as fresh. Timestamp-preserving external edits
may need a forced sweep. Unsupported source formats and native parser gaps remain
possible; agents must check coverage and use source fallback. In CBM 0.11.0 we
observed occasional false `metadata_changed` reports even when stored hashes and
timestamps matched: investigate such reports rather than dismissing them.

## Verify on each PC

```powershell
$graphState = Join-Path $HOME '.local\share\repro-graph'
Get-ScheduledTask -TaskName 'ReproDevShell Graph Freshness'
Get-ScheduledTaskInfo -TaskName 'ReproDevShell Graph Freshness'
Get-Content (Join-Path $graphState 'last-run.json')
$graphPython = (& uv python find 3.11).Trim()
& $graphPython .\scripts\graph\verify_graph.py
```

If you used `-PythonPath`, use that executable for verification too. A zero task
exit code and recent `last-run.json` with no `error` statuses establish a completed
sweep. `missing`/empty roots are reported separately and are not indexed. The
verifier creates unique synthetic Git and non-Git folders, makes two revisions,
runs the real refresh function and retrieves each revision through **both clients'
actual configured MCP commands** (eight checks). It leaves synthetic evidence and
`client-verification.json` locally. No model or repository push is involved.

To verify the timer itself, create `graph_probe.py` in a disposable saved workspace
with `def graph_probe_v1(): return 1`. Wait for the next task completion, then
change it to `def graph_probe_v2(): return 2`, wait again, and ask the client to
retrieve that exact function from that project's graph. This separately tests
discovery, scheduled execution and client tool usage. The synthetic verifier does
not claim to test the wall-clock schedule or the GUI's approval state.

The graph viewer is configured at **http://127.0.0.1:9749**. It becomes available
when the daemon starts. A port conflict or blocked daemon must be resolved before
claiming the viewer works. The installer does not expose it to the LAN.

For a manual forced refresh:

```powershell
& $graphPython (Join-Path $graphState 'graph_watch.py') --once --force
```

Client-local MCP serves Codex and Cursor. It does not automatically grant the
ordinary ChatGPT website access to local files or chat/project uploads. Graphs
reduce code-discovery context; they do not synchronize ChatGPT memory. Shared RAG
requires a separate ingestion/retrieval service and access design.

## Existing ATS workstation / rollback

Do not run a second sweep task alongside **ATS Local Graph Freshness**. The
installer refuses that combination. The current working ATS setup can stay as-is
while this repository is copied to new PCs. No migration is needed to use it on a
new machine.

If you later choose to migrate this machine, first save the old task XML and note
its runtime directory. Disable the old task explicitly (do not delete its state),
run the new installer, complete verification and compare root inventories. The new
installation discovers current workspaces but does not automatically import the
old manual root list. Add any missing roots locally. Restore the adjacent client
backups and re-enable the old task if verification fails.

To pause the new task without deleting indexes:

```powershell
Disable-ScheduledTask -TaskName 'ReproDevShell Graph Freshness'
```

Restore only the affected graph entries/managed instruction block from backups;
do not replace an entire config if you made other changes since that backup.
No uninstall script removes user data or indexes. `-SkipSchedule` prepares the
new client configuration without registering a timer; it is not a read-only
preview. Use `-WhatIf` for preview.

## WSL and Linux boundaries

The graph installer currently targets **Windows x64**. The existing base shell
still supports WSL Ubuntu. Windows Codex/Cursor can index their local Windows
checkouts. Native WSL clients and repositories inside the Linux filesystem need
a separate Linux CBM binary, Linux paths and a user-level watcher/timer; this
package does not install or claim to verify those. Do not point a native Linux
MCP configuration at the Windows executable or copy a Windows graph database
into WSL. ARM64/macOS installers are also outside this tested package.

## Development checks

```powershell
& $graphPython -m unittest discover -s tests -p 'test_*.py' -v
Invoke-Pester .\tests -CI
Invoke-ScriptAnalyzer -Path . -Recurse -Severity Error
```

CI runs the offline Python regressions on Windows and Linux, alongside the
existing PowerShell/Bash checks. A clean-machine install, GUI client approvals
and the timer probe still require verification on each destination PC.

Local validation on 2026-10-14: 20 Python regressions passed on Windows and WSL
Ubuntu; six existing Pester tests passed; PSScriptAnalyzer reported no errors.
An isolated Windows test profile installed the checksum-verified official ZIP,
passed all eight native MCP retrieval checks and ran the generated refresh
launcher successfully. The isolated test daemon was stopped afterward. The
existing ATS task and live client configurations were preserved; a new recurring
task was not registered on that workstation during packaging.

Upstream references: [CBM 0.11.0 release](https://github.com/DeusData/codebase-memory-mcp/releases/tag/v0.11.0),
[Cursor MCP configuration](https://cursor.com/docs/mcp).
