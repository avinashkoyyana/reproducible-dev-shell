"""Prepare a per-user Windows graph installation; no credentials or model calls.

The PowerShell entry point owns scheduling. This module owns verified artifacts
and conservative config merging. All live state stays outside the repository.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tomllib
import urllib.request
import uuid
import zipfile

SERVER = 'codebase-memory-mcp'
REPO = Path(__file__).resolve().parents[2]
BEGIN = '<!-- repro-graph:start -->'
END = '<!-- repro-graph:end -->'
GUIDANCE = '''For code discovery, first confirm the project and generation using
list_projects or index_status. Prefer search_graph, trace_path and
get_code_snippet. Check evidence paths with check_index_coverage; read source for
stale, partial, skipped or unknown coverage. Paginate relevant results. Graph
coverage is best effort, never proof of completeness. Use source searches for
config values and literals or when MCP is unavailable. Never assume a graph
from another project is the current project. Keep responses scoped and concise.
'''


def cursor_config(text, binary, cache, runtime):
    doc = json.loads(text or '{}')
    servers = doc.setdefault('mcpServers', {})
    entry = servers.setdefault(SERVER, {})
    if 'url' in entry:
        raise ValueError('Remote graph MCP entry exists; review it before replacing it.')
    entry.update(command=str(binary), args=[])
    entry.setdefault('env', {}).update(CBM_CACHE_DIR=str(cache), CBM_RUNTIME_DIR=str(runtime))
    return json.dumps(doc, indent=2) + '\n'


def codex_config(text, binary, cache, runtime):
    """Replace only conventional graph tables, refusing unusual/ambiguous TOML.

    Comparing the parsed result protects unrelated settings even when a table
    header appears inside a multiline string. No generic TOML reserialization.
    """
    before = tomllib.loads(text)
    old = before.get('mcp_servers', {}).get(SERVER, {})
    if any(k not in {'command', 'args', 'env', 'env_vars'} for k in old):
        raise ValueError('Graph MCP has custom access/settings; merge it manually.')
    environment = dict(old.get('env', {}))
    environment.update(CBM_CACHE_DIR=str(cache), CBM_RUNTIME_DIR=str(runtime))
    inherited = [key for key in old.get('env_vars', []) if key not in {'CBM_CACHE_DIR', 'CBM_RUNTIME_DIR'}]
    sections = re.split(r'(?m)^(?=\s*\[)', text)
    retained = []
    for section in sections:
        line = section.splitlines()[0].strip() if section.strip() else ''
        if re.fullmatch(r'\[mcp_servers\.codebase-memory-mcp(?:\.[A-Za-z0-9_-]+)*\]\s*(?:#.*)?', line):
            continue
        retained.append(section)
    block = ('\n[mcp_servers.codebase-memory-mcp]\n'
             f'command = {json.dumps(str(binary))}\nargs = []\n'
             + (f'env_vars = {json.dumps(inherited)}\n' if inherited else '')
             + '[mcp_servers.codebase-memory-mcp.env]\n'
             + ''.join(f'{json.dumps(key)} = {json.dumps(value)}\n' for key, value in environment.items()))
    result = ''.join(retained).rstrip() + '\n' + block
    after = tomllib.loads(result)
    old_other, new_other = deepcopy(before), deepcopy(after)
    old_other.setdefault('mcp_servers', {}).pop(SERVER, None)
    new_other.setdefault('mcp_servers', {}).pop(SERVER, None)
    if old_other != new_other:
        raise ValueError('Unsupported TOML layout; unrelated config would change.')
    # Explicit disable/tool restrictions are user choices, not installer defaults.
    return result


def managed_guidance(text):
    pattern = re.compile(re.escape(BEGIN) + r'.*?' + re.escape(END), re.S)
    if text.count(BEGIN) != text.count(END) or text.count(BEGIN) > 1:
        raise ValueError('Malformed graph instruction markers.')
    block = BEGIN + '\n' + GUIDANCE + END
    return (pattern.sub(block, text).rstrip() if BEGIN in text else text.rstrip() + '\n\n' + block).lstrip('\n') + '\n'


def write_backup(path, content):
    """Back up every changed file alongside it; leave identical files untouched."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = content if isinstance(content, bytes) else content.encode('utf-8')
    if path.exists() and path.read_bytes() == data:
        return
    if path.exists():
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
        shutil.copy2(path, path.with_name(path.name + f'.pre-repro-graph-{stamp}-{uuid.uuid4().hex[:8]}'))
    temporary = path.with_name(path.name + '.repro-pending')
    temporary.write_bytes(data)
    temporary.replace(path)


