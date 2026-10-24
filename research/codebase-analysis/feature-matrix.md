# Feature Matrix: What Works, What's WIP, What's Missing

## Core Features

| Feature | Status | Notes |
|---------|--------|-------|
| Project Discovery | DONE | Smart exclusion, monorepo-aware, max-depth |
| Filesystem Watching | DONE | watchdog-based, zero polling, noise filters |
| Genome Detection | DONE | Stack, tests, CI, docs, docker, git |
| Stage Inference | DONE | R&D/Development/Deployed/Dormant + confidence decay |
| Context Assembly | DONE | JSON payload + prompt rendering |
| Status Reporting | DONE | Tier 0 deterministic + Tier 1 LangGraph |
| Completion Scoring | DONE | DoD assertions or heuristic fallback |
| Kanban Tasks | DONE | todo/in_progress/review/done/discarded |
| Autopilot | DONE | Propose-only, approve/discard, revert on discard |
| Self-Improvement | DONE | Daily execution, other-work-first priority |
| REST API | DONE | FastAPI, routes for all major domains |
| Web UI | DONE | Single-file SPA, serves on / |
| TUI | DONE | Rich-based terminal UI |
| WIP Triage | DONE | Review diff, run tests, commit, discard |
| Project Classification | DONE | github/library/local-git/local |

## Gaps vs PRD

| PRD Feature | Status | Gap |
|-------------|--------|-----|
| Trello Sync | NOT STARTED | Mentioned but no integration |
| Multi-user Auth | NOT STARTED | Single-user local-first |
| Cloud Sync | NOT STARTED | No remote backend |
| Plugin System | NOT STARTED | Monolithic, no extension API |
| Mobile Client | NOT STARTED | Web-only |
| Advanced Analytics | NOT STARTED | Basic health counts only |
| CI Integration | MINIMAL | Detects CI presence, no direct integration |

## What It Cannot Do
- Run across multiple machines without manual sync
- Share context between team members
- Act as a SaaS product out of the box
- Replace project management tools like Linear/Jira
- Guarantee safe agent runs on untrusted code (shell=True risk)
