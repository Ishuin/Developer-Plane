# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- Settings tab: LLM provider (Anthropic or OpenAI-compatible), API key, connection test, and agent-mode switch; `.env` support
- Native development agent (`DCP_AGENT_MODE=native`) with sandboxed file tools and fixed test runners; no external CLI needed
- Demo mode (`--demo`, `--reset-demo`) with isolated database and sample projects; `docs/DEMO.md`
- Opt-in auto-analyze after scans (`DCP_AUTO_ANALYZE=1`)
- 27 new tests (149 total)

### Fixed
- Claude content-block replies crashed status analysis and the advisor
- Scanning a project no longer resets its idle clock, so dormant projects stay Dormant

## [0.1.0] - 2026-10-22

### Added
- Project discovery with smart exclusions and monorepo handling
- Filesystem watching via watchdog with noise filters
- Project genome detection for stack, tests, CI, docs, Docker, and git
- Stage inference with confidence decay
- Context assembly and prompt rendering for agents
- FastAPI REST API and single-file web UI
- Terminal UI via Rich
- Status reporting with Tier 0 deterministic analysis
- Completion scoring via `dod.yaml` or heuristic fallback
- Kanban task management
- Autopilot with propose-only safety and revert on discard
- Self-improvement pipeline
- 122 passing tests

### Notes
Initial public-ready state for open-core launch.
