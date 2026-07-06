# Architecture

The Developer Control Plane is an event-driven modular monolith. One process, strictly separated domains, communicating through an internal event bus.

## The Data Trinity

Everything flows through three immutable layers (see [[database]]):

1. **Raw Signals (facts)** — file events, git commits, discovery results
2. **Inferences (probabilities)** — stage guesses, always with a confidence score
3. **Decisions (actions)** — agent runs, refactor suggestions

## Modules

| Module | Doc | Responsibility |
| --- | --- | --- |
| `dcp.core` | [[core]] | Domain models, event bus |
| `dcp.database` | [[database]] | SQLite event store + projects projection |
| `dcp.sentry` | [[sentry]] | Filesystem watching, discovery, genome |
| `dcp.cortex` | [[cortex]] | Stage inference, context assembly, agent routing |
| `dcp.agents` | [[agents]] | Tier 0 heuristics + Tier 1 LangGraph |
| `dcp.api` | [[api]] | FastAPI REST layer (thin) |
| `dcp.interfaces` | [[interfaces]] | Web UI + TUI (thin clients) |

## Dependency direction

```
interfaces ──▶ api ──▶ cortex ──▶ agents
                 │        │
                 ▼        ▼
               sentry ─▶ database ◀─ core
```

Interfaces never touch the filesystem or database directly; they only consume the API. All modules may use `core`.

## Principles

- **Local-first, offline-capable** — SQLite, no cloud dependency
- **AI-optional** — Tier 0 heuristics always work; Tier 1 (LangGraph) is opt-in via `DCP_AI_ENABLED=1`
- **Reactive** — near-zero idle CPU; the watcher uses OS hooks, not polling
- **No microservices** — single process, modular packages
