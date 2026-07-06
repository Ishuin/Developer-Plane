"""Shared application state and dependency wiring."""

from dataclasses import dataclass
from pathlib import Path

from dcp.agents import HealthCheckAgent, LangGraphAdvisorAgent
from dcp.agents.executor import CodeAgentExecutor
from dcp.agents.status_agent import StatusReportAgent
from dcp.config import Settings
from dcp.cortex import (
    AgentRouter,
    AnalysisManager,
    AutopilotManager,
    CompletionEngine,
    ContextAssembler,
    SelfImprovementManager,
    StageInferenceEngine,
    TaskService,
)
from dcp.database import EventSourcingDB
from dcp.sentry import ProjectDiscovery, ScanManager, SentryWatcher


@dataclass
class AppState:
    settings: Settings
    db: EventSourcingDB
    discovery: ProjectDiscovery
    scanner: ScanManager
    watcher: SentryWatcher
    inference: StageInferenceEngine
    assembler: ContextAssembler
    router: AgentRouter
    analysis: AnalysisManager
    completion: CompletionEngine
    autopilot: AutopilotManager
    tasks: TaskService
    self_improvement: SelfImprovementManager


def build_state(settings: Settings) -> AppState:
    db = EventSourcingDB(settings.db_path)
    router = AgentRouter(db)
    router.register(HealthCheckAgent())
    router.register(LangGraphAdvisorAgent(settings))
    status_agent = StatusReportAgent(settings)
    router.register(status_agent)
    owned_users = [u.strip() for u in settings.github_users.split(",") if u.strip()]
    discovery = ProjectDiscovery(db, owned_users=owned_users)
    inference = StageInferenceEngine(db, settings.confidence_half_life_days)
    assembler = ContextAssembler(db)
    completion = CompletionEngine(db)
    tasks = TaskService(db)
    executor = CodeAgentExecutor(settings)
    # The control plane's own repository root (…/src/dcp/api/deps.py → repo).
    home_path = str(Path(__file__).resolve().parents[3])
    self_improvement = SelfImprovementManager(db, tasks, executor, home_path)
    return AppState(
        settings=settings,
        db=db,
        discovery=discovery,
        scanner=ScanManager(discovery),
        watcher=SentryWatcher(db),
        inference=inference,
        assembler=assembler,
        router=router,
        analysis=AnalysisManager(
            db, status_agent, inference, assembler,
            max_workers=settings.analysis_workers,
            tasks=tasks,
        ),
        completion=completion,
        autopilot=AutopilotManager(
            db, executor, completion, inference, assembler,
            tasks=tasks, self_improvement=self_improvement,
        ),
        tasks=tasks,
        self_improvement=self_improvement,
    )
