"""Executor that picks the CLI or native agent per run from live settings."""

from dcp.agents.executor import CodeAgentExecutor, ExecutionOutcome
from dcp.agents.native_executor import NativeAgentExecutor
from dcp.config import Settings

MODE_CLI = "cli"
MODE_NATIVE = "native"
AGENT_MODES = (MODE_CLI, MODE_NATIVE)


class ModeSwitchingExecutor:
    """Delegates to the executor matching settings.agent_mode at call time."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._cli = CodeAgentExecutor(settings)
        self._native = NativeAgentExecutor(settings)

    def execute(self, project_path: str, brief: str) -> ExecutionOutcome:
        executor = self._native if self.settings.agent_mode == MODE_NATIVE else self._cli
        return executor.execute(project_path, brief)
