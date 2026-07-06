# cortex

The analytical brain.

- `inference.py` — `StageInferenceEngine.infer_stage(path)`: scores deterministic evidence (git, tests, CI, docker, manifests) into stages **R&D / Development / Deployed**, then applies exponential confidence decay (`half-life = DCP_HALF_LIFE_DAYS`, default 14). Idle > 2 half-lives flips the stage to **Dormant**. Every result is logged as an inference with its confidence.
- `context.py` — `ContextAssembler.assemble(path)`: packages genome + stage + recent signals/inferences into an agent payload; `to_prompt()` renders it as compact markdown for prompt injection.
- `router.py` — `AgentRouter`: registry + dispatch. If a Tier 1 agent raises `AgentUnavailable`, the router falls back to a Tier 0 agent and records the run as a decision. AI is never a blocking dependency.

Related: [[sentry]], [[agents]], [[database]]
