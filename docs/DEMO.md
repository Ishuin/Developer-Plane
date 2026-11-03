# Demo script (about 3 minutes)

## Start and stop

```bash
python src/main.py --demo --reset-demo   # fresh sample data (first start takes ~30s: it analyzes with your LLM key)
python src/main.py --demo                # reuse the existing demo data
```

Open http://127.0.0.1:8787. The header shows `agent: native · DEMO`.

`--demo` only changes this process: it uses its own database and sample projects in
`~/.dcp/demo` and the built-in agent. Your real database, scan root and `.env` are not
modified. **To go back to normal, restart without `--demo`.**

Needs an API key saved in the Settings tab (or in `.env`) for the AI summaries and the native agent.

## Walkthrough

1. **Projects tab**: seven sample projects with health, completion, and stage (Deployed, Development,
   R&D, Dormant). Point out `legacy-blog` (Dormant) and `ml-experiments` (R&D).
2. Click `todo-cli`: genome, stage evidence, status report, and the Kanban card.
3. **Agents tab**: run `advisor` on `todo-cli` for an AI summary, risks, and next steps.
4. **Board tab**: one focused card each for `todo-cli` and `text-utils`.
5. **Autopilot tab**: both projects are armed. Click start. Each run takes about 30 seconds.
6. Review each proposal's diff:
   - `todo-cli`: one-line fix in `todo.py`. **Approve** (change is kept, nothing is committed).
   - `text-utils`: new `slugify`. **Discard** (files are reverted).
7. **Settings tab**: show the LLM provider (Anthropic or OpenAI-compatible), the key (never shown),
   **Test connection**, and the agent-mode switch (native or CLI).

## Reset between demos

Stop the server, then `python src/main.py --demo --reset-demo`.
