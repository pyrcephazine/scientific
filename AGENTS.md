# Scientific research protocol

Last updated: 13 October 2026

When AI agents help with scientific and computational research that requires coding, they frequently overcomplicate the files and repositories that document it.

Possible causes include biases in the training data for large language models, the nature of RLHF, or multi-session agent harnesses. One highly intuitive explanation is that, because LLMs are heavily trained and conditioned on enterprise software, they tend toward the defensive and distributed design patterns seen in those examples. For example, agents inject microservice conventions—files like `deploy.json`, `audit_log.json`, and `manifest.yaml`—in cases where only a single user is responsible for the repository. Andrej Karpathy calls this a tendency to "overcomplicate code and APIs, bloat abstractions... over 1000 lines when 100 would do" ([`multica-ai/andrej-karpathy-skills`](https://github.com/multica-ai/andrej-karpathy-skills)).

In any case, the symptom is a tendency for AI agents to build complex state manifests and plumbing without an intuitive grasp of the cognitive and maintenance load they entail. The solution is to adopt a specification that deliberately enforces simplicity while maintaining an appropriate level of infrastructure for scientific studies. By strictly limiting the number, type, and role of allowable files and by explicitly forbidding superfluous scaffolding, we can compel agents to prioritize the actual scientific work and results therefrom.

This document outlines one such specification for scientific projects and experiments. IF A PROBLEM DURING A PROJECT REQUIRES AN AMENDMENT TO THESE RULES, THE REQUESTING AGENT MUST CLEARLY JUSTIFY, EXPLAIN, AND DEFINE THE CHANGE TO THE USER. AFTER CORRECTIONS AND ONLY AFTER RECEIVING EXPLICIT APPROVAL MAY THE AGENT EDIT THE RELEVANT SECTION OF `AGENTS.md`, AND MUST LOG THE DEVIATION UNDER [RECORD OF DEVIATIONS](#record-of-deviations).

---

## 1. Roles

We divide the research process into two logical domains:

- **LOCAL** is the domain of scientific synthesis—comprised of theory, analyzing scientific results in the big picture, documentation of prior results, high-level directives, literature review, and the final manuscript. This can be called "orchestration." Often, but not always, LOCAL is managed by an agent such as Codex running on the user's personal computer.
- **CLUSTER** is the domain of execution—comprised of implementation, instrumentation, executing experiments, recording data, and scientific analyses in a small and restricted picture for each experiment. While operating in this role, an agent may autonomously plan and execute follow-up experiments within the assigned scope. Often, but not always, CLUSTER is managed by a headless agent running on a high-performance computing environment (such as [NOTS](https://crc.rice.edu/), [TACC](https://www.tacc.utexas.edu/), or [Hyak](https://hyak.uw.edu/)) where experiments are to be conducted.

Despite the names, LOCAL need not always be charged to a different agent than CLUSTER in the same project. It is possible for a single agent to handle both roles simultaneously, such as when the entire project is orchestrated from one Codex session on the user's personal computer. Nonetheless, the two roles as logical concepts must remain strictly isolated.

Both LOCAL and CLUSTER may read all tracked files in this specification. As a result, a repository that intends to meet this specification must be tracked by Git (and [Git LFS](https://git-lfs.com/)) and cloned at most twice—once on LOCAL and once on CLUSTER—while untracked bulk caches, checkpoints, and scratch workspaces reside on their respective cluster storage volumes. However, only one of the two domains may hold write permission to any specific file, depending on their role as detailed below:

| Content                                                                                       | Owner   |
| :-------------------------------------------------------------------------------------------- | :------ |
| Scientific synthesis (`THEORY.md`, `MOTIVATION.md`, `PRIOR_WORK.md`, `EMPIRICAL_EVIDENCE.md`) | LOCAL   |
| Literature and manuscripts (`papers/`, `references.bib`, `<author-year-paper-title>/`)        | LOCAL   |
| Project directives (`AGENTS.md`, root `README.md`)                        | LOCAL   |
| Implementation, execution, and data acquisition (`src/`, `tools/`)                            | CLUSTER |
| Experiment narratives and compact results (`experiments/<experiment_id>/`)                    | CLUSTER |
| Provenance and execution lifecycle registry (`index.db`)                                      | CLUSTER |
| Shared immutable data, caches, and promoted checkpoints (`cache/`, `weights/`)                | CLUSTER |
| Temporary workspaces (`scratch/`)                                                             | CLUSTER |

In particular, neither domain should generate authorization files, dispatch queues, heartbeat files, state snapshots, deployment manifests, consolidation flags, or completion tickets when the necessary facts already belong in `index.db`, Git history, the live job scheduler, or scientific documents. Only useful scientific information belongs in experiment files. Agent state, credentials, and installed virtual environments (`.venv/`) are not such scientific artifacts, so do not track them.

---

## 2. Definitions

Throughout this specification, a **project** refers to the entire body of work. An **experiment** (recorded as a row in the `experiments` table of `index.db` keyed by `experiment_id`) refers to a single, frozen scientific configuration, its execution, and its output under `experiments/<experiment_id>/` that contributes evidence toward the project's goals as may be inferred from context or outlined in `MOTIVATION.md`. Each experiment has one, and only one, purpose. Altering any scientific parameter or executable code creates a new `experiment_id`, whereas retrying an unchanged configuration and pinned `code_commit` after a transient runtime error simply replaces the active `dispatch_id` of the existing experiment. A retry preserves the frozen specification and code version whereas a correction requiring a different code version receives a new `experiment_id`, with its relationship to the original recorded in `experiments/<experiment_id>/README.md`.

The final record of the project's scientific claims is held by four root-level Markdown documents maintained exclusively by LOCAL. `MOTIVATION.md` establishes the high-level scientific goals, scope, and primary research questions and should change only sparingly throughout the course of the project; any change to `MOTIVATION.md` requires explicit permission from the human user. As CLUSTER completes experiments, LOCAL reads the resulting `experiments/<experiment_id>/README.md` narratives and numerical artifacts, compares them against existing claims, and synthesizes the findings—including null, adverse, and contradictory outcomes—into `THEORY.md` and `EMPIRICAL_EVIDENCE.md`. Git commit history and inline `experiment_id` citations serve as the sole record of this consolidation; no consolidation table or acknowledgement file is permitted, because experiments may be re-evaluated and incorporated more than once if subsequent findings call earlier interpretations into question. Meanwhile, `PRIOR_WORK.md` is kept strictly separate from `THEORY.md` to create a structure that encourages novelty; whenever a derivation or empirical result already covered by existing literature is uncovered, it must be cited in `PRIOR_WORK.md` with a corresponding entry in `references.bib` rather than appended to `THEORY.md`.

Within CLUSTER, execution is divided between a single **supervisor** and one or more distributed **workers**. All executable source code, model architectures, and environment definitions reside in `src/` and `tools/`, whereas `experiments/<experiment_id>/` directories serve as records of execution and empirical results and never house experiment code. The supervisor is the sole actor permitted to modify and commit to `src/` and `tools/`. When planning a new experiment within its assigned scope, the supervisor reads the canonical synthesis documents, implements, commits, and pushes any required code changes in `src/` or `tools/` to `origin/main` to obtain a shared, immutable `code_commit` hash, freezes the experiment specification (`spec_json`), serializes its registration into `index.db`, and dispatches the job. Distributed workers are strictly read-only consumers of `src/`, `tools/`, and shared caches: each worker executes the pinned `code_commit` (materialized into its isolated `scratch/<experiment_id>/<dispatch_id>/` workspace via `git archive` or a detached worktree so concurrent supervisor edits on the main checkout never affect running jobs) and never writes directly to `src/`, `index.db`, or `experiments/`.

---

## 3. Repository Layout

To prevent agents from treating an example directory tree as a baseline onto which arbitrary new files can be grafted, this specification treats the layout below as a **closed-world path allowlist** for the tracked Git repository. The repository is cloned at most twice—once on LOCAL and once on CLUSTER. Every tracked path in the repository must conform to one of the roles shown here; any file or directory not covered by these rules is forbidden. Because this tree illustrates the maximum allowable structure across a project, empty directories and optional files must not be created in advance.

```text
<project-root>/
├── .gitignore
├── .gitattributes
├── AGENTS.md
├── README.md
│
├── MOTIVATION.md
├── THEORY.md
├── PRIOR_WORK.md
├── EMPIRICAL_EVIDENCE.md
│
├── references.bib
├── index.db
│
├── papers/
│   └── <author-year-first-four-words-title>.<ext>
│
├── src/
│   └── <shared project source code and environment definitions>
│
├── tools/
│   └── <reproducible acquisition, migration, and operational scripts>
│
├── experiments/
│   └── <experiment_id>/
│       ├── README.md
│       └── <scientific-results>.<ext>
│
└── <author-year-paper-title>/
    └── <manuscript TeX source and figure files>
```

The root directory may contain only `.gitignore`, `.gitattributes`, the six Markdown directive and project files, `references.bib`, and `index.db` (alongside its untracked SQLite recovery sidecars `index.db-journal`, `index.db-wal`, and `index.db-shm`, and an optional untracked root `.venv/`). Any reference papers downloaded into `papers/` must sit flatly in that directory under the naming convention `author-year-first-four-words-title.ext` (where `ext` is typically `pdf`), and all TeX bibliography citations across the entire repository must resolve to the root-level `references.bib`.

All shared library code, model architectures, and environment specifications belong in `src/`, while utility scripts for repetitive tasks—such as dataset preparation, schema migrations, or interacting with Slurm—belong in `tools/`. Each `experiments/<experiment_id>/` directory is independently owned by CLUSTER and holds a single `README.md`—recording the experimental rationale, execution notes, and initial analysis—alongside compact scientific result files in whatever format is scientifically appropriate (such as `.csv`, `.parquet`, `.npz`, or `.npy`). Source code, scripts, and virtual environments must never be placed inside `experiments/`. Finally, when a manuscript is prepared, its TeX sources and figures reside in a dedicated `<author-year-paper-title>/` directory at the repository root (using the full or short paper title), which CLUSTER must never edit.

---

## 4. Storage and Cache

High-performance computing environments typically separate persistent bulk storage (often `$WORK`) from high-bandwidth temporary storage (`$SCRATCH`), both of which are distinct from the user's LOCAL machine. Rather than cloning the Git repository onto every storage device, the Git repository is cloned at most once on LOCAL and once on CLUSTER. Untracked bulk assets (`cache/` and `weights/`) and disposable execution workspaces (`scratch/`) live in external storage roots on the cluster.

```text
<cluster-persistent-storage>/               # e.g., $WORK/<project-name>/ (UNTRACKED)
├── cache/
│   ├── manifest.json
│   ├── datasets/
│   └── models/
└── weights/
    └── <experiment_id>/

<cluster-scratch-storage>/                  # e.g., $SCRATCH/<project-name>/ (UNTRACKED)
└── scratch/
    └── <experiment_id>/<dispatch_id>/
```

If a project runs on hardware with fewer than three distinct storage devices (for example, a single workstation or a cluster with unified storage), these logical storage domains may reside on the same physical disk—or be symlinked into `<project-root>/`, where `.gitignore` prevents them from being committed—without ever duplicating the Git repository itself.

| Tier                                                    | Contents and Retention                                                                                                                                                                                                                                                           |
| :------------------------------------------------------ | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Git and Git LFS** (LOCAL & CLUSTER)                   | Scientific documents, executable code, environment and acquisition specifications, `index.db`, results tables, literature PDFs, and published numerical artifacts needed for analysis.                                                                                           |
| **Retained CLUSTER** (`cache/`, `weights/` — untracked) | Fixed cache inputs (`cache/`) and promoted checkpoints (`weights/<experiment_id>/`). Locations remain stable across experiments and do not rely on access-time refresh to survive.                                                                                               |
| **Temporary SCRATCH** (`scratch/` — untracked)          | Isolated worker directories (`scratch/<experiment_id>/<dispatch_id>/`), incomplete outputs, heavy working tensors, download/unpack staging, and expendable recovery checkpoints. Contents may vanish at any time without losing required evidence or reconstruction information. |

While `cache/` and `weights/` must physically reside on persistent CLUSTER storage, `scratch/` may resolve to shared temporary filesystems or disks present only on each HPC node. Any symlink from CLUSTER into temporary storage inherits that temporary storage's retention risk, and scratch can disappear entirely if the compute node fails. Consequently, any state required for recovery or downstream dependency must have a surviving copy in persistent CLUSTER storage. Even without bulk cluster assets, the tracked LOCAL checkout always retains enough code, specifications, input recipes, and measured evidence to reproduce all analyses and rerun computations once raw inputs are re-acquired. Because rerunning stochastic computation does not recover the exact historical data, the measurements underlying reported claims are always preserved in `experiments/`.

To prevent redundant downloads in `cache/`, datasets, pretrained models, and fixed representations are published once into immutable, project-wide versions indexed in `cache/manifest.json`. Each version is uniquely identified by its raw input or model revision and any other information needed for this purpose. Compute workers consume these published versions strictly read-only and never independently replace or duplicate shared assets. All acquisition and preparation logic must remain reproducible through versioned code in `src/` or `tools/`; any unique input that cannot be programmatically re-downloaded or regenerated requires retained CLUSTER storage and an explicit statement that declares this dependency.

---

## 5. Git, Git LFS, and Synchronization

Both LOCAL and CLUSTER checkouts share a single Git history. Text documents, source code, and compact CSV tables use standard Git, whereas `index.db` and selected binary scientific artifacts use [Git LFS](https://git-lfs.com/). LFS rules never override the `.gitignore` exclusion of heavy caches (`cache/`, `weights/`) and working state (`scratch/`).

### `.gitignore`

```gitignore
# Bulk cluster assets and working state (if symlinked or mounted under root)
/cache/
/scratch/
/weights/

# SQLite operational sidecars: preserve for recovery; do not commit
/index.db-journal
/index.db-wal
/index.db-shm

# Installed environments and Python artifacts
.venv/
__pycache__/
*.pyc
```

Ignoring SQLite operational sidecars prevents them from polluting commits, but it **never** authorizes deleting them while the database is active or awaiting crash recovery.

### `.gitattributes`

```gitattributes
/index.db merge=binary filter=lfs diff=lfs -text

*.pdf filter=lfs diff=lfs merge=lfs -text
*.parquet filter=lfs diff=lfs merge=lfs -text
*.npz filter=lfs diff=lfs merge=lfs -text
*.npy filter=lfs diff=lfs merge=lfs -text
```

Exceptionally large scientific CSVs may be added to `.gitattributes` as needed, while bulk working tensors remain untracked in `scratch/` or `weights/` even when they share an extension (`.npz`, `.npy`) with small published arrays. Declaring [`merge=binary`](https://git-scm.com/docs/gitattributes#_performing_a_three_way_merge) on `/index.db` prevents Git from attempting a text merge on the LFS pointer file; if histories ever diverge, Git surfaces an explicit conflict rather than silently choosing one database pointer over another.

### Git Commits and Synchronization

To preserve a single, linear history for the execution registry, CLUSTER authors every `index.db` snapshot strictly on `main`, and LOCAL never stages or authors modifications to `index.db`. When adopting this specification, configure pre-receive or push checks to reject any CLUSTER registry commit outside `main` and any LOCAL commit that touches `index.db`. LOCAL pulls `origin/main` strictly by fast-forward (`git pull --ff-only`) when no local commits are pending, preparing its synthesis edits either on `main` or on short-lived branches (or an untracked external `git worktree`) that leave `index.db` untouched, rebasing those edits onto the latest `origin/main`, and fast-forwarding `main` prior to pushing.

Registry commit ancestry and pinned code versions (`code_commit`) must never be fractured or rewritten through cherry-picks, squashes, rebases of already-dispatched commits, or force-pushes. Every `code_commit` must be pushed to `origin/main` *before* the supervisor dispatches a job referencing it, ensuring code versions remain recoverable even if the supervisor checkout is lost. Because [Git rejects competing non-fast-forward pushes](https://git-scm.com/docs/git-push#_note_about_fast_forwards), CLUSTER Git synchronization routines must use an explicit fetch-and-reconcile path—rebasing only **unclaimed, undispatched** commits onto `origin/main` while preserving the latest verified CLUSTER `index.db` snapshot—rather than force-pushing or rewriting any commit already recorded in `index.db`. In particular, never invoke [`git merge --strategy=ours`](https://git-scm.com/docs/merge-strategies#Documentation/merge-strategies.txt-ours) (or `-s ours`) to reconcile a branch with `main`, as that strategy applies to the entire commit tree and silently discards incoming scientific files alongside the registry update. If a fast-forward is blocked by an accidental conflict on `index.db`, reconcile the scientific branch by explicitly restoring `/index.db` to the verified CLUSTER snapshot from `main` while preserving unrelated synthesis edits.

On CLUSTER, the supervisor must complete all transactions and close database connections (or generate a snapshot via [SQLite's online Backup API](https://www.sqlite.org/backup.html)) before staging `index.db`, ensuring a live, mutating database is never committed. While transient `PENDING` and `RUNNING` transitions remain local to CLUSTER's `index.db` (or may be optionally pushed alongside `code_commit` and fault-recovery notes), every terminal completion or cancellation commit bundles the validated `experiments/<experiment_id>/` files together with the corresponding `index.db` snapshot, and the saved experiment record is considered available to LOCAL only after both the Git commit and all referenced LFS objects have been fetched.

### Short-Lived LOCAL Queries

Because Git and Git LFS operations replace `index.db` on disk during repository updates, LOCAL must never hold open database connections across a pull or background LFS fetch. All LOCAL query helpers and repository synchronization tasks must coordinate through a single, untracked host-local reader-writer lock in OS temporary storage (such as `/tmp/` or `$XDG_RUNTIME_DIR`)—holding shared read access during queries and exclusive access during Git/LFS checkout replacements.

```python
import sqlite3
from contextlib import closing


def query_registry(query: str, params: tuple = ()) -> list:
    # Acquire shared read lock on the host-local reader-writer lock here
    with closing(sqlite3.connect("file:index.db?mode=ro", uri=True)) as conn:
        with closing(conn.execute(query, params)) as cursor:
            return cursor.fetchall()
```

Query functions must always return materialized data (`fetchall()`) rather than live connections or cursors. In Python's [`sqlite3`](https://docs.python.org/3/library/sqlite3.html#how-to-use-the-connection-context-manager) module, a connection context manager (`with conn:`) manages transactions but does not close the file handle; wrapping both the connection and cursor in [`contextlib.closing`](https://docs.python.org/3/library/contextlib.html#contextlib.closing) guarantees immediate closure on exit or exception. Opening the [SQLite URI](https://www.sqlite.org/uri.html) with `mode=ro` prevents accidental writes while preserving standard file locking. Never pass `immutable=1` on the URI, as the underlying file may be replaced by Git between queries.

---

## 6. Single-Table Execution Registry (`index.db`)

The registry contains a single table, `experiments`, dedicated exclusively to experiment identity, current execution lifecycle, and dispatch idempotency. It does not store numerical results, execution histories, or consolidation flags; no `attempts` or `consolidations` tables may be added.

### Concurrency and Placement

A single CLUSTER supervisor serializes all writes to `index.db`, `src/`, `tools/`, `cache/`, `weights/`, and `experiments/`; distributed workers never write to these paths or the database file directly. Because SQLite only serializes individual transactions and does not prevent multiple supervisor processes from coexisting, CLUSTER must enforce exclusive supervisor lifetime ownership across allocation renewals and recovery—using scheduler job dependencies (such as singleton or after-any chaining) together with a supported lifetime lock outside the tracked repository (in persistent cluster storage or OS runtime storage)—so an expiring supervisor and its continuation never overlap as writers or independently admit jobs against the same cluster capacity. Database transactions must be kept brief and must never remain open across file copies, digest verifications, Git operations, experiment execution, or scheduler waits.

By default, the supervisor writes root `index.db` directly on CLUSTER using rollback-journal mode (`DELETE`), conditional on confirming that the [network filesystem supports POSIX advisory locking](https://www.sqlite.org/useovernet.html) and synchronous `fsync` durability. Standard [SQLite `WAL` mode does not support multi-node access over network filesystems](https://www.sqlite.org/wal.html#noshm), and increasing `busy_timeout` does not overcome that limitation.

If the shared CLUSTER filesystem cannot reliably support direct rollback-journal locking, the supervisor should instead host the live database on its node-local disk (where `WAL` mode is permitted) and publish self-contained, rollback-mode snapshots to root `index.db` on CLUSTER using [SQLite's Backup API](https://www.sqlite.org/backup.html). In this host-local fallback, root `index.db` acts as a portable snapshot of the same logical registry rather than an independently edited database. The supervisor must durably publish each dispatch claim snapshot to CLUSTER *before* submitting the corresponding job to the scheduler, and it must never copy only the main database file of an active WAL database. If the supervisor node is replaced, the new supervisor restores the latest snapshot from CLUSTER and reconciles active scheduler jobs before retrying uncertain submissions.

### Schema

Every writer connection must apply the connection-level pragmas below (the host-local fallback alters only the live local database's `journal_mode`, while ensuring all published snapshots revert to `DELETE`):

```sql
PRAGMA journal_mode = DELETE;
PRAGMA synchronous = FULL;
PRAGMA busy_timeout = 60000;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS experiments (
    experiment_id         TEXT PRIMARY KEY NOT NULL,

    -- Frozen scientific definition
    spec_hash             TEXT UNIQUE NOT NULL,
    spec_json             TEXT NOT NULL,
    hypothesis_ref        TEXT,
    code_commit           TEXT NOT NULL,

    -- Current execution state
    status                TEXT NOT NULL DEFAULT 'PENDING'
                          CHECK (status IN (
                              'PENDING', 'RUNNING', 'COMPLETED', 'CANCELLED'
                          )),
    dispatch_id           TEXT UNIQUE,
    scheduler_ref         TEXT,
    command               TEXT,
    device_info           TEXT,

    -- UTC timestamps
    created_at            TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at            TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at            TEXT,
    completed_at          TEXT,

    -- Latest operational explanations
    last_execution_issue  TEXT,
    cancellation_reason   TEXT,

    CHECK (
        status != 'RUNNING'
        OR (dispatch_id IS NOT NULL AND command IS NOT NULL)
    ),
    CHECK (
        status != 'COMPLETED'
        OR completed_at IS NOT NULL
    ),
    CHECK (
        status != 'CANCELLED'
        OR cancellation_reason IS NOT NULL
    )
);

CREATE INDEX IF NOT EXISTS idx_experiments_status
ON experiments(status);

CREATE INDEX IF NOT EXISTS idx_experiments_hypothesis
ON experiments(hypothesis_ref);

CREATE TRIGGER IF NOT EXISTS trg_experiments_updated_at
AFTER UPDATE ON experiments
FOR EACH ROW
WHEN NEW.updated_at IS OLD.updated_at
BEGIN
    UPDATE experiments
    SET updated_at = CURRENT_TIMESTAMP
    WHERE experiment_id = NEW.experiment_id
      AND updated_at IS NOT CURRENT_TIMESTAMP;
END;
```

The [`trg_experiments_updated_at` trigger](https://www.sqlite.org/lang_createtrigger.html) automatically captures updates to any column without requiring a column whitelist. Its `WHEN` and `WHERE` clauses avoid redundant writes when a timestamp is already current and prevent same-second recursion even if recursive triggers are enabled. Because `CURRENT_TIMESTAMP` resolves to whole seconds, multiple updates within the same second share a timestamp; `updated_at` is an informational record, not a sequence number. Replacing an existing trigger definition requires an explicit migration (`DROP TRIGGER`), as `IF NOT EXISTS` will not overwrite an existing trigger.

### Field Semantics

Before registering an experiment, the supervisor reads the canonical synthesis documents and relevant experiment READMEs, validates and canonically serializes the configuration in code, freezes its scientific identity, and pins a recoverable Git commit. A hash without both a recoverable `spec_json` and `code_commit` is insufficient for reproducibility.

| Field | Meaning |
| :--- | :--- |
| `experiment_id` | Stable identifier matching the folder under `experiments/<experiment_id>/`. |
| `spec_json` | Frozen configuration JSON: parameters, seeds, input cache identities and preprocessing, compute budget, objective, hypothesis/forecast, endpoints, environment requirements, and checkpoint retention intentions. |
| `spec_hash` | SHA-256 of a deterministic serialization of `spec_json` and `code_commit`, excluding timestamps and temporary host-specific paths. |
| `hypothesis_ref` | Optional reference to the motivating scientific question in canonical LOCAL documentation. |
| `code_commit` | Recoverable Git commit identifying the code version of the source (`src/`, `tools/`) and environment definitions, pushed to `origin/main` prior to dispatch. Workers must execute this pinned code version rather than importing from an actively edited checkout or mutating environment. |
| `status` | Current lifecycle state (`PENDING`, `RUNNING`, `COMPLETED`, `CANCELLED`). |
| `dispatch_id` | Unique token for the current execution claim (such as a UUID); replaced on retry claims and used to reject stale worker callbacks. |
| `scheduler_ref` | Current batch job, allocation, or array identifier (multiple references may use a defined encoding within this field). |
| `command` | Exact invocation recorded before job submission. |
| `device_info` | Actual compute node, accelerator hardware, and software-driver versions captured at runtime. |
| `started_at` | UTC timestamp when active computation began, excluding scheduler queue waiting. |
| `completed_at` | UTC timestamp when required scientific outputs were verified and published on CLUSTER. |
| `last_execution_issue` | Brief description of the latest technical interruption; retained when a retry is claimed and replaced only by a subsequent fault or explicit correction. |
| `cancellation_reason` | Mandatory explanation of why the experiment was deliberately discontinued. |

---

## 7. Lifecycle, Dispatch, and Fault Recovery

### Lifecycle States

An experiment begins in `PENDING` (eligible for execution, either initially or following a recoverable technical fault), moves to `RUNNING` once claimed by the supervisor (including queue wait time), and finishes in `COMPLETED` once its required evidence is generated and validated, or `CANCELLED` if deliberately discontinued because it is no longer needed.

Crucially, `COMPLETED` reflects the successful collection of valid empirical evidence, regardless of whether that evidence supports the hypothesis. A null effect, poor model performance, disproved hypothesis, or prespecified measurement of divergence or training collapse is a `COMPLETED` scientific outcome. Agents must never retry adverse scientific findings as if they were technical faults. Similarly, high-level goal changes originate on LOCAL, and already-running experiments retain their frozen specifications unless explicitly cancelled.

### Atomic Claim and Budget Enforcement

The supervisor enforces the project-wide compute budget and storage admission across all concurrent experiments and accounts. Database claims do not replace scheduler reservations or quota checks: before claiming an experiment, the supervisor must inspect live scheduler state as well as filesystem block and inode quotas, active reservations, expected write volumes, and headroom for atomic checkpoint promotion rather than relying on raw free space alone, and must confirm that `code_commit` is already present in `origin/main`.

To claim a `PENDING` experiment, the supervisor executes an immediate transaction:

```sql
BEGIN IMMEDIATE;

UPDATE experiments
SET status = 'RUNNING',
    dispatch_id = :dispatch_id,
    command = :command,
    scheduler_ref = NULL,
    device_info = NULL,
    started_at = NULL,
    completed_at = NULL,
    cancellation_reason = NULL
WHERE experiment_id = :experiment_id
  AND status = 'PENDING';

COMMIT;
```

The supervisor submits the job to the cluster scheduler only if the update affected exactly one row (`changes() == 1`). Notice that `last_execution_issue` is intentionally preserved so claiming a retry does not erase the prior fault record. While `spec_hash` prevents duplicate registration and the conditional update prevents concurrent claims, the supervisor must persist the claim before submitting the external batch job and bind `dispatch_id` into the scheduler's identifying metadata. If job submission succeeds but the acknowledgement is lost, the supervisor reconciles `dispatch_id` against the live scheduler before resubmitting. All subsequent execution-driven updates—including filesystem staging and final output saving—must match `(experiment_id, dispatch_id, status = 'RUNNING')` so an orphaned worker or stale handler from an older attempt can never overwrite published files or corrupt a newer dispatch.

### Fault Recovery and Cleanup

A stale `updated_at` timestamp never proves by itself that an execution has died. Before returning an experiment from `RUNNING` to `PENDING`, the supervisor must execute the following recovery sequence:

1. Confirm via the batch scheduler or process table that all jobs and processes associated with the active `dispatch_id` have terminated, or stop them under the assigned authority.
2. Check whether verified output saving already finished prior to the interruption and can simply be reconciled and marked `COMPLETED`.
3. Record a brief technical diagnostic in `last_execution_issue`, while documenting any substantive scientific consequences (such as altered timing, data missingness, or changed resource costs) in `experiments/<experiment_id>/README.md` or the numerical result files. Recoveries must never silently reset wall-clock time or compute budgets to fabricate an uninterrupted endpoint.
4. Clean disposable working files under `scratch/<experiment_id>/<dispatch_id>/` and any uncommitted temporary artifacts, while strictly preserving the frozen specification, `README.md`, and any committed evidence under `experiments/<experiment_id>/`.
5. Release the claim by resetting `status = 'PENDING'`, `dispatch_id = NULL`, and `scheduler_ref = NULL`, ensuring the next execution receives a fresh `dispatch_id` and a pristine `scratch/` workspace.

Never automatically delete a tracked `experiments/<experiment_id>/` directory, as it may contain preregistered forecasts, preparation notes, or valid observations. Automatic pruning is restricted to disposable `scratch/` workspaces and superseded recovery checkpoints with no unresolved dependencies—never accepted scientific evidence or SQLite recovery sidecars.

---

## 8. Scientific Output Saving and Checkpoint Promotion

During execution, workers write all intermediate outputs and working state to isolated directories under `scratch/<experiment_id>/<dispatch_id>/`. Once computation finishes, the supervisor serializes final output saving and completion against cancellation and redispatch, revalidating `(experiment_id, dispatch_id, status = 'RUNNING')` before promoting checkpoints or overwriting canonical result files:

1. Confirm that `(experiment_id, dispatch_id, status = 'RUNNING')` remains the active claim in `index.db`, then finish and close the source checkpoint in `scratch/`, ensuring its contents are immutable before copying.
2. Copy the checkpoint to a dispatch-scoped temporary file (incorporating `dispatch_id` in the temporary filename) inside persistent CLUSTER storage under `weights/<experiment_id>/`. Because promoting a file from `scratch/` to `weights/` typically crosses filesystems, it is not an atomic rename; full copying is the portable default, and hard links may be used only when both directories reside on the same filesystem and the source is permanently immutable. Retained paths in `weights/` must never symlink back into temporary storage.
3. Verify the destination temporary file's byte count and SHA-256 digest against the completed source. The mere existence of a temporary file is never proof of a complete copy, and a format-specific load check may supplement—but never replace—cryptographic payload verification. A truncated temporary copy must never be renamed to the final checkpoint name or consumed by a downstream experiment.
4. Revalidate `(experiment_id, dispatch_id, status = 'RUNNING')` immediately before final promotion, flush and synchronize (`fsync`) the verified destination payload, atomically rename the dispatch-scoped temporary file to its canonical filename within `weights/<experiment_id>/`, and synchronize the `weights/<experiment_id>/` directory entry. Once a checkpoint becomes a scientific dependency, it is exempt from automatic pruning until its dependency and retention decisions are resolved.
5. Stage the validated compact result files and updated `README.md` (referencing the promoted checkpoint path and SHA-256 digest) under `experiments/<experiment_id>/` using dispatch-scoped temporary filenames, revalidate that `dispatch_id` is still active, and atomically rename them to their canonical filenames.
6. Commit a short registry transaction updating the matching `(experiment_id, dispatch_id, status = 'RUNNING')` row to `status = 'COMPLETED'` and recording `completed_at`.
7. Close the database (or export a consistent Backup API snapshot) and publish `experiments/<experiment_id>/` and `index.db` together to `main` via Git and Git LFS.

Verified output saving (Steps 1–5) and the SQLite completion transaction (Step 6) must be serialized by the single active supervisor against cancellation and redispatch, preceding Git/LFS synchronization (Step 7). If verified output saving finishes for the active `dispatch_id` but the database update is interrupted, the supervisor reconciles and finalizes the database state using the existing validated outputs; if the database update completes but Git/LFS push is interrupted, the supervisor finishes the Git push rather than rerunning the computation.

---

## Record of Deviations

See preamble.

- 13 October 2026: Human-approved consolidation of the specification into `AGENTS.md`, with additional agent instructions at the bottom. File references and the root allowlist were updated; operational rules and the database schema are unchanged.

---

## References

- [Git attributes and binary merge behavior (`gitattributes(5)`)](https://git-scm.com/docs/gitattributes#_performing_a_three_way_merge)
- [Git merge strategies and `--strategy=ours` hazards (`git-merge(1)`)](https://git-scm.com/docs/merge-strategies#Documentation/merge-strategies.txt-ours)
- [Git push fast-forward rules and non-fast-forward rejection (`git-push(1)`)](https://git-scm.com/docs/git-push#_note_about_fast_forwards)
- [Git LFS tracking and object lifecycle (`git-lfs(1)`)](https://git-lfs.com/)
- [SQLite Write-Ahead Logging (WAL) network filesystem restrictions](https://www.sqlite.org/wal.html#noshm)
- [SQLite over network filesystems and advisory locking requirements](https://www.sqlite.org/useovernet.html)
- [SQLite Online Backup API](https://www.sqlite.org/backup.html)
- [SQLite Uniform Resource Identifier (URI) access modes (`mode=ro` vs. `immutable=1`)](https://www.sqlite.org/uri.html)
- [SQLite `CREATE TRIGGER` semantics](https://www.sqlite.org/lang_createtrigger.html)
- [Python `sqlite3` transaction context managers](https://docs.python.org/3/library/sqlite3.html#how-to-use-the-connection-context-manager) vs. [`contextlib.closing`](https://docs.python.org/3/library/contextlib.html#contextlib.closing)

---

## Additional agent instructions

Keep this repository small and retain one authoritative location for each fact.

- LOCAL owns the root scientific documents, literature and manuscript. CLUSTER owns `src/`, `tools/`, experiment records and the registry. One agent may perform either logical role, but must respect ownership while doing so.
- Use `git config scientific.role LOCAL` for this checkout. Set `CLUSTER` only on the supervisor checkout or while explicitly performing authorized supervisor work. Registry changes belong to CLUSTER on `main`.
- Use `python3 tools/repository.py setup --role LOCAL` after cloning to install Git LFS settings and ownership hooks. Repository-local settings and hooks are not transferred by Git.
- Keep reusable code in `src/` and utility scripts in `tools/`. Keep experiment code out of `experiments/`. Do not create empty experiment directories, fictional results or extra metadata files.
- Root scientific files are blank starting points. Populate them only from actual research. Changes to `MOTIVATION.md` require human authorization.
- Preserve null and adverse results. Technical interruptions return an unchanged experiment to `PENDING`; changed code or scientific specifications require a new experiment identity.
- LOCAL reads `index.db` through `src.registry.query_registry`. Synchronize repository replacement through `tools/repository.py sync` so queries cannot overlap replacement.
- Before completion, the supervisor must validate actual outputs, verify/promote required checkpoints, and serialize final filesystem writes with the dispatch check. `complete()` records that decision; it does not perform experiment-specific validation or scheduler reconciliation.
- Do not add attempts or consolidation tables, status documents, authorization receipts or per-poll snapshots. Do not amend the specification without the user's explicit approval and its required deviation record.
- No project goal, cluster endpoint or compute budget is configured in this blank scaffold. It does not authorize jobs or remote changes.
