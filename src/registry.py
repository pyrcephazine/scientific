"""Small POSIX/stdlib registry implementation; cluster policy stays in the supervisor."""

from contextlib import closing, contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import uuid


ROOT = Path(__file__).resolve().parents[1]


def git(root, *args):
    return subprocess.check_output(
        ['git', '-C', str(root), *args], text=True, stderr=subprocess.PIPE
    ).strip()


@contextmanager
def repository_lock(root=ROOT, *, exclusive=False):
    """Coordinate queries, writers and Git replacement on this host only."""
    identity = hashlib.sha256(str(Path(root).resolve()).encode()).hexdigest()
    directory = Path(tempfile.gettempdir()) / f'scientific-locks-{os.getuid()}'
    directory.mkdir(mode=0o700, exist_ok=True)
    with (directory / identity).open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def initialize(root=ROOT):
    """Provision a new empty database once; never overwrite an existing one."""
    root = Path(root)
    path = root / 'index.db'
    with repository_lock(root, exclusive=True):
        if path.exists():
            with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as conn:
                names = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                if names != [('experiments',)]:
                    raise ValueError('Existing registry has an unexpected schema; migrate explicitly')
            return
        try:
            with closing(sqlite3.connect(path)) as conn:
                conn.executescript((root / 'src/schema.sql').read_text())
                conn.commit()
        except Exception:
            # Only the new file created by this initializer may be discarded.
            path.unlink(missing_ok=True)
            raise


def query_registry(query, params=(), *, root=ROOT):
    with repository_lock(root):
        uri = (Path(root).resolve() / 'index.db').as_uri() + '?mode=ro'
        with closing(sqlite3.connect(uri, uri=True)) as conn:
            conn.row_factory = sqlite3.Row
            with closing(conn.execute(query, params)) as cursor:
                return [dict(row) for row in cursor.fetchall()]


def assert_writer(root=ROOT):
    try:
        role = git(root, 'config', '--get', 'scientific.role')
    except subprocess.CalledProcessError:
        role = ''
    if role != 'CLUSTER' or git(root, 'branch', '--show-current') != 'main':
        raise PermissionError('Registry writes require scientific.role=CLUSTER on main')


@contextmanager
def writer(root=ROOT):
    assert_writer(root)
    with repository_lock(root, exclusive=True):
        uri = (Path(root).resolve() / 'index.db').as_uri() + '?mode=rw'
        with closing(sqlite3.connect(uri, uri=True, isolation_level=None)) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute('PRAGMA journal_mode=DELETE')
            conn.execute('PRAGMA synchronous=FULL')
            conn.execute('PRAGMA busy_timeout=60000')
            conn.execute('PRAGMA foreign_keys=ON')
            yield conn


def verify_code_commit(root, code_commit):
    resolved = git(root, 'rev-parse', '--verify', code_commit + '^{commit}')
    subprocess.run(
        ['git', '-C', str(root), 'merge-base', '--is-ancestor', resolved, 'refs/remotes/origin/main'],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )
    return resolved


def register(experiment_id, specification, code_commit, *, hypothesis_ref=None, root=ROOT):
    if not experiment_id or experiment_id in {'.', '..'} or '/' in experiment_id or '\\' in experiment_id:
        raise ValueError('experiment_id must be one safe directory name')
    if not isinstance(specification, dict):
        raise TypeError('The specification must be a JSON object')
    assert_writer(root)
    code_commit = verify_code_commit(root, code_commit)
    spec = json.dumps(specification, sort_keys=True, separators=(',', ':'), allow_nan=False)
    fingerprint = json.dumps([code_commit, specification], sort_keys=True, separators=(',', ':'), allow_nan=False)
    digest = hashlib.sha256(fingerprint.encode()).hexdigest()
    with writer(root) as conn:
        conn.execute(
            'INSERT INTO experiments(experiment_id,spec_hash,spec_json,hypothesis_ref,code_commit) VALUES(?,?,?,?,?)',
            (experiment_id, digest, spec, hypothesis_ref, code_commit),
        )
    return digest


