# database

`EventSourcingDB` (repository pattern) over SQLite in `dcp/database/repository.py`.

## Tables

- `raw_signals`, `inferences`, `decisions` — append-only Data Trinity logs
- `projects` — a *projection* derived from `ProjectDiscovered` signals so listings stay O(page) without replaying the log

## Guarantees

- Thread-safe (single connection + lock; FastAPI threadpool safe)
- Inference writes validate `0.0 <= confidence <= 1.0` at the model layer
- Every list method paginates via `limit/offset` and has a matching `count_*`

Related: [[core]], [[cortex]]
