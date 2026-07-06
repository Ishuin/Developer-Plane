# core

Shared primitives. No dependencies on other dcp modules.

- `dcp/core/models.py` — pydantic domain models: `Project`, `Signal`, `Inference`, `Decision`, `Genome`, `StageResult`, and the generic `Page[T]` pagination envelope used by every list endpoint.
- `dcp/core/bus.py` — `EventBus`, a thread-safe in-process observer. Subscribe with `bus.subscribe("FileChanged", handler)` or `"*"` for everything. A failing handler is logged, never fatal.

Related: [[database]], [[sentry]]
