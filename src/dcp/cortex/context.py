"""Context Assembler: package project state into a payload for AI agents."""

from typing import Any, Dict, Optional

from dcp.core.models import Genome, StageResult
from dcp.database import EventSourcingDB
from dcp.sentry.genome import build_genome


class ContextAssembler:
    def __init__(self, db: EventSourcingDB):
        self.db = db

    def assemble(
        self,
        project_path: str,
        genome: Optional[Genome] = None,
        stage: Optional[StageResult] = None,
        recent_signals: int = 15,
    ) -> Dict[str, Any]:
        genome = genome or build_genome(project_path)
        signals = self.db.get_signals(limit=recent_signals, project_id=project_path)
        inferences = self.db.get_inferences(limit=5, project_id=project_path)

        return {
            "project": project_path,
            "genome": genome.model_dump(),
            "stage": stage.model_dump() if stage else None,
            "recent_signals": [s.model_dump() for s in signals],
            "recent_inferences": [i.model_dump() for i in inferences],
        }

    @staticmethod
    def to_prompt(context: Dict[str, Any]) -> str:
        """Render the payload as a compact prompt for agent injection."""
        genome = context["genome"]
        lines = [
            f"# Project Context: {context['project']}",
            f"- Stack: {genome['type']}",
            f"- Markers: {', '.join(genome['markers']) or 'none'}",
            f"- Tests: {'yes' if genome['has_tests'] else 'no'}"
            f" | CI: {'yes' if genome['has_ci'] else 'no'}"
            f" | Docker: {'yes' if genome['has_dockerfile'] else 'no'}",
        ]
        git = genome.get("git") or {}
        if git.get("is_repo"):
            lines.append(
                f"- Git: branch={git.get('branch', '?')}, "
                f"last commit {git.get('last_commit_date', '?')} "
                f"({git.get('dirty_files', 0)} dirty)"
            )
        stage = context.get("stage")
        if stage:
            lines.append(
                f"- Inferred stage: {stage['stage']} "
                f"(confidence {stage['confidence']:.2f})"
            )
        if context["recent_signals"]:
            lines.append("\n## Recent activity")
            for s in context["recent_signals"][:10]:
                lines.append(f"- {s['timestamp']} {s['event_type']}")
        return "\n".join(lines)
