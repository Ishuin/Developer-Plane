# api

FastAPI app factory (`create_app`) with lifespan-managed state (`deps.build_state`). Routes are thin; all logic lives in [[sentry]] / [[cortex]].

## Endpoints

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/api/health` | version + status |
| GET | `/api/projects` | paginated: `page`, `page_size`, `search`, `type` |
| GET | `/api/projects/types` | distinct stacks for filter dropdown |
| POST | `/api/projects/scan?path=` | run discovery |
| GET | `/api/projects/genome?path=` | project genome |
| GET | `/api/projects/stage?path=` | inferred stage + confidence + evidence |
| GET | `/api/projects/context?path=&as_prompt=` | agent payload or rendered prompt |
| GET | `/api/signals` `/api/inferences` `/api/decisions` | paginated Data Trinity |
| GET | `/api/agents` | registered agents |
| POST | `/api/agents/run` | `{agent, path}` → AgentResult |
| GET/POST | `/api/watcher` `/start` `/stop` | Sentry watcher control |
| GET | `/` | web UI |

Every list response is a `Page[T]`: `{items, page, page_size, total}`.

Related: [[interfaces]]