def claim(experiment_id, command, *, root=ROOT):
    """Claim only; caller must perform current quota/scheduler checks and submit safely."""
    if not command:
        raise ValueError('An execution command is required')
    assert_writer(root)
    records = query_registry('SELECT code_commit FROM experiments WHERE experiment_id=?', (experiment_id,), root=root)
    if not records:
        raise KeyError(experiment_id)
    verify_code_commit(root, records[0]['code_commit'])
    token = str(uuid.uuid4())
    with writer(root) as conn:
        conn.execute('BEGIN IMMEDIATE')
        try:
            changed = conn.execute(
                "UPDATE experiments SET status='RUNNING',dispatch_id=?,command=?,scheduler_ref=NULL,"
                "device_info=NULL,started_at=NULL,completed_at=NULL,cancellation_reason=NULL "
                "WHERE experiment_id=? AND status='PENDING'", (token, command, experiment_id),
            ).rowcount
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return token if changed == 1 else None


def update_execution(experiment_id, dispatch_id, *, root=ROOT, **values):
    allowed = {'scheduler_ref', 'device_info'}
    if not values or set(values) - allowed:
        raise ValueError('Only scheduler_ref and device_info may be updated here')
    assignments = ','.join(f'{key}=?' for key in values)
    _change(root, experiment_id, dispatch_id, assignments, tuple(values.values()))


def mark_started(experiment_id, dispatch_id, *, root=ROOT):
    _change(root, experiment_id, dispatch_id, 'started_at=CURRENT_TIMESTAMP', ())


def complete(experiment_id, dispatch_id, *, root=ROOT):
    """Record completion only after the supervisor validated and durably saved outputs."""
    _change(root, experiment_id, dispatch_id, "status='COMPLETED',completed_at=CURRENT_TIMESTAMP", ())


def retry(experiment_id, dispatch_id, reason, *, jobs_terminated=False, root=ROOT):
    if not jobs_terminated or not reason.strip():
        raise ValueError('Confirm termination of old jobs and provide a technical explanation')
    _change(root, experiment_id, dispatch_id,
            "status='PENDING',dispatch_id=NULL,scheduler_ref=NULL,last_execution_issue=?", (reason,))


def cancel(experiment_id, reason, *, dispatch_id=None, root=ROOT):
    if not reason.strip():
        raise ValueError('A cancellation reason is required')
    with writer(root) as conn:
        changed = conn.execute(
            "UPDATE experiments SET status='CANCELLED',cancellation_reason=? WHERE experiment_id=? "
            "AND ((status='PENDING' AND ? IS NULL) OR (status='RUNNING' AND dispatch_id=?))",
            (reason, experiment_id, dispatch_id, dispatch_id),
        ).rowcount
        if changed != 1:
            raise ValueError('Study is absent, terminal or has a different active dispatch')


def _change(root, experiment_id, dispatch_id, assignments, parameters):
    with writer(root) as conn:
        changed = conn.execute(
            f"UPDATE experiments SET {assignments} WHERE experiment_id=? AND dispatch_id=? AND status='RUNNING'",
            (*parameters, experiment_id, dispatch_id),
        ).rowcount
        if changed != 1:
            raise ValueError('Study is absent, terminal or has a different active dispatch')


def snapshot(destination, *, root=ROOT):
    """Export a self-contained snapshot elsewhere; do not replace the open source DB."""
    destination = Path(destination).resolve()
    if destination == (Path(root).resolve() / 'index.db'):
        raise ValueError('Snapshot destination must differ from the live database')
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=destination.name + '.', dir=destination.parent)
    os.close(fd)
    try:
        with repository_lock(root):
            uri = (Path(root).resolve() / 'index.db').as_uri() + '?mode=ro'
            with closing(sqlite3.connect(uri, uri=True)) as source, closing(sqlite3.connect(temporary)) as target:
                source.backup(target)
                target.execute('PRAGMA journal_mode=DELETE')
                if target.execute('PRAGMA quick_check').fetchone() != ('ok',):
                    raise ValueError('Snapshot integrity check failed')
        with open(temporary, 'rb') as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        directory = os.open(destination.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(temporary).unlink(missing_ok=True)
