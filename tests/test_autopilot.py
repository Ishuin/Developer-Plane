"""Tests for the autopilot manager and executor (fake agent command only)."""

import subprocess
import sys

import pytest

from dcp.agents.executor import CodeAgentExecutor
from dcp.config import Settings
from dcp.core.models import AgentRun
from dcp.cortex import CompletionEngine, ContextAssembler, StageInferenceEngine
from dcp.cortex.autopilot import AutopilotManager

PY = sys.executable.replace("\\", "/")

# Fake agent: creates one file in the project so a diff exists.
FAKE_AGENT = f'"{PY}" -c "open(\'agent_output.txt\',\'w\').write(\'done\')"'
FAKE_NOOP = f'"{PY}" -c "pass"'


def make_manager(db, agent_cmd=FAKE_AGENT, timeout=60):
    settings = Settings(agent_cmd=agent_cmd, agent_timeout=timeout, ai_enabled=False)
    return AutopilotManager(
        db,
        CodeAgentExecutor(settings),
        CompletionEngine(db),
        StageInferenceEngine(db),
        ContextAssembler(db),
    )


def git(path, *args):
    subprocess.run(["git", "-C", str(path), *args], capture_output=True, check=True)


@pytest.fixture
def git_project(tmp_path):
    proj = tmp_path / "gitproj"
    proj.mkdir()
    (proj / "main.py").write_text("print('hello')\n")
    (proj / "requirements.txt").write_text("")
    git(proj, "init", "-q")
    git(proj, "add", "-A")
    git(proj, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init")
    return proj


def test_queue_ordering(db):
    db.upsert_project("/q/half", "Python")
    db.upsert_project("/q/near", "Python")
    db.upsert_project("/q/off", "Python")
    for path in ("/q/half", "/q/near", "/q/off"):
        db.set_automation(path, True)
    db.set_automation("/q/off", False)
    db.set_project_completion("/q/half", 50.0, "heuristic")
    db.set_project_completion("/q/near", 90.0, "heuristic")

    queue = db.autopilot_queue()
    assert [p.path for p in queue] == ["/q/near", "/q/half"]  # off excluded


def test_run_project_records_run_and_decision(db, git_project):
    manager = make_manager(db)
    outcome = manager.run_project(str(git_project))
    assert outcome == "done"

    runs = db.get_agent_runs(limit=5)
    assert len(runs) == 1
    run = runs[0]
    assert run.exit_code == 0
    assert "agent_output.txt" in run.diff_stat
    assert run.verdict is None
    assert (git_project / "agent_output.txt").is_file()

    decisions = [d for d in db.get_decisions(limit=10)
                 if d.decision_type == "AgentRunProposed"]
    assert decisions and decisions[0].data["changed_files"] == ["agent_output.txt"]


def test_dirty_tree_skipped(db, git_project):
    (git_project / "main.py").write_text("print('WIP')\n")  # uncommitted change
    manager = make_manager(db)
    assert manager.run_project(str(git_project)) == "skipped"
    assert db.count_agent_runs() == 0


def test_pending_run_blocks_second(db, git_project):
    manager = make_manager(db, agent_cmd=FAKE_NOOP)
    assert manager.run_project(str(git_project)) == "done"
    # First run pending verdict → second run refused.
    assert manager.run_project(str(git_project)) == "skipped"
    assert db.count_agent_runs() == 1


def test_discard_reverts_changes(db, git_project):
    manager = make_manager(db)
    manager.run_project(str(git_project))
    run = db.get_agent_runs(limit=1)[0]
    assert (git_project / "agent_output.txt").is_file()

    result = manager.apply_verdict(run.id, "discarded")
    assert result["reverted"] is True
    assert not (git_project / "agent_output.txt").exists()
    assert db.get_agent_run(run.id).verdict == "discarded"


def test_approve_keeps_changes(db, git_project):
    manager = make_manager(db)
    manager.run_project(str(git_project))
    run = db.get_agent_runs(limit=1)[0]
    manager.apply_verdict(run.id, "approved")
    assert (git_project / "agent_output.txt").is_file()
    assert db.get_agent_run(run.id).verdict == "approved"

    with pytest.raises(ValueError):
        manager.apply_verdict(run.id, "discarded")  # already verdicted


def test_batch_lifecycle(db, git_project):
    db.upsert_project(str(git_project), "Python")
    db.set_automation(str(git_project), True)
    manager = make_manager(db, agent_cmd=FAKE_NOOP)
    manager.start(limit=5)
    manager.wait(timeout=60)
    status = manager.status()
    assert status["running"] is False
    assert status["done"] == 1
    assert status["failed"] == 0


def test_executor_timeout(db, git_project):
    slow = f'"{PY}" -c "import time; time.sleep(30)"'
    manager = make_manager(db, agent_cmd=slow, timeout=2)
    manager.run_project(str(git_project))
    run = db.get_agent_runs(limit=1)[0]
    assert run.exit_code == -1
    assert "timed out" in run.report
