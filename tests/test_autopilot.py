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


def make_manager(db, agent_cmd=FAKE_AGENT, timeout=60, tasks=None, selfimp=None):
    settings = Settings(agent_cmd=agent_cmd, agent_timeout=timeout, ai_enabled=False)
    return AutopilotManager(
        db,
        CodeAgentExecutor(settings),
        CompletionEngine(db),
        StageInferenceEngine(db),
        ContextAssembler(db),
        tasks=tasks,
        self_improvement=selfimp,
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
    outcome, reason = manager.run_project(str(git_project))
    assert outcome == "done" and reason is None

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
    outcome, reason = manager.run_project(str(git_project))
    assert outcome == "skipped"
    assert "uncommitted" in reason
    assert db.count_agent_runs() == 0


def test_pending_run_blocks_second(db, git_project):
    manager = make_manager(db, agent_cmd=FAKE_NOOP)
    assert manager.run_project(str(git_project))[0] == "done"
    # First run pending verdict → second run refused.
    outcome, reason = manager.run_project(str(git_project))
    assert outcome == "skipped"
    assert "approve/discard" in reason
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


def test_library_projects_never_touched(db, git_project):
    path = str(git_project)
    db.upsert_project(path, "Python")
    db.set_project_kind(path, "library")

    manager = make_manager(db)
    outcome, reason = manager.run_project(path)
    assert outcome == "skipped"
    assert "read-only" in reason
    assert db.count_agent_runs() == 0
    refusals = [d for d in db.get_decisions(limit=10)
                if d.decision_type == "AgentRunRefused"]
    assert refusals and "library" in refusals[0].data["reason"]


def test_run_moves_kanban_cards(db, git_project):
    from dcp.cortex.tasks import TaskService

    path = str(git_project)
    db.upsert_project(path, "Python")
    tasks = TaskService(db)
    card = tasks.seed(path, ["Do the thing"], origin="analysis")[0]

    manager = make_manager(db, agent_cmd=FAKE_NOOP, tasks=tasks)
    manager.run_project(path)

    moved = db.get_task(card.id)
    assert moved.status == "review"
    assert moved.run_id == db.get_agent_runs(limit=1)[0].id

    # Approve → card lands in done.
    run = db.get_agent_runs(limit=1)[0]
    manager.apply_verdict(run.id, "approved")
    assert db.get_task(card.id).status == "done"


def test_discard_verdict_returns_card_to_todo(db, git_project):
    from dcp.cortex.tasks import TaskService

    path = str(git_project)
    db.upsert_project(path, "Python")
    tasks = TaskService(db)
    card = tasks.seed(path, ["Another thing"], origin="analysis")[0]

    manager = make_manager(db, agent_cmd=FAKE_NOOP, tasks=tasks)
    manager.run_project(path)
    run = db.get_agent_runs(limit=1)[0]
    manager.apply_verdict(run.id, "discarded")
    assert db.get_task(card.id).status == "todo"


def test_failed_run_records_bottleneck(db, git_project, tmp_path):
    from dcp.cortex.self_improvement import SelfImprovementManager
    from dcp.cortex.tasks import TaskService

    home = tmp_path / "home"
    home.mkdir()
    tasks = TaskService(db)
    selfimp = SelfImprovementManager(
        db, tasks,
        CodeAgentExecutor(Settings(agent_cmd=FAKE_NOOP, agent_timeout=30)),
        str(home),
    )
    failing = f'"{PY}" -c "import sys; sys.exit(3)"'
    manager = make_manager(db, agent_cmd=failing, tasks=tasks, selfimp=selfimp)
    manager.run_project(str(git_project))

    self_tasks = db.list_tasks(pipeline="self", limit=10)
    assert self_tasks and "agent-run-failure" in self_tasks[0].title


def test_executor_pipes_brief_via_stdin(db, git_project):
    copier = (f'"{PY}" -c "import sys; '
              f"open('brief_copy.txt','w').write(sys.stdin.read())\"")
    manager = make_manager(db, agent_cmd=copier)
    manager.run_project(str(git_project))

    copy = (git_project / "brief_copy.txt").read_text(encoding="utf-8")
    assert "Rules (non-negotiable)" in copy
    assert "Project Context" in copy


def test_executor_brief_file_written_inside_project(db, git_project):
    checker = (f'"{PY}" -c "import os,sys; '
               f"sys.exit(0 if os.path.isfile('.dcp_brief.md') else 4)\"")
    # A template containing the placeholder triggers the file-path branch.
    settings = Settings(agent_cmd=checker + "  # {brief_file}", agent_timeout=30)
    executor = CodeAgentExecutor(settings)
    outcome = executor.execute(str(git_project), "brief body")
    assert outcome.exit_code == 0
    # Brief file is cleaned up afterwards and never counted as a change.
    assert not (git_project / ".dcp_brief.md").exists()
    assert ".dcp_brief.md" not in outcome.changed_files


def test_tooling_dirs_not_counted_as_changes(db, git_project):
    polluter = (f'"{PY}" -c "import os; os.makedirs(\'.omc\', exist_ok=True); '
                f"open('.omc/state.json','w').write('x'); "
                f"open('real_change.py','w').write('pass')\"")
    manager = make_manager(db, agent_cmd=polluter)
    manager.run_project(str(git_project))
    run = db.get_agent_runs(limit=1)[0]
    assert "real_change.py" in run.diff_stat
    assert ".omc" not in run.diff_stat


def test_executor_timeout(db, git_project):
    slow = f'"{PY}" -c "import time; time.sleep(30)"'
    manager = make_manager(db, agent_cmd=slow, timeout=2)
    manager.run_project(str(git_project))
    run = db.get_agent_runs(limit=1)[0]
    assert run.exit_code == -1
    assert "timed out" in run.report
