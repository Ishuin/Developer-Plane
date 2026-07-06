"""Tests for the Definition-of-Done completion engine."""

import sys

from dcp.cortex.completion import CompletionEngine, load_dod


def write_dod(path, content):
    (path / "dod.yaml").write_text(content, encoding="utf-8")


def test_load_dod_missing_returns_empty(tmp_path):
    assert load_dod(str(tmp_path)) == []


def test_load_dod_malformed_returns_empty(tmp_path):
    write_dod(tmp_path, ":::not yaml:::[")
    assert load_dod(str(tmp_path)) == []


def test_dod_assertions_all_types(db, tmp_path):
    proj = tmp_path / "dodproj"
    proj.mkdir()
    (proj / "ci.yml").write_text("ok")
    (proj / "code.py").write_text("# TODO one thing\nprint('x')\n")
    py = sys.executable.replace("\\", "/")
    write_dod(proj, f"""
assertions:
  - name: command passes
    type: command
    run: '"{py}" -c "exit(0)"'
  - name: command fails
    type: command
    run: '"{py}" -c "exit(1)"'
  - name: ci file exists
    type: file_exists
    path: ci.yml
  - name: few todos
    type: max_todos
    limit: 5
""")
    result = CompletionEngine(db).evaluate(str(proj))
    assert result.source == "dod"
    assert result.percent == 75.0
    assert "command fails" in result.failed
    assert {"command passes", "ci file exists", "few todos"} <= set(result.passed)


def test_max_todos_fails_over_limit(db, tmp_path):
    proj = tmp_path / "todoproj"
    proj.mkdir()
    (proj / "a.py").write_text("# TODO 1\n# FIXME 2\n# XXX 3\n")
    write_dod(proj, "assertions:\n  - name: todos\n    type: max_todos\n    limit: 2\n")
    result = CompletionEngine(db).evaluate(str(proj))
    assert result.percent == 0.0
    assert result.failed == ["todos"]


def test_heuristic_fallback_scores_genome(db, sample_tree):
    py_proj = str(sample_tree / "py_proj")  # tests+docs, no git/ci/docker
    result = CompletionEngine(db).evaluate(py_proj)
    assert result.source == "heuristic"
    assert result.percent == 40.0  # tests 25 + docs 15
    assert "version control" in result.failed


def test_evaluate_persists_to_projection_and_log(db, sample_tree):
    py_proj = str(sample_tree / "py_proj")
    db.upsert_project(py_proj, "Python")
    CompletionEngine(db).evaluate(py_proj)

    project = db.get_project(py_proj)
    assert project.completion_percent == 40.0
    assert project.completion_source == "heuristic"

    inference = db.get_inferences(limit=1)[0]
    assert inference.inference_type == "CompletionEvaluated"
    assert inference.confidence_score == 0.5
