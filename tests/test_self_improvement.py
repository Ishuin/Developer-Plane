"""Tests for the self-improvement pipeline (bottlenecks, gating, daily-once)."""

import sys
from datetime import datetime, timedelta

import pytest

from dcp.agents.executor import CodeAgentExecutor
from dcp.config import Settings
from dcp.cortex.self_improvement import SELF_FILE, SelfImprovementManager
from dcp.cortex.tasks import TaskService

PY = sys.executable.replace("\\", "/")
FAKE_NOOP = f'"{PY}" -c "pass"'


@pytest.fixture
def home(tmp_path):
    h = tmp_path / "dcp_home"
    h.mkdir()
    return h


@pytest.fixture
def manager(db, home):
    return SelfImprovementManager(
        db, TaskService(db),
        CodeAgentExecutor(Settings(agent_cmd=FAKE_NOOP, agent_timeout=30)),
        str(home),
    )


def test_bottleneck_creates_self_task_and_file(db, home, manager):
    task = manager.record_bottleneck(
        "agent-run-failure", "exit 1 on demo: pytest missing", project_id="/p/demo"
    )
    assert task is not None and task.pipeline == "self"
    assert db.count_open_tasks(pipeline="self") == 1

    content = (home / SELF_FILE).read_text(encoding="utf-8")
    assert "Self-Improvement Backlog" in content
    assert "agent-run-failure" in content

    signals = db.get_signals(limit=5)
    assert any(s.event_type == "BottleneckObserved" for s in signals)


def test_duplicate_bottleneck_not_duplicated(db, manager):
    manager.record_bottleneck("timeout", "same issue")
    manager.record_bottleneck("timeout", "same issue")
    assert db.count_open_tasks(pipeline="self") == 1


def test_daily_run_executes_one_task(db, home, manager):
    manager.record_bottleneck("timeout", "improve digest caps")
    manager.record_bottleneck("guard-skip", "second issue")

    result = manager.maybe_run_daily()
    assert result["executed"] is True

    # One task moved to review, the other still todo.
    tasks = db.list_tasks(pipeline="self", limit=10)
    statuses = sorted(t.status for t in tasks)
    assert statuses == ["review", "todo"]

    runs = db.get_agent_runs(limit=5)
    assert len(runs) == 1 and runs[0].exit_code == 0


def test_daily_budget_one_per_day(db, manager):
    manager.record_bottleneck("timeout", "first")
    manager.record_bottleneck("timeout", "second")
    assert manager.maybe_run_daily()["executed"] is True

    second = manager.maybe_run_daily()
    assert second["executed"] is False
    assert "daily budget" in second["reason"]

    # A day later it becomes eligible again.
    tomorrow = datetime.now() + timedelta(days=1, minutes=1)
    third = manager.maybe_run_daily(now=tomorrow)
    # Second task is todo but its sibling sits in review (pending verdict on
    # home project) — pending runs on the HOME project do not block self work.
    assert third["executed"] is True


def test_other_project_work_blocks_self_execution(db, manager):
    manager.record_bottleneck("timeout", "self task")
    TaskService(db).seed("/p/other", ["Ship feature"], origin="analysis")

    result = manager.maybe_run_daily()
    assert result["executed"] is False
    assert "other projects" in result["reason"]


def test_no_tasks_no_execution(db, manager):
    result = manager.maybe_run_daily()
    assert result["executed"] is False
    assert "no self-improvement tasks" in result["reason"]


def test_status_shape(db, manager):
    status = manager.status()
    assert {"open_self_tasks", "last_execution", "next_eligible",
            "other_work_active", "scheduler_running"} <= set(status)
