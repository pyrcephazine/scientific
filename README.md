# Scientific project scaffold

This is a blank, reusable implementation of [AGENTS.md](AGENTS.md). It contains an empty SQLite registry, Git/LFS configuration, ownership hooks and small registry utilities. No experiments, scientific claims, remote repository or cluster jobs are configured.

## Start a project

1. Fill in `MOTIVATION.md` with the human-approved scientific goal and resource limits. Use `THEORY.md`, `PRIOR_WORK.md` and `EMPIRICAL_EVIDENCE.md` for their corresponding scientific accounts.
2. Configure a Git remote with LFS support. Do not share independent writable registry copies.
3. After cloning, run `python3 tools/repository.py setup --role LOCAL` on LOCAL and `python3 tools/repository.py setup --role CLUSTER` on the supervisor checkout. This installs repository-local LFS settings and hooks. It creates a blank registry only if none exists; existing registries are preserved.
4. Add real implementation and environment definitions under `src/`, utilities under `tools/`, and literature under `papers/` when needed. Do not create placeholder experiment folders or bulk-storage directories.
5. Publish the source commit to `origin/main` before registering/claiming real experiments. Choose the actual persistent cache, weights and temporary-work locations on the cluster.

Python 3.10+ on a POSIX system is sufficient for the scaffold; its Python code uses only the standard library. Git and Git LFS are external requirements. Add a real environment lock under `src/` when the scientific workload introduces dependencies.

## Files

| Path | Purpose |
|---|---|
| `AGENTS.md` | Full operating contract and additional agent instructions |
| `src/schema.sql` | Exact one-table schema and timestamp trigger from the specification |
| `src/registry.py` | Initialization, locked read-only queries, registration, conditional lifecycle updates and consistent snapshots |
| `tools/repository.py` | Setup, query, synchronized fast-forward updates and Git ownership hooks |
| `src/test_registry.py` | Regression tests using temporary repositories and databases |
| `index.db` | Empty registry containing only the `experiments` table |
| `.gitattributes`, `.gitignore` | LFS/binary-merge rules and cluster-data exclusions |

## Use the registry

LOCAL can inspect a snapshot without leaving connections open:

```sh
python3 tools/repository.py query 'SELECT experiment_id, status FROM experiments'
python3 tools/repository.py sync
```

The synchronization command requires `origin/main`. It holds the same host-local exclusive lock used by the registry helpers, then performs a strict fast-forward and LFS download. It never resolves conflicts or discards local changes automatically.

The supervisor imports `src.registry` to register a frozen specification, claim it, record its job reference, and record completion, retry or cancellation. Write functions require the CLUSTER role on `main`. Registration and claiming also require the pinned source commit to be reachable from the locally fetched `origin/main`.

The supervisor remains responsible for fresh scheduler/quota checks, exclusive lifetime ownership, actual job submission, immutable worker code, artifact validation, checkpoint promotion, and Git/LFS synchronization. These depend on the real project and cluster; this scaffold does not invent a scheduler or run dummy experiments. Do not call `complete()` before those required validations and filesystem writes are finished.

`retry()` requires explicit confirmation that the old jobs terminated. Dispatch-matching updates reject stale tokens. Technical explanations survive retry claims. `snapshot()` uses SQLite's Backup API and same-filesystem replacement; close/pause the live writer before staging the root database directly.

The supervisor can use `python3 tools/repository.py stage-registry` to integrity-check and stage the closed registry while holding the exclusive host-local lock. Stage the corresponding validated experiment files for the same commit. The lock is host-local; it does not replace exclusive supervisor lifetime ownership across cluster nodes.

## Git ownership

The setup command configures `scientific.role`, `pull.ff=only`, LFS filters, and hooks under `.git/hooks/`. The commit hook checks the closed-world tracked-path allowlist and role ownership. The push hook rejects new LOCAL-authored registry changes and registry updates targeting anything except remote `main`, and then runs the Git LFS pre-push hook with its original input.

LOCAL may not commit `index.db`. Initial provisioning is supervisor work: make the registry's first commit from the CLUSTER logical role on `main`. No commits are made by setup. For the first project commit, stage LOCAL-owned documentation separately from CLUSTER-owned implementation/registry files and use the appropriate logical role for each commit.

Hooks are safeguards for cooperative agents, not a substitute for remote permissions. Install matching remote checks if the hosting service supports them. No remote has been chosen in this scaffold.

## Verify

```sh
python3 -m unittest discover -s src -p 'test_*.py' -v
```

Tests use temporary files and leave the blank project registry untouched.
# scientific