def extract_verified(archive, expected_hash, destination):
    if hashlib.sha256(archive.read_bytes()).hexdigest() != expected_hash:
        raise ValueError('Graph archive checksum mismatch; nothing extracted.')
    with zipfile.ZipFile(archive) as bundle:
        # Extract named files only; never honor archive-controlled paths.
        names = {Path(n).name: n for n in bundle.namelist()}
        if 'codebase-memory-mcp.exe' not in names:
            raise ValueError('Graph archive has no Windows executable.')
        for name in ('codebase-memory-mcp.exe', 'LICENSE', 'THIRD_PARTY_NOTICES.md'):
            if name in names:
                target = destination / name
                payload = bundle.read(names[name])
                if target.exists() and target.read_bytes() != payload:
                    raise ValueError('Versioned install differs; preserve it and review before replacing.')
                write_backup(target, payload)


def ps_literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def runner(base):
    # PowerShell 7 launches hidden by Task Scheduler; direct invocation retains
    # an accurate exit code and avoids detached child processes on normal runs.
    return ("$ErrorActionPreference = 'Stop'\n"
            f"& {ps_literal(sys.executable)} -u {ps_literal(base / 'graph_watch.py')} --once --base {ps_literal(base)}\n"
            'exit $LASTEXITCODE\n')


def prepare(home, base, binary, cache, runtime, codex_home):
    def existing(path):
        return path.read_text(encoding='utf-8-sig') if path.exists() else ''
    cursor = home / '.cursor/mcp.json'
    codex = codex_home / 'config.toml'
    instructions = codex_home / 'AGENTS.md'
    # Validate both complete files before writing either. Never print contents.
    changes = {
        cursor: cursor_config(existing(cursor), binary, cache, runtime),
        codex: codex_config(existing(codex), binary, cache, runtime),
        instructions: managed_guidance(existing(instructions)),
        base / 'settings.json': json.dumps({'binary': str(binary), 'cache': str(cache), 'runtime': str(runtime)}, indent=2) + '\n',
        base / 'graph_watch.py': (Path(__file__).parent / 'graph_watch.py').read_bytes(),
        base / 'run.ps1': runner(base),
    }
    skill = '---\nname: repro-graph\ndescription: Use for code discovery and graph freshness verification.\n---\n\n' + GUIDANCE
    changes[home / '.cursor/skills/repro-graph/SKILL.md'] = skill
    changes[codex_home / 'skills/repro-graph/SKILL.md'] = skill
    roots = base / 'roots.json'
    if roots.exists():
        config = json.loads(existing(roots))
        if not isinstance(config.get('roots'), list):
            raise ValueError('roots.json must contain a roots array.')
    else:
        changes[roots] = json.dumps({'roots': [str(home / 'Projects')], 'discover_clients': True, 'exclude': []}, indent=2) + '\n'
    return changes


def install(home, base, local_appdata, codex_home, archive=None):
    manifest = json.loads((REPO / 'config/graph-tools.json').read_text())
    artifact = manifest['windows-amd64']
    binary = local_appdata / f"Programs/repro-dev-shell/codebase-memory-mcp/{manifest['version']}/codebase-memory-mcp.exe"
    # Keep existing environment-selected cache/runtime; never copy their data.
    cache = Path(os.environ.get('CBM_CACHE_DIR', home / 'cbm-cache')).resolve()
    runtime = Path(os.environ.get('CBM_RUNTIME_DIR', home / 'cbm-runtime')).resolve()
    changes = prepare(home, base, binary, cache, runtime, codex_home)
    if archive is None:
        base.mkdir(parents=True, exist_ok=True)
        archive = base / f"cbm-{manifest['version']}-windows-amd64.zip"
        if not archive.exists():
            with urllib.request.urlopen(artifact['url'], timeout=120) as response:
                temporary = archive.with_suffix('.download')
                with temporary.open('wb') as output:
                    shutil.copyfileobj(response, output)
                temporary.replace(archive)
    extract_verified(archive, artifact['sha256'], binary.parent)
    cache.mkdir(parents=True, exist_ok=True)
    runtime.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(CBM_CACHE_DIR=str(cache), CBM_RUNTIME_DIR=str(runtime))
    for key, value in {'auto_index': 'true', 'auto_watch': 'true', 'watcher_enabled': 'true', 'ui_enabled': 'true', 'ui_port': '9749'}.items():
        result = subprocess.run([str(binary), 'config', 'set', key, value], env=env,
                                capture_output=True, timeout=30,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode:
            raise RuntimeError(f'Graph setting failed: {key}; client configs unchanged.')
    for path, content in changes.items():
        write_backup(path, content)
    print(json.dumps({'status': 'configured', 'version': manifest['version'], 'state_directory': str(base), 'client_restart_required': True}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive', type=Path, help='Offline official ZIP; checksum is still required.')
    args = parser.parse_args()
    if sys.platform != 'win32':
        parser.error('This installer targets Windows x64. WSL uses its own native runtime.')
    home = Path.home()
    try:
        install(home, home / '.local/share/repro-graph', Path(os.environ['LOCALAPPDATA']),
                Path(os.environ.get('CODEX_HOME', home / '.codex')), args.archive)
    except Exception as exc:
        # No config contents, tokens, URLs-with-credentials or child stderr.
        print(f'Graph setup failed ({type(exc).__name__}). Client files have adjacent backups if changed.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
