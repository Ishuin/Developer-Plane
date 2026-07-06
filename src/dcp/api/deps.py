"""Shared application state and dependency wiring."""

from dataclasses import dataclass

from dcp.agents import HealthCheckAgent, LangGraphAdvisorAgent
from dcp.agents.status_agent import StatusReportAgent
from dcp.config import Settings
from dcp.cortex import (
    AgentRouter,
    AnalysisManager,
    ContextAssembler,
    StageInferenceEngine,
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


def build_state(settings: Settings) -> AppState:
    db = EventSourcingDB(settings.db_path)
    router = AgentRouter(db)
    router.register(HealthCheckAgent())
    router.register(LangGraphAdvisorAgent(settings))
    status_agent = StatusReportAgent(settings)
    router.register(status_agent)
    discovery = ProjectDiscovery(db)
    inference = StageInferenceEngine(db, settings.confidence_half_life_days)
    assembler = ContextAssembler(db)
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
        ),
    )
