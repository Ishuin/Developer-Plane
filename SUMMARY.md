# Developer Control Plane — Project Summary

_Assessed 2026-11-03 from code, docs, tests, and a live run of the server. Updated the same day after adding the LLM Settings feature (section 8) the native development agent (section 9), and demo mode (section 11)._

## 1. What it is

A local-first "Context Fabric": a single-process Python modular monolith that sits between the filesystem and AI coding agents. It discovers projects, records facts in an append-only SQLite event log, infers stage and completion with confidence scores, and launches headless agents in propose-only mode (changes stay uncommitted until approved; discard reverts them).

Stack: Python 3.10+, FastAPI/uvicorn, SQLite, watchdog, Rich, PyYAML. Optional LangGraph advisor for Tier 1 AI. Dual-licensed AGPL-3.0 and commercial.

## 2. Current state (verified)

| Check | Result |
| --- | --- |
| Test suite | **149 passed** in about 2 minutes (full run, after all changes) |
| Server launch | `python src/main.py --host 127.0.0.1 --port 8787` starts; `/` returns 200; `/api/projects` returns paginated data |
| Live data | 249 projects discovered, 18 of the first 25 analyzed |
| Size | about 4.3k lines of Python in `src/`, 943-line single-file web UI, 63-line TUI |
| Docs | `README`, `PRD`, `docs/architecture.md`, 13 per-module docs, `CHANGELOG`, demo GIF and MP4 |
| History | 32 commits, v0.1.0 tagged in the changelog (2026-10-22) |

## 3. Done vs. project direction (PRD)

| PRD item | Status | Notes |
| --- | --- | --- |
| Sentry: discovery of git and non-git repos, monorepos, smart exclusions | Done | `sentry/discovery.py`, `classify.py` |
| Sentry: OS-level filesystem watcher, no polling, noise filters | Done | `sentry/watcher.py`, watchdog |
| Sentry: project genome (stack, tests, CI, docs, Docker, git) | Done | `genome.py`, `detectors.py` |
| Append-only SQLite event log | Done | `database/repository.py` |
| Internal event bus | Done | `core/bus.py` |
| Cortex: stage inference with confidence decay | Done | Heuristic, with a configurable half-life. The PRD says "Bayesian"; the implementation is a decay-weighted heuristic. |
| Cortex: context assembler and prompt rendering | Done | `cortex/context.py` |
| Cortex: agent router, headless agent execution | Done | `agents/executor.py`, `router.py`, `DCP_AGENT_CMD` |
| Code-driven Definition of Done | Done | `dod.yaml` assertions with heuristic fallback |
| FastAPI REST layer | Done | projects, analysis, tasks, agents, autopilot, wip, watcher, trinity routes |
| Web UI | Done | Single `index.html` served by the API |
| Terminal UI | Minimal | 63 lines in `interfaces/tui/app.py`. The PRD says "built first"; it is the thinnest part. |
| Hard limits on active work (WIP) | Done | `api/routes/wip.py` |
| Status reports (`project_status.md`) | Done | Tier 0 deterministic |
| Kanban tasks | Done | `cortex/tasks.py` |
| Autopilot, propose-only with revert | Done | `cortex/autopilot.py` |
| Self-improvement pipeline | Done | Works, but see the stale item in section 5 |
| AI-optional Tier 1 advisor | **Done, verified live** | Works with Anthropic and OpenAI-compatible providers. Configured from the new Settings tab or `.env`. A real Claude call succeeded (`Test connection` returned "OK"). |
| **Trello / external task sync (offline queue)** | **Not started** | No code references Trello. This is one of the four PRD feature rows. |
| **Embedded terminal multiplexing in the TUI** | **Not started** | TUI is a viewer, not an agent launcher. |
| Success metrics (fewer active projects, more shipped code) | Not measurable yet | No metrics or telemetry on dormant-project surfacing or shipped output. |

