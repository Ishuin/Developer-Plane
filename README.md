# Developer Control Plane

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-AGPL--3.0-green)
![Tests](https://img.shields.io/badge/tests-122%20passing-brightgreen)

**The local-first nervous system for your AI coding agents.**

Developer Control Plane watches your projects, remembers context between sessions, safely runs headless agents with approve/discard control, and gives you a real-time health dashboard of all your codebases — offline by default.

## Why this exists

If you use Claude Code, Codex CLI, or Kimi CLI across multiple projects, you already know the problem: every session starts from zero. Context is lost. It’s hard to see which repos are active, which are dead, and where an agent should actually work.

This project fixes that with three ideas:

- **Event-sourced memory**: every file change, git commit, and agent run is recorded locally.
- **Confidence-calibrated inference**: project stage and completion are expressed with honest uncertainty, not fake certainty.
- **Propose-only agents**: changes are left uncommitted until you approve; discard reverts automatically.

## Demo

<img src="https://raw.githubusercontent.com/Ishuin/Developer-Plane/main/src/dcp/interfaces/web/brag.gif" alt="Developer Control Plane demo" style="width:100%; max-width:900px; border-radius:8px; border:1px solid #ddd;">

Click the GIF to view the full video.

## Quick start

```bash
git clone https://github.com/<your-username>/developer_plane.git
cd developer_plane
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Scan a folder and exit
python src/main.py --scan D:\\Projects

# Start the API + web UI
python src/main.py --host 127.0.0.1 --port 8787
# Open http://127.0.0.1:8787
```

## What you get

- **Discovery** — finds git and non-git projects, ignores system folders, handles monorepos
- **Filesystem watcher** — OS-level hooks, zero polling, noise filters
- **Project genome** — detects stack, tests, CI, docs, Docker, git state
- **Stage inference** — R&D / Development / Deployed / Dormant with confidence decay
- **Context assembler** — packages project state into a compact prompt for agents
- **Status reports** — writes `project_status.md` into each project
- **Completion scoring** — explicit `dod.yaml` assertions, or deterministic heuristic fallback
- **Kanban board** — per-project cards seeded from analysis; agents move them as work executes
- **Autopilot** — runs coding agents across completion-priority projects; every run is a reviewable proposal
- **Self-improvement** — bottlenecks observed while agents work become tasks for the control plane itself

## Configuration

All behavior is driven by environment variables with safe defaults.

| Variable | Default | Purpose |
| --- | --- | --- |
| `DCP_DB_PATH` | `~/.dcp/context_fabric.db` | SQLite event store location |
| `DCP_SCAN_ROOT` | `.` | Default scan path |
| `DCP_WATCH_ROOTS` | *(unset)* | Comma-separated dirs to watch on startup |
| `DCP_GITHUB_USERS` | `Ishuin` | Your GitHub accounts for `github` classification |
| `DCP_HALF_LIFE_DAYS` | `14` | Confidence decay half-life |
| `DCP_AGENT_CMD` | `claude -p --permission-mode acceptEdits` | Headless coding agent command |
| `DCP_AI_ENABLED` | `0` | Enable Tier 1 LangGraph advisor |
| `DCP_LLM_API_KEY` | *(unset)* | LLM key when AI is enabled |
| `DCP_LLM_MODEL` | *(unset)* | Model name when AI is enabled |

## Security notes

- The API has no authentication; keep it on `127.0.0.1`.
- Autopilot never runs on third-party libraries.
- `dod.yaml` commands and test commands run with `shell=True`; only score projects you trust.

## Development

```bash
python -m pytest tests -q
```

## License

AGPL-3.0. See `LICENSE`.
