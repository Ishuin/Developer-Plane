# interfaces

Thin clients only — no core logic, no direct filesystem/database access.

## Web (`dcp/interfaces/web/index.html`)

Single static page, zero build step, zero external assets. Seven tabs keep clutter categorized: **Projects · Signals · Inferences · Decisions · Agents · Autopilot · Board**. The project list is paginated (25/page) and scrollable, with search + type filter; clicking a row loads genome + stage detail inline, plus the WIP triage panel. Light/dark via `prefers-color-scheme`.

Polling loops (scan, analysis, autopilot) are guarded: a failed poll retries briefly, then reports the error instead of leaving a stuck spinner. Every fire-and-forget fetch routes through a `bg()` helper so rejections surface in the status line.

## TUI (`dcp/interfaces/tui/app.py`)

Rich-based paginated project table with stage + confidence per project. Run either:

```
python src/main.py --tui
```

or directly (self-bootstrapping `sys.path`):

```
python src/dcp/interfaces/tui/app.py
```

Both read the same settings/database as the server. The TUI is read-only — mutations happen through the API.

Related: [[api]]