Rough PRD coverage: about 75–80% of the spec. The core engine is complete. The gaps are the Trello sync and the TUI orchestration experience.

## 4. Quality assessment

**Strengths**
- Architecture matches the stated principles. Layers are cleanly separated (`sentry`, `cortex`, `core`, `database`, `api`, `interfaces`) and there is one process.
- 122 passing tests across every domain, including autopilot, DoD, watcher, and the API.
- The safety design (propose-only, revert on discard, WIP limits, no agents on third-party libraries) is a real differentiator.
- Documentation is unusually thorough for a v0.1: a PRD, an architecture doc, and per-module docs.
- Honest uncertainty (confidence scores, decay) is built in rather than bolted on.
- Offline by default. It needs no API key to be useful.
- Licensing and launch assets (GIF, MP4, README badges) are already in place.

**Weaknesses**
- The API has no authentication. This is documented as a known limit and mitigated by binding to localhost. The new Settings endpoints can read and change LLM config, so this now matters more.
- `shell=True` is used for `dod.yaml` and test commands. It is documented, but it is an injection surface for untrusted repos.
- The TUI is very thin (63 lines), and the web UI is one 943-line HTML file with no build step or component structure.
- The test suite is slow (about 112s for 122 tests), which hurts iteration.
- Only a minority of discovered projects have been analyzed (18 of 25 on page one). Analysis seems to be on-demand, not automatic.
- `/api/trinity` and `/api/autopilot` return 404 at the bare path. The routes need a sub-path, so API discoverability is poor without reading `/docs`.
- `project_status.md` in the repo is stale (dated 2026-07-06) and still says "Add CI". `.github/` has only issue templates, so there is no CI workflow, even though the README shows a "tests passing" badge.
- Repo hygiene: `context_fabric.db` (3.5 MB) sits in the working tree. It is gitignored and not tracked, but it holds the author's real local project paths, so check that nothing leaks in demos. `LICENSE.gpl3.bak` and `self_improvement.md` are untracked.
- `self_improvement.md` contains a captured agent failure ("OAuth session expired") with a raw stderr dump. The bottleneck capture is noisy and not very actionable.

## 5. Demo readiness

**Verdict: demo-ready for a guided, local walkthrough (about 7/10). Not ready for a "download and try it" public demo or for a skeptical technical audience.**

What works today for a demo:
1. Start the server, open `http://127.0.0.1:8787`, and show the dashboard of discovered projects with stage, health, and completion percent.
2. Show a project's genome, status report, and Kanban cards.
3. Run an agent through autopilot and show the propose, approve or discard flow.
4. Show the pre-made `brag.gif` and `brag.mp4` as a fallback.

What will hurt a live demo:
- The default scan finds 249 projects, including temp folders such as `...\opencode\dcp_demo\demo-app`. The dashboard will look cluttered and may expose private project names.
- Autopilot depends on a working headless `claude` CLI login (your subscription, not the API key). The stored failure shows this breaks when the login expires, which is a risk on stage.
- Cold start: the first scan and analysis of a large tree is slow, and the first view can show un-analyzed projects with `null` status.
- The TUI cannot carry a demo on its own.

## 6. What to add to be demo-ready

**Must have (about 1–2 days)**
1. **Seeded demo mode**: a `--demo` flag or a `DCP_DB_PATH` pointing at a curated database with 5–6 fake, clean projects in varied stages (R&D, Development, Deployed, Dormant). This removes the clutter, the privacy risk, and the cold-start slowness.
2. **Offline-safe autopilot demo**: a mock or scripted agent command (`DCP_AGENT_CMD`) that makes a deterministic edit, so the propose, approve, discard flow never depends on network or login.
3. **Auto-analyze on scan** (or a one-click "Analyze all" in the UI), so no project shows empty status.
4. **A scripted 3-minute demo path** in `docs/` (commands and expected screens).
5. **Refresh stale artifacts**: regenerate `project_status.md`, clean the stale self-improvement entry, and delete the `.bak` file.
6. **Add a CI workflow** (GitHub Actions running pytest) so the "122 passing" badge is backed by a real pipeline. Mark slow tests to speed it up.

