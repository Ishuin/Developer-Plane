# I built a local-first context fabric for AI coding agents

If you use Claude Code, Codex CLI, or Kimi CLI across multiple projects, you already know the problem: every session starts from zero. Context is lost. It’s hard to see which repos are active, which are dead, and where an agent should actually work.

I built **Developer Control Plane** to fix that.

## The context-switch tax is real

I juggle 30+ projects. Some are in R&D, some are half-built, some are production-ready. Switching between them means rebuilding mental context every time. Current AI coding agents make this worse: they’re amnesic between sessions. They forget architectural decisions, dependencies, and recent work.

## Why current agents are amnesic

Claude Code, Codex CLI, and similar tools are stateless. Each run is a fresh conversation. They don’t remember:
- Which project you were working on yesterday
- What the last commit was
- Whether tests pass
- What stage the project is in

You have to re-explain everything every time.

## The three-layer architecture: signals → inferences → decisions

Developer Control Plane solves this with an event-sourced architecture built on three immutable layers:

1. **Raw Signals (Facts)**: Deterministic data such as git commits, file modifications, test coverage presence, and open task counts.
2. **Inferences (Probabilities)**: AI or heuristic-driven guesses about the project, such as assigning it a "Development" stage or calculating completion probability. Every inference includes a confidence score.
3. **Decisions (Actions)**: System triggers, such as orchestrating an AI agent, suggesting refactors, or marking a project as dormant.

This keeps the system honest. Instead of fake certainty, you get calibrated confidence that decays as a project sits idle.

## How propose-only safety works

The biggest risk with AI coding agents is uncontrolled changes. Developer Control Plane uses a **propose-only model**:

1. Agent runs are proposed, not auto-committed
2. Changes stay uncommitted in your working tree
3. You review the diff stat in the dashboard
4. You **approve** to keep changes, or **discard** to revert
5. Discard automatically reverts the exact files the run touched

This means you never have to fear what an agent might break. Every change is reviewable and reversible.

## Self-improving control plane

Here’s the part I’m most excited about: **bottlenecks observed while agents work become tasks for the control plane itself**.

If an agent run fails, times out, or hits a guard skip, Developer Control Plane records it as a self-improvement task. A background loop executes at most one self-improvement task per day, and only when no other project’s work is pending.

The control plane fixes its own bottlenecks.

## Results after 2 weeks of use

- **Context recovery**: I can resume any project in seconds, not minutes
- **Visibility**: The dashboard shows me which projects actually need work
- **Safety**: Zero “agent broke something and I didn’t notice” incidents
- **Time savings**: Probably 5+ hours per week on context-switching

## How to try it

```bash
git clone https://github.com/Ishuin/Developer-Plane.git
cd Developer-Plane
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python src/main.py --scan D:\Projects
python src/main.py --host 127.0.0.1 --port 8787
# Open http://127.0.0.1:8787
```

Or with Docker:
```bash
docker build -t developer-plane .
docker run -p 8787:8787 -v %cd%:/app developer-plane
```

## What’s next

- Team sync and multi-user support
- Cloud backup for context fabric
- Plugin system for custom agents
- Advanced analytics and reporting

If you’re juggling multiple AI coding agents, this might save you hours of context-switching per week.

GitHub: https://github.com/Ishuin/Developer-Plane  
License: AGPL-3.0
