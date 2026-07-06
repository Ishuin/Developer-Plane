# self-improvement

Dedicated pipeline for improving the Developer Control Plane itself (`dcp/cortex/self_improvement.py`).

## Where tasks come from

Bottlenecks observed while agents work on *other* projects become `self`-pipeline tasks automatically:
- agent run failures / timeouts (`AgentRunFailure` exit codes)
- guard skips and analysis errors

Each bottleneck logs a `BottleneckObserved` signal and is mirrored into **`self_improvement.md`** at the repo root — a human-readable, committed backlog grouped by status.

## Daily cadence, strict priority

A background scheduler (started with the API, hourly check) enforces:
1. **At most ONE self-improvement execution per day** (tracked via `SelfImprovementExecuted` decisions).
2. **Other projects come first** — if any other project has pending runs or open project-pipeline tasks, self work is deferred.
3. Execution is propose-only via the same executor as [[autopilot]]: the agent works in the control plane's repo, never commits; the result lands in the runs list for approve/discard.

## Endpoints

| Method | Path |
| --- | --- |
| GET | `/api/self/status` — open tasks, last/next execution, blocking state |
| GET | `/api/self/tasks` — the self board |
| POST | `/api/self/check` — run the daily check immediately |

UI: banner panel on the **Board** tab shows open count, last execution, next eligibility, and a "Run daily check now" button.

Related: [[tasks]], [[autopilot]]
