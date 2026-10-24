# Implementation vs PRD/README Claims

## Verdict
The codebase largely matches the README/PRD. Most advertised features are actually implemented, not just stubbed.

## Confirmed Implemented
- Project discovery with smart exclusion lists
- OS-level filesystem watching via watchdog
- Event-sourced SQLite backend with 4 tables + migrations
- Three-layer Data Trinity: raw_signals, inferences, decisions
- Project genome detection
- Stage inference with confidence decay
- Context assembler with prompt rendering
- FastAPI REST API with routers
- Single-file web UI
- Terminal UI
- Status reporting agent (Tier 0 deterministic + Tier 1 LangGraph)
- Completion scoring via dod.yaml or heuristics
- Kanban task management
- Autopilot with propose-only safety model
- Self-improvement pipeline
- Project classification (github/library/local-git/local)

## Partial / Optional
- LangGraph AI tier: present but gated behind env vars and optional deps
- Web UI: minimal single-file SPA, functional but basic
- Trello sync: mentioned in PRD but not implemented

## Not Implemented
- Multi-user authentication
- Remote sync / cloud backup
- Plugin system
- Advanced analytics dashboard
- Mobile client

## Architecture Assessment
Single-process modular monolith with internal event bus. Clean separation:
- `sentry/` - data collection
- `cortex/` - inference and orchestration
- `agents/` - execution
- `api/` - thin REST layer
- `interfaces/` - UI clients
- `database/` - persistence

Thread safety via threading.Lock around SQLite. Subprocess timeouts throughout.
