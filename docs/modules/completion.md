# completion (Code-Driven Definition of Done)

`dcp/cortex/completion.py` — scores every project 0–100% and writes it back
to the projection (`completion_percent`, `completion_source`).

## dod.yaml

A project can declare its own Definition of Done instead of relying on
heuristics. File sits at the project root:

```yaml
assertions:
  - name: tests pass
    type: command          # command | file_exists | max_todos
    run: python -m pytest -q
  - name: pyproject present
    type: file_exists
    path: pyproject.toml
  - name: few TODOs
    type: max_todos
    limit: 10
```

- `command` runs with `shell=True` in the project dir, 120s timeout —
  **only score projects you trust** (a malicious `dod.yaml` executes code).
- Percent = passed / total assertions. Source is recorded as `dod`.

## Heuristic fallback

No (or malformed) `dod.yaml` → deterministic genome weights: tests, CI,
docs, Dockerfile, TODO/FIXME density. Source recorded as `heuristic`
(inference confidence 0.5 vs 1.0 for dod).

## Consumers

- Autopilot queue order (closest-to-done first) — see [[autopilot]]
- WIP triage test command detection — see [[wip]]
- Web UI "Score All" (`/api/completion/evaluate_all`)

Related: [[cortex]], [[sentry]]
