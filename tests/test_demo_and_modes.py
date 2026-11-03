"""Tests for demo workspace, agent-mode API, and scan-triggered analysis."""

import pytest
from fastapi.testclient import TestClient

from dcp import demo
from dcp.api import create_app
from dcp.config import Settings
from dcp.core.models import AgentRun  # noqa: F401  (import check)
from dcp.sentry.scanner import ScanManager


def make_client(tmp_path, **over):
    settings = Settings(db_path=str(tmp_path / "m.db"), env_file=str(tmp_path / ".env"),
                        ai_enabled=False, **over)
    return TestClient(create_app(settings)), tmp_path / ".env"


def test_demo_workspace_has_all_projects(tmp_path, monkeypatch):
    monkeypatch.setattr(demo, "DEMO_WORKSPACE", tmp_path / "ws")
    paths = demo.build_demo_workspace()
    names = {p.replace("\\", "/").rsplit("/", 1)[-1] for p in paths}
    assert {"invoice-api", "todo-cli", "text-utils", "ml-experiments", "legacy-blog"} <= names
    assert demo.build_demo_workspace() == paths  # idempotent


def test_reset_demo_removes_readonly_git_objects(tmp_path, monkeypatch):
    monkeypatch.setattr(demo, "DEMO_HOME", tmp_path / "home")
    monkeypatch.setattr(demo, "DEMO_WORKSPACE", tmp_path / "home" / "workspace")
    demo.build_demo_workspace()
    demo.reset_demo()
    assert not (tmp_path / "home").exists()


def test_agent_mode_persists_outside_demo(tmp_path):
    client, env_path = make_client(tmp_path)
    with client:
        assert client.put("/api/settings/agent", json={"mode": "native"}).json()["mode"] == "native"
        assert client.get("/api/health").json()["agent_mode"] == "native"
        assert client.put("/api/settings/agent", json={"mode": "bogus"}).status_code == 422
    assert "DCP_AGENT_MODE=native" in env_path.read_text()


def test_agent_mode_not_persisted_in_demo(tmp_path, monkeypatch):
    monkeypatch.setattr(demo, "DEMO_WORKSPACE", tmp_path / "ws")
    monkeypatch.setattr("dcp.api.app.seed_demo_state", lambda state: None)
    client, env_path = make_client(tmp_path, demo_mode=True)
    with client:
        client.put("/api/settings/agent", json={"mode": "cli"})
        assert client.get("/api/health").json()["demo"] is True
    assert not env_path.exists()


def test_scan_triggers_callback(db, sample_tree):
    from dcp.sentry import ProjectDiscovery

    called = []
    manager = ScanManager(ProjectDiscovery(db), on_finished=lambda: called.append(1))
    manager.start(str(sample_tree))
    manager.wait(30)
    assert called == [1]


def test_start_unanalyzed_only_picks_new_projects(db):
    from dcp.cortex.analysis import AnalysisManager

    db.upsert_project("/a", "Python")
    db.upsert_project("/b", "Python")
    manager = AnalysisManager(db, None, None, None)
    started = []
    manager.start = lambda paths=None: started.append(sorted(paths))
    manager.start_unanalyzed()
    assert started == [["/a", "/b"]]
