"""Tests for the event-sourcing repository."""

import pytest
from pydantic import ValidationError


def test_signal_roundtrip(db):
    signal = db.log_signal("FileChanged", {"src_path": "a.py"}, project_id="proj1")
    assert signal.id is not None

    fetched = db.get_signals(limit=10)
    assert len(fetched) == 1
    assert fetched[0].event_type == "FileChanged"
    assert fetched[0].data == {"src_path": "a.py"}
    assert fetched[0].project_id == "proj1"


def test_signal_pagination_and_ordering(db):
    for i in range(30):
        db.log_signal("Tick", {"n": i})
    assert db.count_signals() == 30

    page1 = db.get_signals(limit=10, offset=0)
    page3 = db.get_signals(limit=10, offset=20)
    assert len(page1) == 10 and len(page3) == 10
    # Newest first.
    assert page1[0].data["n"] == 29
    assert page3[-1].data["n"] == 0


def test_signal_project_filter(db):
    db.log_signal("A", {}, project_id="p1")
    db.log_signal("B", {}, project_id="p2")
    assert db.count_signals(project_id="p1") == 1
    assert db.get_signals(project_id="p2")[0].event_type == "B"


def test_inference_requires_valid_confidence(db):
    inference = db.log_inference("Stage", {"stage": "Dev"}, 0.8, project_id="p")
    assert inference.confidence_score == 0.8

    with pytest.raises(ValidationError):
        db.log_inference("Stage", {}, 1.5)
    with pytest.raises(ValidationError):
        db.log_inference("Stage", {}, -0.1)


def test_decision_roundtrip(db):
    db.log_decision("AgentRun", {"agent": "health-check"}, project_id="p")
    decisions = db.get_decisions()
    assert decisions[0].decision_type == "AgentRun"
    assert db.count_decisions() == 1


def test_project_upsert_and_listing(db):
    db.upsert_project("/a/one", "Python")
    db.upsert_project("/a/two", "Rust")
    db.upsert_project("/a/one", "Python")  # idempotent upsert

    items, total = db.list_projects(limit=10, offset=0)
    assert total == 2
    assert [p.path for p in items] == ["/a/one", "/a/two"]


def test_project_search_and_type_filter(db):
    db.upsert_project("/x/alpha", "Python")
    db.upsert_project("/x/beta", "Go")

    items, total = db.list_projects(search="alph")
    assert total == 1 and items[0].path == "/x/alpha"

    items, total = db.list_projects(project_type="Go")
    assert total == 1 and items[0].type == "Go"

    assert db.project_types() == ["Go", "Python"]


def test_project_list_pagination(db):
    for i in range(45):
        db.upsert_project(f"/p/{i:03d}", "Python")
    items, total = db.list_projects(limit=20, offset=40)
    assert total == 45
    assert len(items) == 5
