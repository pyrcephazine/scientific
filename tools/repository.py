#!/usr/bin/env python3
"""Repository setup and guards; no scheduler, manifests or experiment scaffolding."""

import argparse
from contextlib import closing
import json
from pathlib import Path
import re
import subprocess
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import registry


ROOT_FILES = {
    '.gitignore', '.gitattributes', 'AGENTS.md', 'README.md',
    'MOTIVATION.md', 'THEORY.md', 'PRIOR_WORK.md', 'EMPIRICAL_EVIDENCE.md',
    'references.bib', 'index.db',
}


def role():
    value = registry.git(ROOT, 'config', '--get', 'scientific.role')
    if value not in {'LOCAL', 'CLUSTER'}:
        raise ValueError('Configure scientific.role as LOCAL or CLUSTER')
    return value


def owner(path):
    parts = Path(path).parts
    if len(parts) == 1:
        if path not in ROOT_FILES:
            raise ValueError(f'Root path is outside AGENTS.md: {path}')
        return 'CLUSTER' if path == 'index.db' else 'LOCAL'
    if parts[0] in {'src', 'tools'}:
        return 'CLUSTER'
    if parts[0] == 'papers':
        if len(parts) != 2 or not re.fullmatch(r'.+-\d{4}-.+\.[^.]+', parts[1]):
            raise ValueError(f'Paper must be flat and named author-year-title.ext: {path}')
        return 'LOCAL'
    if parts[0] == 'experiments':
        if len(parts) != 3 or (parts[2] != 'README.md' and Path(path).suffix.lower() in {'.py', '.sh', '.sql', '.pt', '.pth', '.safetensors'}):
            raise ValueError(f'Experiment files must be flat scientific outputs, not code/weights: {path}')
        return 'CLUSTER'
    if re.fullmatch(r'.+-\d{4}-.+', parts[0]):
        return 'LOCAL'
    raise ValueError(f'Path is outside AGENTS.md: {path}')


def guard_commit():
    paths = registry.git(ROOT, 'diff', '--cached', '--name-only', '-z').split('\0')
    current = role()
    deleted = set(registry.git(ROOT, 'diff', '--cached', '--diff-filter=D', '--name-only', '-z').split('\0'))
    for path in filter(None, paths):
        # LOCAL may remove obsolete root files outside the current allowlist.
        if path in deleted and len(Path(path).parts) == 1 and path not in ROOT_FILES and current == 'LOCAL':
            continue
        if owner(path) != current:
            raise ValueError(f'{current} may not author changes to {path}')
        if path == 'index.db' and registry.git(ROOT, 'branch', '--show-current') != 'main':
            raise ValueError('Registry changes belong strictly on main')


def guard_push(arguments, payload):
    current = role()
    for line in payload.decode().splitlines():
        local_ref, local_oid, remote_ref, remote_oid = line.split()
        if set(local_oid) == {'0'}:
            continue
        args = ['rev-list', local_oid]
        args += ['--not', '--remotes'] if set(remote_oid) == {'0'} else ['^' + remote_oid]
        for commit in registry.git(ROOT, *args).splitlines():
            changed = registry.git(ROOT, 'diff-tree', '--root', '--no-commit-id', '--name-only', '-r', commit, '--', 'index.db')
            if changed and (current != 'CLUSTER' or remote_ref != 'refs/heads/main' or local_ref != 'refs/heads/main'):
                raise ValueError('Only CLUSTER main may push new registry versions to remote main')
    subprocess.run(['git', '-C', str(ROOT), 'lfs', 'pre-push', *arguments], input=payload, check=True)


def setup(selected):
    registry.initialize(ROOT)
    subprocess.run(['git', '-C', str(ROOT), 'lfs', 'install', '--local', '--skip-repo'], check=True)
    subprocess.run(['git', '-C', str(ROOT), 'config', '--local', 'scientific.role', selected], check=True)
    subprocess.run(['git', '-C', str(ROOT), 'config', '--local', 'pull.ff', 'only'], check=True)
    if has_config('core.hooksPath'):
        raise ValueError('A custom core.hooksPath already exists; integrate its hooks explicitly')
    hooks = Path(registry.git(ROOT, 'rev-parse', '--git-path', 'hooks'))
    if not hooks.is_absolute():
        hooks = ROOT / hooks
    hooks.mkdir(parents=True, exist_ok=True)
    for name, command in [('pre-commit', 'guard-commit'), ('pre-push', 'guard-push "$@"')]:
        path = hooks / name
        text = f'#!/bin/sh\n# scientific repository guard\nexec python3 tools/repository.py {command}\n'
        if path.exists() and path.read_text() != text:
            raise ValueError(f'Existing {name} hook must be integrated, not overwritten')
        path.write_text(text)
        path.chmod(0o755)
    print(f'Setup complete: role={selected}; LFS configured; ownership hooks installed; no commits created.')


def has_config(key):
    return subprocess.run(['git', '-C', str(ROOT), 'config', '--get', key], stdout=subprocess.DEVNULL).returncode == 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='operation', required=True)
    p = sub.add_parser('setup'); p.add_argument('--role', choices=['LOCAL', 'CLUSTER'], required=True)
    p = sub.add_parser('query'); p.add_argument('sql'); p.add_argument('--params', default='[]')
    sub.add_parser('sync')
    sub.add_parser('stage-registry')
    sub.add_parser('guard-commit')
    p = sub.add_parser('guard-push'); p.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.operation == 'setup':
        setup(args.role)
    elif args.operation == 'query':
        print(json.dumps(registry.query_registry(args.sql, json.loads(args.params), root=ROOT), indent=2))
    elif args.operation == 'sync':
        if role() != 'LOCAL':
            raise ValueError('This sync helper is for LOCAL; a live supervisor must quiesce its writer first')
        with registry.repository_lock(ROOT, exclusive=True):
            subprocess.run(['git', '-C', str(ROOT), 'pull', '--ff-only'], check=True)
            subprocess.run(['git', '-C', str(ROOT), 'lfs', 'pull'], check=True)
    elif args.operation == 'stage-registry':
        registry.assert_writer(ROOT)
        with registry.repository_lock(ROOT, exclusive=True):
            with closing(sqlite3.connect((ROOT / 'index.db').as_uri() + '?mode=ro', uri=True)) as conn:
                if conn.execute('PRAGMA quick_check').fetchone() != ('ok',):
                    raise ValueError('Registry integrity check failed')
            subprocess.run(['git', '-C', str(ROOT), 'add', '--', 'index.db'], check=True)
    elif args.operation == 'guard-commit':
        guard_commit()
    elif args.operation == 'guard-push':
        guard_push(args.arguments, sys.stdin.buffer.read())


if __name__ == '__main__':
    try:
        main()
    except (ValueError, PermissionError, subprocess.CalledProcessError) as error:
        print(f'Repository operation refused: {error}', file=sys.stderr)
        sys.exit(1)
