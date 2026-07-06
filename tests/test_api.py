"""End-to-end API tests via FastAPI TestClient."""

import pytest
from fastapi.testclient import TestClient

from dcp.api import create_app
from dcp.config import Settings


@pytest.fixture
def client(tmp_path, sample_tree):
    settings = Settings(
        db_path=str(tmp_path / "api_fabric.db"),
        scan_root=str(sample_tree),
        ai_enabled=False,
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_scan_then_paginated_listing(client, sample_tree):
    res = client.post(
        "/api/projects/scan", params={"path": str(sample_tree), "wait": True}
    )
    assert res.status_code == 200
    assert res.json()["found"] >= 3

    res = client.get("/api/projects", params={"page": 1, "page_size": 2})
    body = res.json()
    assert res.status_code == 200
    assert len(body["items"]) == 2
    assert body["total"] >= 3
    assert body["page"] == 1

    # Second page returns the remainder, no overlap.
    res2 = client.get("/api/projects", params={"page": 2, "page_size": 2})
    paths1 = {p["path"] for p in body["items"]}
    paths2 = {p["path"] for p in res2.json()["items"]}
    assert paths1.isdisjoint(paths2)


def test_scan_rejects_bad_path(client):
    res = client.post("/api/projects/scan", params={"path": "Z:/definitely/missing"})
    assert res.status_code == 400


def test_async_scan_reports_status_and_registers_projects(client, sample_tree):
    import time

    res = client.post("/api/projects/scan", params={"path": str(sample_tree)})
    assert res.status_code == 200
    body = res.json()
    assert "running" in body and body["root"] == str(sample_tree)

    # Poll until the background scan finishes (well under a second here).
    for _ in range(50):
        status = client.get("/api/projects/scan/status").json()
        if not status["running"]:
            break
        time.sleep(0.1)
    assert status["running"] is False
    assert status["error"] is None
    assert status["found"] >= 3
    assert status["finished_at"] is not None

    # Projects registered incrementally are visible in the listing.
    assert client.get("/api/projects").json()["total"] >= 3


def test_project_search_filter(client, sample_tree):
    client.post(
        "/api/projects/scan", params={"path": str(sample_tree), "wait": True}
    )
    res = client.get("/api/projects", params={"search": "py_proj"})
    body = res.json()
    assert body["total"] == 1
    assert body["items"][0]["type"] == "Python"


def test_genome_stage_context_endpoints(client, sample_tree):
    py_proj = str(sample_tree / "py_proj")

    genome = client.get("/api/projects/genome", params={"path": py_proj}).json()
    assert genome["type"] == "Python"
    assert genome["has_tests"] is True

    stage = client.get("/api/projects/stage", params={"path": py_proj}).json()
    assert stage["stage"] in {"R&D", "Development", "Deployed", "Dormant"}
    assert 0.0 <= stage["confidence"] <= 1.0

    prompt = client.get(
        "/api/projects/context", params={"path": py_proj, "as_prompt": True}
    ).json()
    assert "Project Context" in prompt["prompt"]


def test_trinity_endpoints_paginate(client, sample_tree):
    client.post(
        "/api/projects/scan", params={"path": str(sample_tree), "wait": True}
    )
    for kind in ("signals", "inferences", "decisions"):
        res = client.get(f"/api/{kind}", params={"page": 1, "page_size": 5})
        assert res.status_code == 200
        body = res.json()
        assert {"items", "page", "page_size", "total"} <= set(body)


def test_agents_list_and_offline_run(client, sample_tree):
    agents = client.get("/api/agents").json()["agents"]
    names = {a["name"] for a in agents}
    assert {"health-check", "advisor"} <= names

    res = client.post(
        "/api/agents/run",
        json={"agent": "health-check", "path": str(sample_tree / "py_proj")},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["agent"] == "health-check"
    assert body["recommendations"]


def test_advisor_falls_back_when_ai_disabled(client, sample_tree):
    res = client.post(
        "/api/agents/run",
        json={"agent": "advisor", "path": str(sample_tree / "py_proj")},
    )
    # Router falls back to tier 0 instead of failing.
    assert res.status_code == 200
    assert res.json()["agent"] == "health-check"


def test_analysis_endpoints(client, sample_tree):
    import time

    client.post(
        "/api/projects/scan", params={"path": str(sample_tree), "wait": True}
    )

    res = client.post("/api/analysis/start", json={})
    assert res.status_code == 200
    for _ in range(100):
        status = client.get("/api/analysis/status").json()
        if not status["running"]:
            break
        time.sleep(0.1)
    assert status["running"] is False
    assert status["done"] >= 3

    # Listing now carries status columns.
    items = client.get("/api/projects").json()["items"]
    assert all(p["status_headline"] for p in items)
    assert all(p["status_health"] in ("green", "yellow", "red") for p in items)

    # Report readable via API.
    py_proj = str(sample_tree / "py_proj")
    report = client.get("/api/analysis/report", params={"path": py_proj})
    assert report.status_code == 200
    assert "Project Status" in report.text


def test_analyze_single_project(client, sample_tree):
    py_proj = str(sample_tree / "py_proj")
    res = client.post("/api/analysis/project", params={"path": py_proj})
    assert res.status_code == 200
    body = res.json()
    assert body["headline"]
    assert body["health"] in ("green", "yellow", "red")
    assert (sample_tree / "py_proj" / "project_status.md").is_file()


def test_ui_served_at_root(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "Developer Control Plane" in res.text
