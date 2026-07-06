# Developer Control Plane

A local-first, event-sourced **Context Fabric**: persistent memory and nervous system between your filesystem and your AI agents. Discovers your projects, infers their lifecycle stage with honest confidence scores, and assembles context payloads for AI agents — offline by default.

## Quick start

```bash
pip install -r requirements.txt
python src/main.py                 # API + web UI at http://127.0.0.1:8787
python src/main.py --scan D:\Projects   # one-shot discovery, no server
python -m pytest tests -q          # run the test suite
```

## What it does

- **Discovers projects** across any root (paginated, searchable, filterable by stack)
- **Watches the filesystem** via OS hooks (watchdog) and logs every change as a signal
- **Infers project stage** — R&D / Development / Deployed / Dormant — from deterministic evidence, with confidence that decays as a project sits idle
- **Assembles agent context** — genome + stage + recent activity as JSON or a ready-to-inject prompt
- **Runs agents** — Tier 0 `health-check` works fully offline; Tier 1 `advisor` (LangGraph) activates when you provide LLM credentials, and gracefully falls back when you don't
- **Classifies every project** — `github` (yours), `library` (third-party — agents never modify these), `local-git`, `local`; set your accounts via `DCP_GITHUB_USERS`
- **Autopilot (propose-only)** — ranks automation-enabled projects by completion (dod.yaml assertions or genome heuristic) and runs headless coding agents on the top of the queue; every run is a reviewable proposal you approve or discard
- **Kanban board** — per-project task cards seeded from analysis; agents move them (todo → in progress → review → done) as runs execute and verdicts land; users can emergency-discard any card
- **Self-improvement pipeline** — bottlenecks hit while agents work on your projects become tasks for the control plane itself (mirrored in `self_improvement.md`); at most one is executed per day, and only when no other project's work is open

## Layout

```
src/dcp/
  core/        models + event bus
  database/    SQLite event store (Data Trinity)
  sentry/      discovery, watcher, genome
  cortex/      inference, context assembly, agent routing
  agents/      tier 0 heuristic + tier 1 LangGraph
  api/         FastAPI routes (thin)
  interfaces/  web UI + TUI (thin clients)
docs/          architecture + one note per module (Obsidian-friendly)
tests/         pytest suite
```

Start reading at `docs/architecture.md`.

## AI tier (optional)

```bash
pip install -r requirements-ai.txt
set DCP_AI_ENABLED=1
set DCP_LLM_API_KEY=your-key
set DCP_LLM_MODEL=claude-qwen3-coder
set DCP_LLM_API_BASE=http://localhost:4000   # e.g. local litellm proxy
```

Everything else works without any of this.
