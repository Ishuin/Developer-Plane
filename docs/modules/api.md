# api

FastAPI app factory (`create_app`) with lifespan-managed state (`deps.build_state`). Routes are thin; all logic lives in [[sentry]] / [[cortex]].

## Endpoints

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/api/health` | version + status |
| GET | `/api/projects` | paginated: `page`, `page_size`, `search`, `type`, `health`, `sort` |
| DELETE | `/api/projects` | clear the projection (event log kept) |
| GET | `/api/projects/health_counts` | red/yellow/green/unanalyzed buckets |
| GET | `/api/projects/types` | distinct stacks for filter dropdown |
| POST | `/api/projects/scan?path=&wait=` | run discovery |
| GET | `/api/projects/scan/status` | live scan progress |
| GET | `/api/projects/genome?path=` | project genome |
| GET | `/api/projects/stage?path=` | inferred stage + confidence + evidence |
| GET | `/api/projects/context?path=&as_prompt=` | agent payload or rendered prompt |
| GET | `/api/signals` `/api/inferences` `/api/decisions` | paginated Data Trinity |
| GET | `/api/agents` | registered agents |
| POST | `/api/agents/run` | `{agent, path}` → AgentResult |
| GET/POST | `/api/watcher` `/start` `/stop` | Sentry watcher control |
| POST | `/api/analysis/start` `/project` | batch / single status analysis |
| GET | `/api/analysis/status` `/report?path=` | progress + `project_status.md` |
| GET | `/api/wip` `/diff?path=` | branch, dirty files, capped diff |
| POST | `/api/wip/test` `/commit` `/discard` | WIP triage actions (see [[wip]]) |
| GET | `/api/autopilot/queue` `/status` `/runs` | queue, batch progress, run history |
| POST | `/api/autopilot/start` `/enable` `/runs/{id}/approve\|discard` | propose-only batch + verdicts |
| POST | `/api/completion/evaluate` `/evaluate_all` | score a project (dod.yaml or heuristic) |
| GET | `/api/tasks/board` | kanban columns |
| POST | `/api/tasks/{id}/move` `/discard` | card lifecycle |
| POST | `/api/tasks/classify_all` | re-classify every project kind |
| GET/POST | `/api/self/status` `/check` | self-improvement pipeline |
| GET | `/` | web UI |

Every list response is a `Page[T]`: `{items, page, page_size, total}`.

Related: [[interfaces]]
