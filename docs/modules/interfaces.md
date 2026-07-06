# interfaces

Thin clients only — no core logic, no direct filesystem/database access.

## Web (`dcp/interfaces/web/index.html`)

Single static page, zero build step, zero external assets. Five tabs keep clutter categorized: **Projects · Signals · Inferences · Decisions · Agents**. The project list is paginated (25/page) and scrollable, with search + type filter; clicking a row loads genome + stage detail inline. Light/dark via `prefers-color-scheme`.

## TUI (`dcp/interfaces/tui/app.py`)

Rich-based paginated project table with stage + confidence per project. Run:

```
python -c "import sys; sys.path.insert(0,'src'); from dcp.interfaces.tui import run_tui; run_tui('.')"
```

Related: [[api]]
