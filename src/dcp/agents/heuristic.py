"""Tier 0 agent: deterministic project health check. Always available."""

from typing import Any, Dict, List

from dcp.agents.base import Agent, AgentResult


class HealthCheckAgent(Agent):
    name = "health-check"
    tier = 0
    description = "Deterministic project health report (no AI required)."

    def run(self, context: Dict[str, Any]) -> AgentResult:
        genome = context.get("genome", {})
        stage = context.get("stage") or {}
        recommendations: List[str] = []

        if not genome.get("git", {}).get("is_repo"):
            recommendations.append("Initialize git — no version control detected.")
        if not genome.get("has_tests"):
            recommendations.append("Add a test suite — none detected.")
        if not genome.get("has_ci"):
            recommendations.append("Add CI (e.g., GitHub Actions) for automated checks.")
        if not genome.get("has_docs"):
            recommendations.append("Add a README/docs so agents and humans share context.")
        dirty = genome.get("git", {}).get("dirty_files", 0)
        if dirty > 10:
            recommendations.append(
                f"{dirty} uncommitted files — commit or stash to reduce entropy."
            )
        if not recommendations:
            recommendations.append("Fundamentals look healthy. Keep shipping.")

        stage_txt = (
            f"{stage.get('stage', 'unknown')} "
            f"(confidence {stage.get('confidence', 0):.2f})"
            if stage else "not yet inferred"
        )
        summary = (
            f"{genome.get('type', 'Unknown')} project at stage {stage_txt}; "
            f"{len(recommendations)} recommendation(s)."
        )
        return AgentResult(
            agent=self.name, summary=summary, recommendations=recommendations
        )
