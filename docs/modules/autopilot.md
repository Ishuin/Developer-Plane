# autopilot

Automated development on a completion-priority basis (`dcp/cortex/autopilot.py`, `dcp/cortex/completion.py`, `dcp/agents/executor.py`).

## Completion scoring

`CompletionEngine.evaluate(path)`:
- **dod.yaml** in the project root wins (source `dod`, confidence 1.0):
  ```yaml
  assertions:
    - name: tests pass
      type: command          # exit 0 = pass, 120s timeout
      run: python -m pytest -q
    - name: has CI
      type: file_exists
      path: .github/workflows
    - name: todos closed
      type: max_todos        # TODO/FIXME/XXX count across source
      limit: 5
  ```
  percent = passed / total.
- Otherwise a genome heuristic (source `heuristic`, confidence 0.5): git 20, tests 25, CI 20, docs 15, docker 10, clean tree 10.

## Priority queue

`automation_enabled` projects ordered by completion **descending** (finish nearly-done work first), red-health tiebreak. Enable per project via UI checkbox or `POST /api/autopilot/enable`.

## Agent runs (propose-only)

`AutopilotManager.start(limit)` walks the queue **sequentially** (agent runs are heavy). Per project:
1. Guards: skip if working tree dirty (protects WIP) or a pending run awaits verdict.
2. Brief = context prompt ([[cortex]]) + DoD gaps + next steps from the latest status report + hard rules (never commit/push, stay in directory).
3. Executor runs `Settings.agent_cmd` (default Claude Code headless: `claude -p "$(cat {brief_file})" --permission-mode acceptEdits`) with `DCP_AGENT_TIMEOUT` (900s). Template swaps in any CLI (`DCP_AGENT_CMD`).
4. Before/after `git status --porcelain` delta → diff stat + changed-file list; stored in `agent_runs`.
5. `AgentRunProposed` decision logged. **Nothing is committed.**

Verdicts: `POST /api/autopilot/runs/{id}/approve` (keep changes, you commit) or `/discard` (tracked files checked out, run-created untracked files deleted — exactly the files the run touched).

## Endpoints

| Method | Path |
| --- | --- |
| POST | `/api/completion/evaluate?path=` · `/api/completion/evaluate_all` |
| GET | `/api/autopilot/queue` · `/status` · `/runs` |
| POST | `/api/autopilot/enable` · `/start` · `/runs/{id}/approve` · `/runs/{id}/discard` |

UI: Autopilot tab — Score All, Run Top N with live progress, queue with completion bars, runs list with expandable reports and Approve/Discard.

Related: [[cortex]], [[agents]], [[api]]