**Revised priority (after discussion):** Developer Plane has no coding agent of its own. Autopilot only orchestrates an external CLI (`DCP_AGENT_CMD`, default `claude -p`). To be self-contained, the order is: (1) a native development agent that uses the API key, with read-file, write-file and run-tests tools, plugged into the existing propose-only approve/discard flow; (2) seeded demo data; (3) auto-analyze on scan; (4) a scripted 3-minute demo path. An MCP server was considered and is deferred: it would expose context to Claude Code, which is useful later, but it does not make the demo self-contained.

**Should have (about 3–5 days)**
7. **Trello (or a simpler GitHub Issues) sync** with an offline queue. It is the biggest PRD gap, but a read-only import is enough for a demo.
8. **A better TUI**: a project list, a detail view, and "launch agent with context" actions. This delivers the PRD's "TUI first" promise.
9. **Active-project and dormancy view** in the web UI, with a visible WIP limit. This shows the success metric (surfacing dead projects) visually.
10. **Optional API token** for non-localhost binds, and a safer command runner (no `shell=True`, or an allowlist).
11. **Tier 1 AI advisor demo**: one end-to-end example with a real model, so the "AI-optional" claim is demonstrated rather than only stated.

**Nice to have**
12. Split `index.html` into modules or a small framework, and add UI tests.
13. Metrics page: projects surfaced as dormant, agent runs approved and discarded, and time-to-context.
14. Packaging: publish to PyPI (`pyproject.toml` already defines a `dcp` entry point) and ship a Docker quick start (a `Dockerfile` exists).

## 7. Bottom line

The engine is solid and well tested, and it follows its own architecture rules. It is a credible v0.1. The gaps are product polish and two PRD features (Trello sync and a rich TUI). With a seeded demo dataset, an offline-safe agent, and auto-analysis, it can give a convincing demo within a day or two. A public "try it yourself" release needs CI, API auth, and safer command execution.

## 8. Update: LLM Settings feature (added 2026-11-03)

**Added**
- **Provider-agnostic LLM client** (`src/dcp/llm.py`): `anthropic` (via `langchain-anthropic`) and `openai` (via `langchain-openai`, with `DCP_LLM_API_BASE` for any OpenAI-compatible host). Both the advisor and the status agent use it, replacing duplicated OpenAI-only code.
- **Settings tab in the web UI**: provider, model, key, base URL, enable toggle, **Save** and **Test connection**. Changes apply without a restart and are written to `.env`.
- **Settings API**: `GET/PUT /api/settings/llm` and `POST /api/settings/llm/test`. The key is never returned; only a saved flag and its last four characters.
- **`.env` support** (`src/dcp/envfile.py`), `.env.example`, `langchain-anthropic` in `requirements-ai.txt`, README config table updated.
- **12 new tests** in `tests/test_llm_settings.py`.

**Security review findings, both fixed**
- Credential exfiltration: changing the provider or base URL now requires re-entering the API key, so a saved key cannot be redirected to another host in one request.
- `.env` newline injection: newline, carriage return and NUL are rejected in all LLM fields and in the `.env` writer; the loader reads only `DCP_`-prefixed keys.
- Not done, by choice: a hostname allowlist or private-address blocking for the base URL (it would block local proxies), and authentication on the API.

**Other fixes**
- The tab bar now wraps, and `/` is served with `Cache-Control: no-store`, after the Settings tab appeared missing in the browser.

**Verified**
- With a real Anthropic key, **Test connection** returned `{"ok": true, "reply": "OK"}`. The first attempt failed with `401 invalid x-api-key`, which was a wrong key, fixed by re-entering it.
- The Tier 1 advisor and AI status analysis are now usable. They were not before.

