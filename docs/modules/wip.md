# wip (triage)

Uncommitted changes used to dead-end autopilot (the WIP guard skips
dirty repos to protect your work). WIP triage resolves them from the
dashboard — no editor detour (`dcp/agents/gitops.py`, `dcp/api/routes/wip.py`).

## Flow

1. Autopilot reports `skipped — uncommitted changes` → open the project's
   detail panel → **Review WIP**.
2. Panel shows: branch, dirty file list, full diff, detected test command.
3. **Run tests** — executes the project's own tests (dod.yaml `tests`
   assertion > pytest > npm test > cargo/go) against the uncommitted state.
4. **Commit → PR** — commits everything to a fresh `dcp/wip-<timestamp>`
   branch, pushes to origin, and opens the GitHub compare/PR page for
   manual merge. Non-GitHub remotes: branch is pushed, PR is manual.
   No remote: local branch commit only.
5. **Discard all changes** — double-confirmed full revert.

After commit or discard the tree is clean, completion is re-scored
automatically, and the project becomes eligible for autopilot runs.

## Endpoints

| Method | Path |
| --- | --- |
| GET | `/api/wip?path=` — branch, files, remote, test command |
| GET | `/api/wip/diff?path=` — capped diff incl. untracked names |
| POST | `/api/wip/test` — run detected/custom test command |
| POST | `/api/wip/commit` — branch + commit + optional push, returns `pr_url` for GitHub |
| POST | `/api/wip/discard` — full revert (`confirm: true` required) |

Related: [[autopilot]], [[completion]]
