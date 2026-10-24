# Social Posts

## Hacker News
**Title**: Show HN: Developer Control Plane – local-first context fabric for AI coding agents

**Body**:
I built a local-first system that watches your projects, remembers context between sessions, and safely runs headless coding agents with approve/discard control.

What it does:
- Discovers projects across any folder
- Watches filesystem changes via OS hooks
- Infers project stage with confidence scores
- Assembles context prompts for Claude Code / Codex / Kimi
- Runs agents propose-only; discard reverts automatically
- Self-improvement pipeline fixes its own bottlenecks

Stack: Python, FastAPI, SQLite, watchdog. 122 tests, offline-first.

Why I built it: I was losing context between agent sessions and had no visibility into which of my 30+ projects were actually active.

Would love feedback from anyone running multiple AI coding agents.

GitHub: https://github.com/<your-username>/developer_plane

## Reddit r/selfhosted
**Title**: I built a local-first dashboard for managing multiple AI coding agent projects

**Body**:
Developer Control Plane is a self-hosted tool that gives you persistent memory and orchestration for AI coding agents like Claude Code, Codex CLI, and Kimi.

Key features:
- Event-sourced local database
- Filesystem watching without polling
- Project health dashboard
- Propose-only agent runs with automatic revert
- Kanban board per project

No cloud, no account, no telemetry by default.

Demo video: [link]
GitHub: https://github.com/<your-username>/developer_plane

## Twitter/X Thread
1/ I built a local-first "brain" for my AI coding agents. It remembers project context, safely runs headless agents, and shows me which repos actually need work.

2/ The problem: I use Claude Code across 30+ projects. Every session starts from zero. No memory. No visibility. No safety net if the agent breaks something.

3/ The solution: Developer Control Plane. It watches my filesystem, builds a project genome, infers stage with confidence scores, and assembles context prompts automatically.

4/ The killer feature: propose-only agents. Changes stay uncommitted until I approve. If I discard, files revert automatically. No more fearing what an agent might break.

5/ Everything runs locally. SQLite event store. FastAPI backend. Single-file web UI. 122 tests. Works on Windows, Mac, Linux.

6/ It's open source and free. AGPL-3.0. If you're juggling multiple AI coding agents, this might save you hours of context-switching per week.

7/ GitHub: https://github.com/<your-username>/developer_plane
Demo: [link]
Docs: [link]

## Dev.to Article Outline
**Title**: I built a local-first context fabric for AI coding agents

**Outline**:
1. The context-switch tax is real
2. Why current agents are amnesic
3. The three-layer architecture: signals → inferences → decisions
4. How propose-only safety works
5. Self-improving control plane
6. Results after 2 weeks of use
7. How to try it
8. What's next: team sync and cloud backup
