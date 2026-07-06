# agents

Agent implementations behind a single ABC (`base.py`: `Agent`, `AgentResult`, `AgentUnavailable`).

## Tiers

- **Tier 0 — `health-check`** (`heuristic.py`): deterministic project health report. Always available, fully offline. Recommends git init, tests, CI, docs, committing entropy.
- **Tier 1 — `advisor`** (`langgraph_agent.py`): LangGraph three-node pipeline *summarize → assess risks → recommend* over any OpenAI-compatible endpoint (works with the local litellm proxy). All langchain/langgraph imports are lazy; missing deps or credentials raise `AgentUnavailable` and the [[cortex]] router falls back to Tier 0.

## Enabling Tier 1

```
pip install -r requirements-ai.txt
set DCP_AI_ENABLED=1
set DCP_LLM_API_KEY=...
set DCP_LLM_MODEL=...            # e.g. claude-qwen3-coder via litellm
set DCP_LLM_API_BASE=http://localhost:4000   # optional
```

Related: [[cortex]]
