"""Probabilistic project stage inference with confidence decay.

Stages: R&D, Development, Deployed, Dormant.
Deterministic (Tier 0) evidence scoring; confidence decays exponentially
with inactivity so stale knowledge never masquerades as certainty.
"""

import math
from datetime import datetime, timedelta
from typing import List, Optional

from dcp.core.models import Genome, StageResult
from dcp.database import EventSourcingDB
from dcp.sentry.genome import build_genome


class StageInferenceEngine:
    def __init__(self, db: EventSourcingDB, half_life_days: float = 14.0):
        self.db = db
        self.half_life_days = half_life_days

    def infer_stage(
        self, project_path: str, genome: Optional[Genome] = None
    ) -> StageResult:
        genome = genome or build_genome(project_path)
        evidence: List[str] = []
        scores = {"R&D": 0.0, "Development": 0.0, "Deployed": 0.0}

        # --- deterministic evidence -------------------------------------
        if genome.git.get("is_repo"):
            scores["Development"] += 1.0
            evidence.append("git repository present")
            if genome.git.get("dirty_files", 0) > 0:
                scores["Development"] += 1.0
                evidence.append(f"{genome.git['dirty_files']} uncommitted change(s)")
        else:
            scores["R&D"] += 1.0
            evidence.append("no version control yet")

        if genome.has_tests:
            scores["Development"] += 1.0
            scores["Deployed"] += 0.5
            evidence.append("test suite present")
        else:
            scores["R&D"] += 0.5
            evidence.append("no tests found")

        if genome.has_ci:
            scores["Deployed"] += 1.5
            evidence.append("CI configuration present")
        if genome.has_dockerfile:
            scores["Deployed"] += 1.5
            evidence.append("container/deploy artifacts present")
        if genome.has_docs:
            scores["Development"] += 0.5
            evidence.append("documentation present")
        if not genome.markers:
            scores["R&D"] += 1.0
            evidence.append("no project manifest")

        stage = max(scores, key=scores.get)
        total = sum(scores.values()) or 1.0
        confidence = scores[stage] / total

        # --- inactivity decay --------------------------------------------
        idle_days = self._idle_days(genome)
        if idle_days is not None:
            decay = math.pow(0.5, idle_days / self.half_life_days)
            confidence *= decay
            if idle_days > 2 * self.half_life_days:
                stage = "Dormant"
                evidence.append(f"idle for {idle_days:.0f} days")
                confidence = min(0.9, 1.0 - decay)  # dormancy grows more certain

        confidence = max(0.0, min(1.0, round(confidence, 3)))
        result = StageResult(
            project_id=project_path, stage=stage,
            confidence=confidence, evidence=evidence,
        )
        self.db.log_inference(
            "ProjectStage",
            {"stage": stage, "evidence": evidence},
            confidence_score=confidence,
            project_id=project_path,
        )
        return result

    def _idle_days(self, genome: Genome) -> Optional[float]:
        """Days since last observed activity (git commit or fabric signal)."""
        candidates: List[datetime] = []
        commit_date = genome.git.get("last_commit_date")
        if commit_date:
            try:
                candidates.append(
                    datetime.fromisoformat(commit_date).replace(tzinfo=None)
                )
            except ValueError:
                pass
        signals = self.db.get_signals(limit=1, project_id=genome.path)
        if signals:
            try:
                candidates.append(datetime.fromisoformat(signals[0].timestamp))
            except ValueError:
                pass
        if not candidates:
            return None
        idle: timedelta = datetime.now() - max(candidates)
        return max(0.0, idle.total_seconds() / 86400.0)
