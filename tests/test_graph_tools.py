"""Offline regression tests: python -m unittest discover -s tests -p 'test_*.py'."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/graph'))
import graph_watch as watch
import setup_graph as setup


class GraphTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_cursor_preserves_other_servers_and_options(self):
        original = {'mcpServers': {'other': {'command': 'other', 'env': {'TOKEN': 'synthetic'}}}, 'extra': True}
        updated = json.loads(setup.cursor_config(json.dumps(original), 'exe', 'cache', 'runtime'))
        self.assertEqual(updated['mcpServers']['other'], original['mcpServers']['other'])
        self.assertTrue(updated['extra'])
        self.assertEqual(setup.cursor_config(json.dumps(updated), 'exe', 'cache', 'runtime'), json.dumps(updated, indent=2) + '\n')

    def test_codex_preserves_comments_and_other_tables(self):
        original = '# my setting\nmodel = "example"\n[mcp_servers.other]\ncommand = "keep"\n[mcp_servers.codebase-memory-mcp]\ncommand = "old"\n[mcp_servers.codebase-memory-mcp.env]\nCBM_CACHE_DIR = "old"\n[profiles.demo]\nmodel = "other"\n'
        updated = setup.codex_config(original, 'new', 'cache', 'runtime')
        parsed = tomllib.loads(updated)
        self.assertEqual(parsed['profiles']['demo']['model'], 'other')
        self.assertEqual(parsed['mcp_servers']['other']['command'], 'keep')
        self.assertIn('# my setting', updated)
        self.assertEqual(setup.codex_config(updated, 'new', 'cache', 'runtime'), updated)

    def test_codex_preserves_multiline_strings_or_refuses(self):
        original = 'note = """\n[mcp_servers.codebase-memory-mcp]\ncommand = example\n"""\n'
        with self.assertRaises((ValueError, tomllib.TOMLDecodeError)):
            setup.codex_config(original, 'exe', 'cache', 'runtime')

    def test_codex_keeps_extra_graph_environment(self):
        old = '[mcp_servers.codebase-memory-mcp]\nenv_vars = ["MY_SETTING", "CBM_CACHE_DIR"]\n[mcp_servers.codebase-memory-mcp.env]\nCUSTOM = "keep"\n'
        entry = tomllib.loads(setup.codex_config(old, 'exe', 'cache', 'runtime'))['mcp_servers'][setup.SERVER]
        self.assertEqual(entry['env']['CUSTOM'], 'keep')
        self.assertEqual(entry['env_vars'], ['MY_SETTING'])

    def test_codex_does_not_remove_disabled_or_restricted_policy(self):
        with self.assertRaises(ValueError):
            setup.codex_config('[mcp_servers.codebase-memory-mcp]\nenabled = false\n', 'exe', 'cache', 'runtime')

    def test_invalid_cursor_config_does_not_get_replaced(self):
        with self.assertRaises(ValueError):
            setup.cursor_config('{ broken', 'exe', 'cache', 'runtime')

    def test_remote_cursor_server_is_preserved(self):
        with self.assertRaises(ValueError):
            setup.cursor_config('{"mcpServers":{"codebase-memory-mcp":{"url":"https://example.test"}}}', 'exe', 'cache', 'runtime')

    def test_backup_and_idempotence(self):
        target = self.root / 'config.toml'
        target.write_text('original')
        setup.write_backup(target, 'updated')
        setup.write_backup(target, 'updated')
        backups = list(self.root.glob('*.pre-repro-graph-*'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), 'original')

    def test_guidance_preserves_user_text_and_is_idempotent(self):
        once = setup.managed_guidance('My instructions\n')
        self.assertIn('My instructions', once)
        self.assertEqual(setup.managed_guidance(once), once)

    def test_archive_checksum_and_path_traversal(self):
        archive = self.root / 'release.zip'
        with zipfile.ZipFile(archive, 'w') as bundle:
            bundle.writestr('../../codebase-memory-mcp.exe', b'synthetic')
            bundle.writestr('../../escape.txt', b'never extract')
        target = self.root / 'install'
        with self.assertRaises(ValueError):
            setup.extract_verified(archive, 'wrong', target)
        self.assertFalse(target.exists())
        setup.extract_verified(archive, hashlib.sha256(archive.read_bytes()).hexdigest(), target)
        self.assertEqual((target / 'codebase-memory-mcp.exe').read_bytes(), b'synthetic')
        self.assertEqual([p.name for p in target.iterdir()], ['codebase-memory-mcp.exe'])

    def test_prepare_is_machine_local_and_preserves_roots(self):
        home = self.root / 'different user'; base = home / '.local/share/repro-graph'
        base.mkdir(parents=True)
        (base / 'roots.json').write_text('{"roots":["custom"],"discover_clients":false}')
        changes = setup.prepare(home, base, 'exe', 'cache', 'runtime', home / '.codex')
        self.assertNotIn(base / 'roots.json', changes)
        self.assertTrue(all(p.is_relative_to(home) for p in changes))
        self.assertIn(str(base), changes[base / 'run.ps1'])

    def test_cold_install_creates_coordination_directories_before_cli(self):
        home = self.root / 'new-user'
        cache, runtime = home / 'cache', home / 'runtime'
        def cli(*args, **kwargs):
            self.assertTrue(cache.is_dir())
            self.assertTrue(runtime.is_dir())
            return subprocess.CompletedProcess([], 0)
        with patch.dict(os.environ, {'CBM_CACHE_DIR':str(cache), 'CBM_RUNTIME_DIR':str(runtime)}), patch.object(setup, 'extract_verified'), patch.object(setup.subprocess, 'run', side_effect=cli):
            setup.install(home, home / 'state', home / 'apps', home / '.codex', self.root / 'archive.zip')
        self.assertTrue((home / 'state/settings.json').is_file())

    def test_git_repeated_uncommitted_edits(self):
        subprocess.run(['git', 'init', str(self.root)], check=True, capture_output=True)
        source = self.root / 'probe.py'
        source.write_text('def first(): return 1')
        first = watch.fingerprint(self.root)
        source.write_text('def second_changed(): return 2')
        self.assertNotEqual(first, watch.fingerprint(self.root))

    def test_nongit_deleted_and_sensitive_metadata(self):
        source = self.root / 'probe.py'; source.write_text('def one(): return 1')
        first = watch.fingerprint(self.root)
        (self.root / 'auth.json').write_text('synthetic')
        (self.root / '.env').write_text('synthetic')
        self.assertEqual(first, watch.fingerprint(self.root))
        source.unlink()
        self.assertEqual(watch.fingerprint(self.root)[1], 0)

    def test_index_failure_retries_and_never_marks_fresh(self):
        source = self.root / 'source'; source.mkdir()
        (source / 'probe.py').write_text('def one(): return 1')
        with patch.object(watch, 'BASE', self.root / 'state'), patch.object(watch, 'index', side_effect=RuntimeError('synthetic')) as index:
            for _ in range(2):
                row = watch.sweep([source])[0]
                self.assertEqual(row['status'], 'error')
                self.assertNotIn('fingerprint', row)
            self.assertEqual(index.call_count, 2)

    def test_unchanged_skips_but_last_file_deletion_reindexes(self):
        source = self.root / 'source'; source.mkdir()
        file = source / 'probe.py'; file.write_text('def one(): return 1')
        with patch.object(watch, 'BASE', self.root / 'state'), patch.object(watch, 'index') as index:
            self.assertEqual(watch.sweep([source])[0]['status'], 'indexed')
            self.assertEqual(watch.sweep([source])[0]['status'], 'unchanged')
            file.unlink()
            self.assertEqual(watch.sweep([source])[0]['status'], 'indexed')
            self.assertEqual(index.call_count, 2)

    def test_dubious_git_ownership_does_not_expand_trust(self):
        (self.root / '.git').mkdir()
        (self.root / 'probe.py').write_text('def one(): return 1')
        with patch.object(watch.subprocess, 'run', return_value=subprocess.CompletedProcess([], 128, b'', b'dubious ownership')) as run:
            self.assertEqual(watch.fingerprint(self.root)[1], 1)
            self.assertEqual(run.call_count, 1)
            self.assertNotIn('config', run.call_args.args[0])

    def test_discovery_avoids_broad_and_excluded_roots(self):
        home = self.root / 'user'; base = home / '.local/share/repro-graph'; base.mkdir(parents=True)
        projects = home / 'Projects'; repo = projects / 'repo'; (repo / '.git').mkdir(parents=True)
        excluded = projects / 'excluded'; (excluded / '.git').mkdir(parents=True)
        (base / 'roots.json').write_text(json.dumps({'roots':[str(home),str(projects), str(base)], 'exclude':[str(excluded)], 'discover_clients':False}))
        with patch.object(watch, 'HOME', home), patch.object(watch, 'BASE', base):
            self.assertEqual(watch.discovered_roots(), [repo.resolve()])

    def test_malformed_scope_fails_instead_of_enabling_discovery(self):
        (self.root / 'roots.json').write_text('{broken')
        with patch.object(watch, 'BASE', self.root):
            with self.assertRaises(ValueError):
                watch.discovered_roots()

    def test_powershell_runner_quotes_spaces_and_apostrophes(self):
        runner = setup.runner(Path("C:/Users/Some One's folder"))
        self.assertIn("One''s", runner)
        self.assertIn('exit $LASTEXITCODE', runner)


if __name__ == '__main__':
    unittest.main()