**Housekeeping still open**
- `litellm_config.yaml` and `llm_connection_testing_curl.txt` hold local credentials. They are untracked and now gitignored.
- The new files are now committed and merged (see section 12).

**Updated demo-readiness verdict:** about 7.5/10 (was 7/10). The AI tier now works and is configurable from the UI. The remaining gaps are unchanged: no native development agent, no seeded demo data, no auto-analyze, no CI, no scripted demo path.

## 9. Update: native development agent (added 2026-11-03)

**Finding:** Developer Plane had no coding agent of its own. Autopilot only orchestrated an external CLI (`DCP_AGENT_CMD`, default `claude -p`), which needs a separate login and failed once on an expired session.

**Added** (`src/dcp/agents/native_executor.py`, `DCP_AGENT_MODE=native`)
- A built-in agent that uses the configured LLM key (Anthropic or OpenAI-compatible) in a tool loop: list files, read file, write file, run tests.
- Same contract as the CLI executor, so it plugs into the existing propose-only flow: it never commits, and the git delta feeds approve and discard. Autopilot and the self-improvement pipeline both use it in `native` mode. Default mode is still `cli`.
- 7 tests with a scripted fake model (no network).

**Verified live:** on a throwaway repo with a deliberate bug, Claude read the files, fixed `add` (`a - b` to `a + b`), ran pytest, and reported 1 passed. Only `calc.py` appeared as a change. This was run through the executor directly, not through the Autopilot tab.

**Security review (HIGH) found and fixed:** the first version let the model run allowlisted free-form commands, which reached `python -c` and inherited API keys.
- Now it calls `run_tests` with a runner name (pytest, npm, cargo, go, dotnet, mvn, gradle), each mapped to a fixed command. No model-supplied arguments.
- Child processes get a minimal environment: no `DCP_*` or provider keys.
- File access is confined to the project folder; `.git` is blocked; 25-step limit.
- Known remaining risk: the agent can write a file such as `conftest.py` and run pytest, which executes it. Only container-level isolation closes that. Use native mode on trusted projects and review each diff.

**Updated demo-readiness verdict:** about 8/10 (was 7.5/10). The product now runs end to end on its own with one API key. What is left is demo polish, not capability (see section 10).

## 10. What remains before this can be marked complete

**A. Demo-ready (blocking a good demo)**
1. **Seeded demo data**: a `--demo` mode with 5–6 clean fake projects across stages (R&D, Development, Deployed, Dormant), so the dashboard is not cluttered with 249 real folders and no private paths are shown.
2. **Auto-analyze on scan**, so no project shows an empty status or score.
3. **Native mode in the UI**: a toggle in Settings (today it is an env var and needs a restart), plus a visible indicator of which agent mode is active.
4. **Autopilot run through the UI verified end to end** in native mode: enable, start, review the diff, approve, discard. Only the executor was tested live.
5. **Scripted 3-minute demo path** in `docs/`: scan, analyze, advisor, board, autopilot edit, approve.

**B. Release-ready (blocking a public release)**
6. **CI workflow** (GitHub Actions running pytest), so the README badge is backed by a pipeline. The suite takes about 2 minutes; mark slow tests.
7. **API authentication** or a token for non-localhost use. Settings endpoints can now read and change LLM config.
8. **Container or sandbox isolation for the native agent**, to close the `conftest.py` risk.
9. **Housekeeping**: new files committed and the README test badge updated (done, section 12); still open: refresh the stale `project_status.md` and clear the stale self-improvement entry (both are now gitignored local files).

**C. PRD gaps (blocking "complete" against the spec)**
10. **Trello or external task sync with an offline queue** (not started).
11. **Rich terminal UI** that launches agents with injected context (today it is a 63-line viewer).
12. **Success-metrics view**: dormant projects surfaced, runs approved and discarded, so the PRD's 60-day goals can be measured.
13. **Bayesian confidence**: the PRD says Bayesian; the implementation is a decay-weighted heuristic. Either implement it or amend the PRD.

