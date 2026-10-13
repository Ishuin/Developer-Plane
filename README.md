# Developer Control Plane

A local-first, event-sourced **Context Fabric**: persistent memory and nervous system between your filesystem and your AI agents. Discovers your projects, infers their lifecycle stage with honest confidence scores, and assembles context payloads for AI agents — offline by default.

Built as a single-process modular monolith (no microservices, near-zero idle CPU) around three immutable layers — **Raw Signals → Inferences (with confidence) → Decisions**.

## Quick start

```bash
pip install -r requirements.txt
python src/main.py                 # API + web UI at http://127.0.0.1:8787
python src/main.py --scan D:\Projects   # one-shot discovery, no server
python -m pytest tests -q          # run the test suite (114 tests)
```

Optional terminal UI:

```bash
python -c "import sys; sys.path.insert(0,'src'); from dcp.interfaces.tui import run_tui; run_tui('.')"
```

The server binds to `127.0.0.1` by default — that is the security boundary (the API is unauthenticated by design). Only pass `--host 0.0.0.0` behind your own reverse proxy / firewall.

## What it does

- **Discovers projects** across any root (paginated, searchable, filterable by stack) — monorepo-aware, one project per git child
- **Watches the filesystem** via OS hooks (watchdog, no polling) and logs every change as a signal
- **Infers project stage** — R&D / Development / Deployed / Dormant — from deterministic evidence, with confidence that decays exponentially as a project sits idle
- **Assembles agent context** — genome + stage + recent activity as JSON or a ready-to-inject prompt
- **Runs agents** — Tier 0 `health-check` works fully offline; Tier 1 `advisor` (LangGraph) activates when you provide LLM credentials, and gracefully falls back when you don't
- **Classifies every project** — `github` (yours), `library` (third-party — agents never modify these), `local-git`, `local`; set your accounts via `DCP_GITHUB_USERS`
- **WIP triage** — review the diff, run the detected test command, commit to a fresh branch, or discard changes for any project with uncommitted work, straight from the dashboard; tests run inside the project's own virtualenv (`venv/`, `env/`, …) when one is found, and client-supplied commands are rejected (no shell injection)
- **Autopilot (propose-only)** — ranks automation-enabled projects by completion and runs headless coding agents on the top of the queue; every run is a reviewable proposal you approve or discard (with automatic file revert on discard)
- **Kanban board** — per-project task cards seeded from analysis; agents move them (todo → in progress → review → done) as runs execute and verdicts land; users can emergency-discard any card
- **Self-improvement pipeline** — bottlenecks hit while agents work on your projects become tasks for the control plane itself (mirrored in `self_improvement.md`); at most one is executed per day, and only when no other project's work is open

## Code-Driven Definition of Done

Drop a `dod.yaml` into any project to score it with explicit, testable assertions instead of heuristics:

```yaml
assertions:
  - name: tests pass
    type: command
    run: python -m pytest -q
  - name: pyproject present
    type: file_exists
    path: pyproject.toml
  - name: few TODOs
    type: max_todos
    limit: 10
```

`command` assertions run with a 120s timeout when you hit **Score All**. No `dod.yaml`? Completion falls back to genome heuristics (tests, CI, docs, markers).

## Architecture

```
┌───────────────────────────────────────────────────────────────┐
│                        Interfaces                            │
│        Web UI        │        TUI        │   FastAPI REST     │
└──────────────┬───────────────┬────────────────┬───────────────┘
               │               │                │
┌──────────────▼───────────────▼────────────────▼───────────────┐
│                          Cortex                              │
│     Inference     │   Context Assembly   │    Agent Router    │
└──────────────┬───────────────┬────────────────┬───────────────┘
               │               │                │
┌──────────────▼───────────────▼────────────────▼───────────────┐
│                          Sentry                              │
│      Discovery      │   Filesystem Watcher   │  Genome Builder│
└──────────────┬───────────────┬────────────────┬───────────────┘
               │               │                │
┌──────────────▼───────────────▼────────────────▼───────────────┐
│                       Data Trinity                            │
│              SQLite Event Store   +   File System             │
└───────────────────────────────────────────────────────────────┘
```

## Layout

```text
src/
  main.py      CLI + server entry point (--host/--port/--scan)
  dcp/
    core/        models + event bus
    database/    SQLite event store (Data Trinity)
    sentry/      discovery, watcher, scanner, genome, detectors, classify
    cortex/      inference, context assembly, routing, completion,
                 analysis, autopilot, tasks, self-improvement
    agents/      tier 0 heuristic, tier 1 LangGraph, executor, gitops
    api/         FastAPI routes (thin)
    interfaces/  web UI (single-file SPA) + TUI (thin clients)
docs/          architecture + one note per module (Obsidian-friendly)
tests/         pytest suite (114 tests, no network required)
```

Start reading at `docs/architecture.md`.

## Configuration

All configuration is environment-driven (defaults in `src/dcp/config.py`):

| Variable | Default | Purpose |
|---|---|---|
| `DCP_DB_PATH` | `context_fabric.db` | SQLite event store location |
| `DCP_WATCH_ROOTS` | *(unset)* | Comma-separated dirs the watcher starts on |
| `DCP_GITHUB_USERS` | `Ishuin` | Your GitHub logins, for `github` classification |
| `DCP_HALF_LIFE_DAYS` | `14` | Confidence decay half-life (days) |
| `DCP_AGENT_CMD` | `claude -p --permission-mode acceptEdits` | Headless coding agent used by Autopilot |
| `DCP_AGENT_TIMEOUT` | `900` | Per-agent run timeout (seconds) |

## AI tier (optional)

```bash
pip install -r requirements-ai.txt
set DCP_AI_ENABLED=1
set DCP_LLM_API_KEY=your-key
set DCP_LLM_MODEL=claude-qwen3-coder
set DCP_LLM_API_BASE=http://localhost:4000   # e.g. local litellm proxy
```

Everything else works without any of this — Tier 0 heuristics never call a network.

## Security notes

- The API has no authentication; keep it on `127.0.0.1`.
- Autopilot only runs on projects you explicitly enable, never on `library` classification.
- `dod.yaml` commands and test commands from scanned repos are executed with `shell=True` — only score projects you trust.

## License

[Apache-2.0](LICENSE)
