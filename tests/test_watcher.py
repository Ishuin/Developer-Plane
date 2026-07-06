"""Tests for watcher event attribution (no real filesystem watching)."""

from types import SimpleNamespace

from dcp.sentry.discovery import ProjectDiscovery
from dcp.sentry.watcher import SentryWatcher


def fake_event(src_path, is_directory=False):
    return SimpleNamespace(src_path=src_path, is_directory=is_directory)


def test_events_attributed_to_owning_project(db, sample_tree):
    ProjectDiscovery(db).scan(str(sample_tree))
    watcher = SentryWatcher(db)
    watcher.refresh_roots()

    py_proj = str(sample_tree / "py_proj")
    watcher.on_modified(fake_event(py_proj + "\\app.py"))

    signals = db.get_signals(limit=5, project_id=py_proj)
    assert signals and signals[0].event_type == "FileChanged"

    # last_activity was touched.
    project = db.get_project(py_proj)
    assert project.last_activity is not None


def test_events_outside_projects_have_no_project_id(db, sample_tree):
    ProjectDiscovery(db).scan(str(sample_tree))
    watcher = SentryWatcher(db)
    watcher.refresh_roots()

    watcher.on_modified(fake_event(str(sample_tree / "loose.txt")))
    signals = db.get_signals(limit=1)
    assert signals[0].project_id is None


def test_noise_paths_ignored(db, sample_tree):
    watcher = SentryWatcher(db)
    watcher.refresh_roots()

    watcher.on_modified(fake_event(str(sample_tree / "x" / "__pycache__" / "a.pyc")))
    watcher.on_modified(fake_event(str(sample_tree / "context_fabric.db")))
    watcher.on_modified(fake_event(str(sample_tree / ".omc" / "memory.json")))
    watcher.on_modified(fake_event(str(sample_tree / "a" / "file.lock")))
    assert db.count_signals() == 0

    # A dotfile itself (not inside a dot-dir) is a real edit.
    watcher.on_modified(fake_event(str(sample_tree / ".gitignore")))
    assert db.count_signals() == 1


def test_new_discovery_updates_roots_via_bus(db, tmp_path):
    from dcp.core.bus import EventBus

    bus = EventBus()
    watcher = SentryWatcher(db, event_bus=bus)
    watcher.refresh_roots()

    proj = tmp_path / "fresh"
    proj.mkdir()
    (proj / "go.mod").write_text("module fresh\n")
    ProjectDiscovery(db, event_bus=bus).scan(str(tmp_path))

    watcher.on_modified(fake_event(str(proj / "main.go")))
    signals = db.get_signals(limit=5, project_id=str(proj))
    assert signals, "event should be attributed to newly discovered project"