**Optional:** an MCP server exposing context and tasks to Claude Code (deferred); splitting the single-file web UI.

**Suggested definition of done**
- *Demo complete* = items 1–5.
- *v1.0 release* = demo complete plus items 6–9.
- *PRD complete* = all of the above plus 10–13.

## 11. Update: demo mode (added 2026-11-03)

Items 1–5 of section 10-A are done.

| # | Item | Status |
| --- | --- | --- |
| 1 | Seeded demo data | Done. `python src/main.py --demo [--reset-demo]` builds 7 real git repos in `~/.dcp/demo` (Deployed x2, Development x3, R&D, Dormant) with its own database. |
| 2 | Auto-analyze on scan | Done, opt-in: `DCP_AUTO_ANALYZE=1` (on in demo). Off by default because analysis writes `project_status.md` into every scanned project. |
| 3 | Native mode in the UI | Done. Settings tab has an agent-mode switch (native or cli) that applies live; the header shows `agent: native · DEMO`. |
| 4 | Autopilot end to end | Done and verified live against Claude: start, review diff, approve (change kept) and discard (files reverted). |
| 5 | Scripted demo path | Done: `docs/DEMO.md`. |

**Switching back:** `--demo` changes only that process (its own database, scan root, native agent). Run `python src/main.py` without the flag and you are back to the normal setup. The `.env` file is untouched, and the agent-mode switch is not saved to `.env` while in demo.

**Bugs found and fixed while testing for real**
- Claude returns typed content blocks; the status analysis and the advisor crashed on them. Now handled everywhere through one helper.
- A tool call with a missing argument aborted the whole native-agent run; it is now returned to the model as an error it can correct.
- Scanning a project reset its idle clock, so dormant projects could never show as Dormant. Discovery signals are now ignored for activity.
- The demo reset left broken repos on Windows because git object files are read-only; now removed correctly.

**New tests:** 8 (demo workspace, reset, agent-mode API, scan callback, unanalyzed-only analysis, dormant stays dormant).

**Updated verdict: about 9/10 for a guided demo.** Remaining before a public release (section 10-B and C): CI workflow, API authentication, container isolation for the native agent, CSRF and Host-header checks on the Settings routes, Trello sync, a richer TUI, a metrics view.

## 12. Update: released to `main` (2026-11-03)

Everything above is merged to `main` through three squash-merged pull requests:

| PR | Content |
| --- | --- |
| #1 | LLM Settings UI, native development agent, demo mode, bug fixes, tests, docs |
| #2 | Native agent sandbox denies `.env` and `.env.*` (read, write, listing); `.env.example` allowed |
| #3 | The `.env` deny list is case-insensitive (`.ENV` is the same file on Windows and macOS) |

**Repository state:** `.gitignore` cleaned up (secrets, generated files, backups ignored; `.env.example` committed as the template). The README badge and changelog are updated. Tests: 149 passing at the last full run; the two follow-up fixes were checked with the native-agent tests only.

**Security review log** (automated reviews on each change)
- Settings API: key re-entry required when the provider or base URL changes; control characters rejected; `.env` loader reads `DCP_` keys only. Fixed.
- Native agent commands: free-form commands replaced by named test runners; child processes get a scrubbed environment. Fixed.
- Native agent files: `.env` files blocked, case-insensitively. Fixed.
- **Open, by design:** the native agent can run test code it writes itself, and that code could read files in the project folder. Only container isolation closes this. Until then, use native mode on trusted projects and review every diff.
- **Open:** the Settings routes have no CSRF or Host-header check (the API has no authentication). Plan: add both together with API authentication.

**Remaining work, in order**
1. Container isolation for the native agent.
2. API authentication, with CSRF and Host checks on the Settings routes.
3. CI workflow (the test run takes about two minutes).
4. Trello or external task sync with an offline queue.
5. Richer terminal UI.
6. Success-metrics view.
7. Bayesian confidence, or amend the PRD.
