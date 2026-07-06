# tasks

Kanban task board (`dcp/cortex/tasks.py`) — Jira/Trello-style cards per project, moved automatically by agents.

## Lifecycle

```
todo ──agent picks up──▶ in_progress ──run finishes──▶ review
review ──run approved──▶ done
review ──run discarded─▶ todo          (work reverted, card returns)
any    ──user discard──▶ discarded     (emergency override, terminal)
```

- **Seeding**: status analysis ([[analysis]]) creates `todo` cards from its recommendations; open titles are deduped. Libraries never get cards (see [[classify|sentry]]).
- **Agent movement**: an autopilot run picks the project's open `todo` cards as its work list, moves them `in_progress` with the run id, then `review` when the run finishes. The run verdict finishes the job: approve → `done`, discard → back to `todo`.
- **User override**: `POST /api/tasks/{id}/discard` (or the ✕ on the Board tab) permanently removes a card — agents never pick discarded cards. Manual `POST /api/tasks/{id}/move?status=` also exists.

## Endpoints

| Method | Path |
| --- | --- |
| GET | `/api/tasks/board?project=&pipeline=project\|self` |
| POST | `/api/tasks/{id}/discard` · `/api/tasks/{id}/move?status=` |
| POST | `/api/tasks/classify_all` (re-classify all projects' kind) |

UI: **Board** tab — project picker, pipeline picker, four columns, discard on each card, self-improvement panel on top.

Related: [[autopilot]], [[analysis]], [[self-improvement]]
