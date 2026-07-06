"""Agent Router: registry + dispatch with graceful degradation.

Tier 1 (LangGraph) agents are used when available; otherwise the router
falls back to the deterministic Tier 0 heuristic agent. AI is never a
blocking dependency.
"""

import logging
from typing import Any, Dict, List

from dcp.agents.base import Agent, AgentResult, AgentUnavailable
from dcp.database import EventSourcingDB

logger = logging.getLogger(__name__)


class AgentRouter:
    def __init__(self, db: EventSourcingDB):
        self.db = db
        self._agents: Dict[str, Agent] = {}

    def register(self, agent: Agent) -> None:
        self._agents[agent.name] = agent

    def available(self) -> List[Dict[str, Any]]:
        return [
            {"name": a.name, "tier": a.tier, "description": a.description}
            for a in self._agents.values()
        ]

    def run(self, agent_name: str, context: Dict[str, Any]) -> AgentResult:
        agent = self._agents.get(agent_name)
        if agent is None:
            raise KeyError(f"Unknown agent: {agent_name}")
        try:
            result = agent.run(context)
        except AgentUnavailable as exc:
            fallback = self._tier0_fallback(agent_name)
            if fallback is None:
                raise
            logger.warning("%s unavailable (%s); falling back to %s",
                           agent_name, exc, fallback.name)
            result = fallback.run(context)
            result.notes.append(f"fell back from {agent_name}: {exc}")

        self.db.log_decision(
            "AgentRun",
            {"agent": result.agent, "summary": result.summary, "notes": result.notes},
            project_id=context.get("project"),
        )
        return result

    def _tier0_fallback(self, requested: str) -> Agent | None:
        for agent in self._agents.values():
            if agent.tier == 0 and agent.name != requested:
                return agent
        return None
