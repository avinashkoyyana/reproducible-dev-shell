"""Synthetic Git/non-Git freshness test and real MCP requests for both clients.

Uses existing machine-local settings. Creates only synthetic verification files;
does not invoke an agent/model or read any authentication file. Run after setup.
"""
import argparse
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import time
import tomllib

import graph_watch as watch


def cli(arguments):
    env = os.environ.copy()
    env.update(CBM_CACHE_DIR=str(watch.CACHE), CBM_RUNTIME_DIR=str(watch.RUNTIME))
    result = subprocess.run([str(watch.EXE), 'cli', '--json', *arguments], env=env,
                            capture_output=True, text=True, encoding='utf-8',
                            timeout=180, creationflags=watch.NO_WINDOW)
    if result.returncode:
        raise RuntimeError('graph_cli_failed')
    envelope = json.loads(result.stdout)
    if envelope.get('isError'):
        raise RuntimeError('graph_tool_failed')
    return envelope.get('structuredContent') or json.loads(envelope['content'][0]['text'])


def project_for(root):
    offset = 0
    while True:
        page = cli(['list_projects', '--format', 'json', '--limit', '100', '--offset', str(offset)])
        for project in page['projects']:
            if Path(project['root_path']).resolve() == root.resolve():
                return project['name']
        if not page.get('has_more'):
            raise RuntimeError('fixture_project_not_found')
        offset = page['next_offset']


def verify_client(config, root, project, symbol):
    env = os.environ.copy()
    env.update(config.get('env', {}))
    # Deliberately do not override cache/runtime from client configuration:
    # this test must expose wrong client mappings rather than conceal them.
    process = subprocess.Popen([config['command'], *config.get('args', [])], cwd=root,
                               env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, text=True, encoding='utf-8',
                               creationflags=watch.NO_WINDOW)
    messages = queue.Queue()

    def reader():
        for line in process.stdout:
            try:
                messages.put(json.loads(line))
            except ValueError:
                pass
        messages.put({'transport_closed': True})

    threading.Thread(target=reader, daemon=True).start()

    def send(data):
        process.stdin.write(json.dumps(data) + '\n')
        process.stdin.flush()

    def request(identifier, method, params):
        send({'jsonrpc': '2.0', 'id': identifier, 'method': method, 'params': params})
        deadline = time.monotonic() + 180
        while True:
            message = messages.get(timeout=max(0.01, deadline - time.monotonic()))
            if message.get('transport_closed') or time.monotonic() > deadline:
                raise RuntimeError('mcp_transport_failed')
            if message.get('method') == 'roots/list':
                send({'jsonrpc': '2.0', 'id': message['id'], 'result': {'roots': [{'uri': root.as_uri(), 'name': 'Synthetic verification'}]}})
            elif message.get('id') == identifier:
                if 'error' in message:
                    raise RuntimeError('mcp_response_error')
                return message['result']

    try:
        request(1, 'initialize', {'protocolVersion': '2024-11-05', 'capabilities': {'roots': {'listChanged': False}}, 'clientInfo': {'name': 'repro-graph-verifier', 'version': '1'}})
        send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        found = request(2, 'tools/call', {'name': 'search_graph', 'arguments': {'project': project, 'name_pattern': symbol, 'limit': 5}})
        if found.get('isError') or symbol not in json.dumps(found):
            raise RuntimeError('latest_symbol_not_found')
        return True
    finally:
        process.stdin.close()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=10)
        process.stdout.close()


def run(base, client_home, codex_home):
    watch.BASE = base
    settings = json.loads((base / 'settings.json').read_text())
    watch.EXE, watch.CACHE, watch.RUNTIME = (Path(settings[key]) for key in ('binary', 'cache', 'runtime'))
    clients = {
        'Codex': tomllib.loads((codex_home / 'config.toml').read_text(encoding='utf-8-sig'))['mcp_servers']['codebase-memory-mcp'],
        'Cursor': json.loads((client_home / '.cursor/mcp.json').read_text(encoding='utf-8-sig'))['mcpServers']['codebase-memory-mcp'],
    }
    # Unique directory avoids touching older test runs or user content.
    import uuid
    fixture = base / 'verification' / uuid.uuid4().hex[:12]
    roots = [fixture / 'git', fixture / 'plain']
    for root in roots:
        root.mkdir(parents=True)
    subprocess.run(['git', 'init', str(roots[0])], check=True, capture_output=True)
    checks = []
    for revision in (1, 2):
        for root in roots:
            (root / 'probe.py').write_text(f'def repro_graph_{root.name}_v{revision}():\n    return {revision}\n')
        records = watch.sweep(roots, force=(revision == 1))
        if any(row['status'] != 'indexed' for row in records):
            raise RuntimeError('freshness_sweep_failed')
        for root in roots:
            project = project_for(root)
            symbol = f'repro_graph_{root.name}_v{revision}'
            for client, config in clients.items():
                verify_client(config, root, project, symbol)
                checks.append({'client': client, 'fixture': root.name, 'revision': revision, 'retrieved': True})
                print(json.dumps(checks[-1]), flush=True)
    watch.write_json(base / 'client-verification.json', {'checks': checks, 'finished_at': time.time(), 'scope': 'Synthetic sweep and configured MCP transport; UI tool approval and timer require separate checks.'})
    print(json.dumps({'status': 'passed', 'checks': len(checks)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', type=Path, default=Path.home() / '.local/share/repro-graph')
    parser.add_argument('--client-home', type=Path, default=Path.home())
    parser.add_argument('--codex-home', type=Path, default=Path(os.environ.get('CODEX_HOME', Path.home() / '.codex')))
    args = parser.parse_args()
    try:
        run(args.base.resolve(), args.client_home.resolve(), args.codex_home.resolve())
    except Exception as exc:
        print(json.dumps({'status': 'failed', 'error_type': type(exc).__name__}))
        raise SystemExit(1)
