# Scientific repository

Follow [SPECIFICATION.md](SPECIFICATION.md). Keep this repository small and retain one authoritative location for each fact.

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
