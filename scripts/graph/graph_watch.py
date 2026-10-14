"""Local-only graph freshness sweep for saved Codex and Cursor workspaces.

No model calls. Task Scheduler invokes --once every five minutes. This covers
closed sessions and non-Git roots unsupported by released CBM 0.11.0.
Configuration and indexes belong to this machine, never to the bootstrap repo.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.parse import unquote, urlparse

HOME = Path.home()
BASE = Path(os.environ.get('REPRO_GRAPH_HOME', HOME / '.local/share/repro-graph'))
EXE = None  # Loaded from the machine-local settings.json by main().
CACHE = HOME / 'cbm-cache'
RUNTIME = HOME / 'cbm-runtime'
SKIP = {'.git', '.hg', '.svn', 'node_modules', '.venv', 'venv', '.ats-build-venv',
        '__pycache__', '.pytest_cache', '.next', 'dist', 'build', 'vendor',
        '.codebase-memory', '.gitnexus', 'graphify-out', 'state', 'tmp', 'logs',
        '.ssh', '.aws', '.azure', '.secrets', 'repro-graph'}
EXT = {'.py', '.js', '.jsx', '.ts', '.tsx', '.go', '.rs', '.java', '.cs', '.c',
       '.h', '.cpp', '.hpp', '.rb', '.php', '.swift', '.kt', '.scala', '.sh',
       '.ps1', '.sql', '.md', '.mdx', '.json', '.toml', '.yaml', '.yml', '.html',
       '.css', '.scss', '.vue', '.svelte', '.xml', '.txt', '.dart', '.ipynb'}
HIDDEN_OK = {'.gitignore', '.cbmignore', '.codebase-memory.json'}
NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def read_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return default


def write_json(path, data):
    temp = path.with_suffix('.pending')
    temp.write_text(json.dumps(data, indent=2), encoding='utf-8')
    temp.replace(path)


def allowed(path):
    return (not any(p.lower() in SKIP for p in path.parts)
            and not any(p.startswith('.') and p not in HIDDEN_OK for p in path.parts)
            and path.name.lower() not in {'auth.json', 'credentials.json', 'secrets.json'}
            and (path.suffix.lower() in EXT or path.name in HIDDEN_OK
                 or path.name.lower() in {'dockerfile', 'makefile'}))


def fingerprint(root):
    """Metadata-only change detection; git ignore rules when available."""
    paths = None
    if (root / '.git').exists():
        result = subprocess.run(['git', '-C', str(root), 'ls-files', '-co',
                                 '--exclude-standard', '-z'], capture_output=True,
                                timeout=45, creationflags=NO_WINDOW)
        if result.returncode == 0:
            paths = {Path(x) for x in result.stdout.decode('utf-8', 'surrogateescape').split('\0') if x}
    if paths is None:
        # Read metadata without running Git in repositories it refuses to trust.
        # Never add safe.directory or change repository ownership/permissions.
        paths = set()
        for base, dirs, files in os.walk(root, followlinks=False):
            dirs[:] = [d for d in dirs if d.lower() not in SKIP and not d.startswith('.')
                       and not (Path(base) / d).is_symlink()]
            paths.update((Path(base) / f).relative_to(root) for f in files)
            if len(paths) > 50000:
                raise RuntimeError('file_limit')
    if len(paths) > 50000:
        raise RuntimeError('file_limit')
    rows = []
    for p in sorted(paths):
        if not allowed(p):
            continue
        file = root / p
        if file.is_symlink() or not file.is_file():
            continue
        stat = file.stat()
        rows.append((p.as_posix(), stat.st_size, stat.st_mtime_ns))
    return hashlib.sha256(json.dumps(rows).encode()).hexdigest(), len(rows)


def discovered_roots():
    config_path = BASE / 'roots.json'
    # A malformed user scope must fail, not silently enable default discovery.
    config = json.loads(config_path.read_text(encoding='utf-8-sig')) if config_path.exists() else {}
    for key in ('roots', 'exclude'):
        if not isinstance(config.get(key, []), list) or not all(isinstance(p, str) for p in config.get(key, [])):
            raise ValueError('invalid_root_configuration')
    if not isinstance(config.get('discover_clients', True), bool):
        raise ValueError('invalid_discovery_configuration')
    roots = list(config.get('roots', []))
    state = read_json(Path(os.environ.get('CODEX_HOME', HOME / '.codex')) / '.codex-global-state.json', {}) if config.get('discover_clients', True) else {}
    roots.extend(state.get('electron-saved-workspace-roots', []))
    for project in state.get('local-projects', {}).values():
        roots.extend(project.get('rootPaths', []))
    roots.extend(p for p in state.get('thread-projectless-output-directories', {}).values()
                 if isinstance(p, str) and Path(p).is_absolute())
    storage = Path(os.environ.get('APPDATA', HOME / 'AppData/Roaming')) / 'Cursor/User/workspaceStorage'
    for metadata in storage.glob('*/workspace.json') if config.get('discover_clients', True) else []:
        info = read_json(metadata, {})
        folder = info.get('folder', '')
        if folder.startswith('file:///'):
            roots.append(unquote(urlparse(folder).path).lstrip('/'))
        workspace = info.get('workspace', '')
        if workspace.startswith('file:///'):
            ws = Path(unquote(urlparse(workspace).path).lstrip('/'))
            for item in read_json(ws, {}).get('folders', []):
                if 'path' in item:
                    roots.append(str((ws.parent / item['path']).resolve()))
    result = {}
    # Broad container roots are expanded only to immediate child Git repos.
    containers = {HOME, HOME / 'Projects', HOME / 'Downloads', HOME / 'Documents'}
    for raw in roots:
        if not isinstance(raw, str) or not raw.strip():
            continue
        p = Path(os.path.expandvars(raw)).expanduser().resolve()
        excluded = [Path(os.path.expandvars(x)).expanduser().resolve() for x in config.get('exclude', [])]
        if any(p == x or p.is_relative_to(x) for x in excluded):
            continue
        if p in containers:
            if p.is_dir():
                for child in p.iterdir():
                    if child.is_dir() and not child.is_symlink() and (child / '.git').exists() and not any(child == x or child.is_relative_to(x) for x in excluded):
                        result[str(child).lower()] = child
            continue
        if p == Path(p.anchor) or p == BASE or BASE.is_relative_to(p):
            continue
        if 'appdata' in (x.lower() for x in p.parts) or any(x.lower() in {'.codex', '.cursor', '.ssh', '.aws', '.azure'} for x in p.parts):
            continue
        result[str(p).lower()] = p
    ordered = sorted(result.values(), key=lambda p: (len(p.parts), str(p).lower()))
    selected = []
    for p in ordered:
        if not (p / '.git').exists() and any(p.is_relative_to(parent) for parent in selected):
            continue
        selected.append(p)
    return sorted(selected, key=lambda p: str(p).lower())


def index(root):
    env = os.environ.copy()
    env.update(CBM_CACHE_DIR=str(CACHE), CBM_RUNTIME_DIR=str(RUNTIME), CBM_WORKERS='2')
    result = subprocess.run([str(EXE), 'cli', '--json', 'index_repository',
                             '--repo-path', str(root), '--mode', 'full'],
                            env=env, capture_output=True, text=True,
                            encoding='utf-8', errors='replace', timeout=900,
                            creationflags=NO_WINDOW)
    if result.returncode:
        raise RuntimeError('index_process_failed')
    payload = json.loads(result.stdout)
    if payload.get('isError'):
        raise RuntimeError('index_tool_failed')
    return True


def sweep(roots=None, force=False):
    BASE.mkdir(parents=True, exist_ok=True)
    prior = read_json(BASE / 'state.json', {})
    records = []
    write_json(BASE / 'active.json', {'phase':'discovering', 'pid':os.getpid(), 'time':time.time()})
    inventory = discovered_roots() if roots is None else roots
    write_json(BASE / 'inventory.json', {'roots':[str(p) for p in inventory], 'time':time.time()})
    def process_root(root):
        key = str(root)
        row = {'root': key, 'checked_at': time.time()}
        try:
            if not root.is_dir():
                row['status'] = 'missing'
            else:
                digest, count = fingerprint(root)
                row['files'] = count
                if count == 0 and not prior.get(key, {}).get('fingerprint'):
                    row['status'] = 'empty_or_no_supported_files'
                elif force or prior.get(key, {}).get('fingerprint') != digest:
                    index(root)
                    row.update(status='indexed', fingerprint=digest, indexed_at=time.time())
                else:
                    row.update(status='unchanged', fingerprint=digest,
                               indexed_at=prior[key].get('indexed_at'))
        except Exception as exc:
            # Never persist raw stderr or source text.
            row.update(status='error', error_type=type(exc).__name__)
            if str(exc) in {'file_limit','index_process_failed','index_tool_failed'}:
                row['error_code'] = str(exc)
        if row['status'] == 'error' and key in prior:
            row['last_success'] = prior[key].get('indexed_at')
        return row
    # Two bounded workers avoid one slow repository blocking all other projects.
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(process_root, root) for root in inventory]
        write_json(BASE / 'active.json', {'phase':'processing','total':len(inventory),
                                        'completed':0,'pid':os.getpid(),'time':time.time()})
        for future in as_completed(futures):
            row = future.result()
            prior[row['root']] = row
            records.append(row)
            write_json(BASE / 'state.json', prior)
            write_json(BASE / 'active.json', {'phase':'processing','total':len(inventory),
                                            'completed':len(records),'root':row['root'],
                                            'pid':os.getpid(),'time':time.time()})
            if sys.stdout:
                print(json.dumps({k: v for k, v in row.items() if k != 'fingerprint'}), flush=True)
    write_json(BASE / 'last-run.json', {'finished_at': time.time(), 'projects': records})
    write_json(BASE / 'active.json', {'phase':'complete','pid':os.getpid(),'time':time.time()})
    return records


def main():
    global BASE, EXE, CACHE, RUNTIME
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', type=Path, default=BASE)
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--root', action='append')
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()
    BASE = args.base.resolve()
    settings = read_json(BASE / 'settings.json', {})
    EXE = Path(settings['binary'])
    CACHE, RUNTIME = Path(settings['cache']), Path(settings['runtime'])
    BASE.mkdir(parents=True, exist_ok=True)
    # OS-held lock is released on process death, preventing overlapping sweeps.
    import msvcrt
    with (BASE / 'sweep.lock').open('a+b') as lock:
        if os.fstat(lock.fileno()).st_size == 0:
            lock.write(b'0'); lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            raise SystemExit(0)
        env = os.environ.copy()
        env.update(CBM_CACHE_DIR=str(CACHE), CBM_RUNTIME_DIR=str(RUNTIME))
        # Never print raw daemon output, which can contain machine-local paths.
        daemon = subprocess.run([str(EXE), 'daemon', 'start'], env=env,
                                capture_output=True, timeout=45, creationflags=NO_WINDOW)
        if daemon.returncode:
            print('{"status":"error","error_code":"daemon_start_failed"}')
            raise SystemExit(1)
        rows = sweep([Path(p).resolve() for p in args.root] if args.root else None, args.force)
        raise SystemExit(1 if any(r['status'] == 'error' for r in rows) else 0)


if __name__ == '__main__':
    main()
