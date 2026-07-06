"""Tests for stage inference and confidence decay."""

from dcp.core.models import Genome
from dcp.cortex.inference import StageInferenceEngine


def make_genome(**overrides) -> Genome:
    base = dict(
        path="/fake/proj", type="Python", markers=["requirements.txt"],
        has_tests=False, has_ci=False, has_docs=False, has_dockerfile=False,
        git={},
    )
    base.update(overrides)
    return Genome(**base)


def test_no_git_no_manifest_is_rnd(db):
    engine = StageInferenceEngine(db)
    genome = make_genome(markers=[], git={})
    result = engine.infer_stage("/fake/proj", genome=genome)
    assert result.stage == "R&D"
    assert 0.0 <= result.confidence <= 1.0
    assert result.evidence


def test_git_plus_tests_is_development(db):
    engine = StageInferenceEngine(db)
    genome = make_genome(
        has_tests=True, has_docs=True,
        git={"is_repo": True, "dirty_files": 3},
    )
    result = engine.infer_stage("/fake/proj", genome=genome)
    assert result.stage == "Development"


def test_ci_and_docker_lean_deployed(db):
    engine = StageInferenceEngine(db)
    genome = make_genome(
        has_tests=True, has_ci=True, has_dockerfile=True,
        git={"is_repo": True, "dirty_files": 0},
    )
    result = engine.infer_stage("/fake/proj", genome=genome)
    assert result.stage == "Deployed"


def test_long_idle_project_goes_dormant(db):
    engine = StageInferenceEngine(db, half_life_days=14)
    genome = make_genome(
        git={"is_repo": True, "last_commit_date": "2024-01-01T00:00:00+00:00"},
    )
    result = engine.infer_stage("/fake/proj", genome=genome)
    assert result.stage == "Dormant"
    assert any("idle" in e for e in result.evidence)


def test_recent_activity_keeps_confidence_high(db):
    from datetime import datetime

    engine = StageInferenceEngine(db, half_life_days=14)
    genome = make_genome(
        has_tests=True,
        git={"is_repo": True, "last_commit_date": datetime.now().isoformat(),
             "dirty_files": 1},
    )
    result = engine.infer_stage("/fake/proj", genome=genome)
    assert result.stage == "Development"
    assert result.confidence > 0.3


def test_inference_is_logged_with_confidence(db):
    engine = StageInferenceEngine(db)
    engine.infer_stage("/fake/proj", genome=make_genome())
    inferences = db.get_inferences(limit=1)
    assert inferences[0].inference_type == "ProjectStage"
    assert 0.0 <= inferences[0].confidence_score <= 1.0
