"""Contract tests; all databases, commits and remotes are temporary fixtures."""

from contextlib import closing
import importlib.util
import os
from pathlib import Path
import shlex
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest

import registry


PROJECT = Path(__file__).resolve().parents[1]


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='scientific-test-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'repo'
        self.root.mkdir()
        for name in ['src/schema.sql', 'src/registry.py', 'tools/repository.py', '.gitattributes']:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(PROJECT / name, target)
        self.git('init', '--quiet', '-b', 'main')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('add', 'src', 'tools', '.gitattributes')
        self.git('commit', '--quiet', '-m', 'Temporary source fixture')
        self.code = self.git('rev-parse', 'HEAD').stdout.strip()
        self.git('update-ref', 'refs/remotes/origin/main', self.code)
        self.git('config', 'scientific.role', 'CLUSTER')
        registry.initialize(self.root)

    def git(self, *args, check=True, **kwargs):
        return subprocess.run(['git', '-C', str(self.root), *args], check=check,
                              capture_output=True, text=True, **kwargs)

    def tool(self, *args, check=True, **kwargs):
        return subprocess.run([sys.executable, str(self.root / 'tools/repository.py'), *args],
                              check=check, capture_output=True, text=True, **kwargs)

    def row(self):
        return registry.query_registry('SELECT * FROM experiments', root=self.root)[0]

    def register(self, identifier='example'):
        return registry.register(identifier, {'seed': 1}, self.code, root=self.root)

    def test_empty_schema_and_non_destructive_setup(self):
        self.assertEqual(registry.query_registry("SELECT name FROM sqlite_master WHERE type='table'", root=self.root), [{'name': 'experiments'}])
        self.assertEqual(registry.query_registry('SELECT * FROM experiments', root=self.root), [])
        self.register()
        registry.initialize(self.root)
        self.assertEqual(self.row()['experiment_id'], 'example')
        with self.assertRaises(sqlite3.OperationalError):
            registry.query_registry('DELETE FROM experiments', root=self.root)

    def test_lifecycle_fences_and_preserved_technical_issue(self):
        self.register()
        with self.assertRaises(sqlite3.IntegrityError):
            self.register('same-specification')
        token = registry.claim('example', 'test invocation', root=self.root)
        self.assertIsNone(registry.claim('example', 'duplicate', root=self.root))
        with self.assertRaises(ValueError):
            registry.complete('example', 'stale', root=self.root)
        with self.assertRaises(ValueError):
            registry.retry('example', token, 'node stopped', root=self.root)
        registry.retry('example', token, 'node stopped', jobs_terminated=True, root=self.root)
        replacement = registry.claim('example', 'test invocation', root=self.root)
        self.assertNotEqual(token, replacement)
        self.assertEqual(self.row()['last_execution_issue'], 'node stopped')
        with self.assertRaises(ValueError):
            registry.update_execution('example', token, scheduler_ref='old', root=self.root)
        registry.mark_started('example', replacement, root=self.root)
        registry.complete('example', replacement, root=self.root)
        self.assertEqual(self.row()['status'], 'COMPLETED')
        with self.assertRaises(ValueError):
            registry.cancel('example', 'already terminal', root=self.root)

    def test_role_branch_and_unpublished_code_guards(self):
        self.git('config', 'scientific.role', 'LOCAL')
        with self.assertRaises(PermissionError):
            self.register()
        self.git('config', 'scientific.role', 'CLUSTER')
        self.git('switch', '--quiet', '-c', 'other')
        with self.assertRaises(PermissionError):
            self.register()
        self.git('switch', '--quiet', 'main')
        self.git('commit', '--quiet', '--allow-empty', '-m', 'Not published')
        with self.assertRaises(subprocess.CalledProcessError):
            registry.register('unpublished', {}, self.git('rev-parse', 'HEAD').stdout.strip(), root=self.root)

    def test_concurrent_claims_have_one_winner(self):
        self.register()
        program = 'import registry,sys;from pathlib import Path;print(registry.claim("example","test",root=Path(sys.argv[1])))'
        processes = [subprocess.Popen([sys.executable, '-c', program, str(self.root)],
                                     cwd=self.root / 'src', stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True) for _ in range(4)]
        answers = []
        for process in processes:
            out, error = process.communicate(timeout=15)
            self.assertEqual(process.returncode, 0, error)
            answers.append(out.strip())
        self.assertEqual(sum(answer != 'None' for answer in answers), 1)

    def test_trigger_and_snapshot(self):
        self.register()
        with closing(sqlite3.connect(self.root / 'index.db')) as conn:
            conn.create_function('current_timestamp', 0, lambda: '2000-01-01 00:00:00')
            conn.execute('PRAGMA recursive_triggers=ON')
            conn.execute("UPDATE experiments SET updated_at='1999-01-01 00:00:00'")
            for number in range(100):
                conn.execute('UPDATE experiments SET hypothesis_ref=?', (str(number),))
            conn.commit()
        self.assertEqual(self.row()['updated_at'], '2000-01-01 00:00:00')
        destination = Path(self.temporary.name) / 'snapshot.db'
        registry.snapshot(destination, root=self.root)
        with closing(sqlite3.connect(destination)) as conn:
            self.assertEqual(conn.execute('PRAGMA integrity_check').fetchone(), ('ok',))
            self.assertEqual(conn.execute('SELECT experiment_id FROM experiments').fetchall(), [('example',)])
        with self.assertRaises(ValueError):
            registry.snapshot(self.root / 'index.db', root=self.root)

    def test_query_lock_excludes_repository_replacement(self):
        program = ('import registry,sys;from pathlib import Path;print("ready",flush=True);'
                   '\nwith registry.repository_lock(Path(sys.argv[1]),exclusive=True):print("exclusive",flush=True)')
        with registry.repository_lock(self.root):
            process = subprocess.Popen([sys.executable, '-c', program, str(self.root)],
                                       cwd=self.root / 'src', stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True)
            self.assertEqual(process.stdout.readline().strip(), 'ready')
            with self.assertRaises(subprocess.TimeoutExpired):
                process.communicate(timeout=0.1)
        out, error = process.communicate(timeout=10)
        self.assertEqual(process.returncode, 0, error)
        self.assertIn('exclusive', out)

    def test_git_hooks_lfs_and_branch_ownership(self):
        obsolete = self.root / 'SPECIFICATION.md'
        obsolete.write_text('Historical protocol fixture\n')
        self.git('add', 'SPECIFICATION.md')
        self.git('commit', '--quiet', '-m', 'Historical protocol fixture')
        self.tool('setup', '--role', 'LOCAL')
        obsolete.unlink()
        self.git('add', '--', 'SPECIFICATION.md')
        self.git('commit', '--quiet', '-m', 'Retire standalone specification')
        obsolete.write_text('Must not reintroduce a second protocol\n')
        self.git('add', 'SPECIFICATION.md')
        refused = self.git('commit', '-m', 'Must be rejected', check=False)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn('outside AGENTS.md', refused.stderr)
        self.git('reset', '--quiet', '--', 'SPECIFICATION.md')
        obsolete.unlink()
        self.git('add', 'index.db')
        refused = self.git('commit', '-m', 'Must be rejected', check=False)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn('LOCAL may not author', refused.stderr)
        self.git('config', 'scientific.role', 'CLUSTER')
        self.tool('stage-registry')
        self.git('commit', '--quiet', '-m', 'Empty registry fixture')
        self.assertIn('https://git-lfs.github.com/spec/v1', self.git('show', 'HEAD:index.db').stdout)
        self.git('config', 'scientific.role', 'LOCAL')
        head = self.git('rev-parse', 'HEAD').stdout.strip()
        payload = f'refs/heads/main {head} refs/heads/main {"0"*40}\n'
        refused = self.tool('guard-push', 'origin', 'unused', input=payload, check=False)
        self.assertNotEqual(refused.returncode, 0)
        self.git('config', 'scientific.role', 'CLUSTER')
        remote = Path(self.temporary.name) / 'remote.git'
        subprocess.run(['git', 'init', '--quiet', '--bare', str(remote)], check=True)
        self.git('remote', 'add', 'origin', str(remote))
        self.git('push', '--quiet', 'origin', 'main')
        self.assertTrue(any((remote / 'lfs/objects').rglob('*')))
        self.git('switch', '--quiet', '-c', 'feature')
        with closing(sqlite3.connect(self.root / 'index.db')) as conn:
            conn.execute("INSERT INTO experiments(experiment_id,spec_hash,spec_json,code_commit) VALUES('temporary','x','{}','fixture')")
            conn.commit()
        self.git('add', 'index.db')
        refused = self.git('commit', '-m', 'Wrong branch', check=False)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn('strictly on main', refused.stderr)

    def test_hooks_pin_setup_interpreter_and_upgrade_generated_hooks(self):
        hooks = self.root / '.git/hooks'
        commands = {'pre-commit': 'guard-commit', 'pre-push': 'guard-push "$@"'}
        prefix = '#!/bin/sh\n# scientific repository guard\nexec '
        for name, command in commands.items():
            (hooks / name).write_text(prefix + f'python3 tools/repository.py {command}\n')
        executable = Path(self.temporary.name) / "Python env's $(false)" / 'python3'
        executable.parent.mkdir()
        executable.symlink_to(sys.executable)
        invocation = [str(executable), str(self.root / 'tools/repository.py'), 'setup', '--role', 'LOCAL']
        subprocess.run(invocation, check=True, capture_output=True, text=True)
        expected = {name: prefix + shlex.quote(str(executable)) + f' tools/repository.py {command}\n'
                    for name, command in commands.items()}
        for name, text in expected.items():
            self.assertEqual((hooks / name).read_text(), text)
        subprocess.run(invocation, check=True, capture_output=True, text=True)
        self.assertEqual({name: (hooks / name).read_text() for name in commands}, expected)
        unavailable_python = Path(self.temporary.name) / 'old-python'
        unavailable_python.mkdir()
        replacement = unavailable_python / 'python3'
        replacement.write_text('#!/bin/sh\nexit 97\n')
        replacement.chmod(0o755)
        environment = dict(os.environ, PATH=str(unavailable_python) + os.pathsep + os.environ['PATH'])
        remote = Path(self.temporary.name) / 'remote.git'
        subprocess.run(['git', 'init', '--quiet', '--bare', str(remote)], check=True)
        self.git('remote', 'add', 'origin', str(remote))
        for name, arguments in [('pre-commit', []), ('pre-push', ['origin', str(remote)])]:
            result = subprocess.run([str(hooks / name), *arguments], cwd=self.root, env=environment,
                                    input='', capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        self.tool('setup', '--role', 'LOCAL')
        self.assertEqual((hooks / 'pre-commit').read_text(),
                         prefix + shlex.quote(str(Path(sys.executable).absolute())) + ' tools/repository.py guard-commit\n')

    def test_setup_preserves_unrelated_or_symlinked_hooks(self):
        hook = self.root / '.git/hooks/pre-commit'
        for content in ['#!/bin/sh\necho custom\n',
                        '#!/bin/sh\n# scientific repository guard\nexec python3 tools/repository.py guard-commit\n# custom\n']:
            with self.subTest(content=content):
                hook.write_text(content)
                refused = self.tool('setup', '--role', 'LOCAL', check=False)
                self.assertNotEqual(refused.returncode, 0)
                self.assertIn('must be integrated', refused.stderr)
                self.assertEqual(hook.read_text(), content)
        target = Path(self.temporary.name) / 'external-hook'
        target.write_text('#!/bin/sh\n# scientific repository guard\nexec python3 tools/repository.py guard-commit\n')
        hook.unlink()
        hook.symlink_to(target)
        refused = self.tool('setup', '--role', 'LOCAL', check=False)
        self.assertNotEqual(refused.returncode, 0)
        self.assertTrue(hook.is_symlink())
        self.assertIn('exec python3 ', target.read_text())


if __name__ == '__main__':
    unittest.main()
