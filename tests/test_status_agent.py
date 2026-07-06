"""Tests for the status report agent (digest + tier-0 path)."""

from dcp.agents.status_agent import (
    GENERATED_MARKER,
    ProjectStatus,
    StatusReportAgent,
    build_tier0_status,
    collect_project_digest,
)
from dcp.config import Settings
from dcp.cortex import ContextAssembler


def make_context(db, path):
    return ContextAssembler(db).assemble(str(path))


def test_digest_contains_readme_manifest_and_tree(db, sample_tree):
    py_proj = sample_tree / "py_proj"
    digest = collect_project_digest(str(py_proj))
    assert "README.md" in digest
    assert "requirements.txt" in digest
    assert "File tree" in digest
    assert "app.py" in digest


def test_digest_caps_large_readme(db, tmp_path):
    proj = tmp_path / "big"
    proj.mkdir()
    (proj / "README.md").write_text("x" * 100_000)
    digest = collect_project_digest(str(proj))
    # README head capped at 2000 chars + section headers.
    assert len(digest) < 5000


def test_tier0_status_shape_and_health(db, sample_tree):
    context = make_context(db, sample_tree / "py_proj")
    status = build_tier0_status(context)
    assert status.health in {"green", "yellow", "red"}
    assert status.headline and len(status.headline) <= 120
    assert "Python" in status.headline
    assert status.tier == 0
    # py_proj has no git/CI → improvement steps expected.
    assert status.next_steps


def test_markdown_render_has_marker_and_sections(db, sample_tree):
    context = make_context(db, sample_tree / "py_proj")
    md = build_tier0_status(context).to_markdown()
    assert md.startswith(GENERATED_MARKER)
    assert "# Project Status:" in md
    assert "## Summary" in md
    assert "## Suggested next steps" in md


def test_agent_falls_back_to_tier0_without_ai(db, sample_tree):
    agent = StatusReportAgent(Settings(ai_enabled=False))
    context = make_context(db, sample_tree / "py_proj")
    status = agent.build_status(context)
    assert isinstance(status, ProjectStatus)
    assert status.tier == 0  # graceful internal fallback, no exception
