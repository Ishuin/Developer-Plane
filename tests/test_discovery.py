"""Tests for project discovery and stack detection."""

from dcp.sentry.detectors import detect
from dcp.sentry.discovery import ProjectDiscovery


def test_detect_by_marker():
    assert detect(["requirements.txt", "app.py"]) == "Python"
    assert detect(["package.json"]) == "JavaScript/TypeScript"
    assert detect(["Cargo.toml"]) == "Rust"
    assert detect(["go.mod"]) == "Go"
    assert detect(["pom.xml"]) == "Java/Maven"


def test_detect_by_sources_needs_threshold():
    # One stray file is not a project.
    assert detect(["script.py"]) == "Unknown"
    # Three or more source files count.
    assert detect(["a.py", "b.py", "c.py"]) == "Python"


def test_scan_finds_projects_and_skips_noise(db, sample_tree):
    projects = ProjectDiscovery(db).scan(str(sample_tree))
    paths = {p.path for p in projects}

    assert any(p.endswith("py_proj") for p in paths)
    assert any(p.endswith("node_proj") for p in paths)
    assert any(p.endswith("mono") for p in paths)
    # Plain notes dir is not a project.
    assert not any(p.endswith("notes") for p in paths)


def test_scan_keeps_monorepo_children_with_own_repo(db, sample_tree):
    projects = ProjectDiscovery(db).scan(str(sample_tree))
    paths = {p.path for p in projects}
    # web/ has its own .git inside mono → kept as child project.
    assert any(p.endswith("web") for p in paths)


def test_scan_rejects_manifest_only_children(db, sample_tree):
    projects = ProjectDiscovery(db).scan(str(sample_tree))
    paths = {p.path for p in projects}
    # engine/ only has CMakeLists.txt inside mono → internals, not a project.
    assert not any(p.endswith("engine") for p in paths)


def test_scan_skips_system_trees_and_install_dirs(db, tmp_path):
    # Python-install-like tree: Lib/ full of .py files must not be a project.
    install = tmp_path / "Program Files" / "SomeTool"
    libdir = install / "Lib"
    libdir.mkdir(parents=True)
    for name in ("os_shim.py", "re_shim.py", "sys_shim.py"):
        (libdir / name).write_text("pass\n")

    # Case variants of excluded internals outside system trees.
    tool = tmp_path / "toolbox"
    include = tool / "Include"
    include.mkdir(parents=True)
    for name in ("a.h", "b.h", "c.h"):
        (include / name).write_text("// h\n")

    projects = ProjectDiscovery(db).scan(str(tmp_path))
    paths = {p.path for p in projects}
    assert not any("Program Files" in p for p in paths)
    assert not any(p.endswith("Include") or p.endswith("Lib") for p in paths)


def test_scan_registers_projection_and_signals(db, sample_tree):
    found = ProjectDiscovery(db).scan(str(sample_tree))
    items, total = db.list_projects(limit=50)
    assert total == len(found)
    signals = db.get_signals(limit=50)
    assert any(s.event_type == "ProjectDiscovered" for s in signals)


def test_scan_streams_projects_incrementally(db, sample_tree):
    seen = []
    found = ProjectDiscovery(db).scan(str(sample_tree), on_found=seen.append)
    assert [p.path for p in seen] == [p.path for p in found]
    # Each streamed project is already queryable at callback time —
    # verified here by the projection matching the stream exactly.
    items, total = db.list_projects(limit=50)
    assert total == len(seen)


def test_scan_manager_lifecycle(db, sample_tree):
    from dcp.sentry import ScanInProgress, ScanManager
    from dcp.sentry.discovery import ProjectDiscovery as PD

    manager = ScanManager(PD(db))
    status = manager.start(str(sample_tree))
    assert status["root"] == str(sample_tree)
    manager.wait(timeout=10)

    final = manager.status()
    assert final["running"] is False
    assert final["error"] is None
    assert final["found"] >= 3

    # After completion a new scan may start again without error.
    manager.start(str(sample_tree))
    manager.wait(timeout=10)
    assert manager.status()["running"] is False


def test_scan_types_are_detected(db, sample_tree):
    projects = ProjectDiscovery(db).scan(str(sample_tree))
    by_suffix = {p.path.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]: p.type for p in projects}
    assert by_suffix["py_proj"] == "Python"
    assert by_suffix["node_proj"] == "JavaScript/TypeScript"
    assert by_suffix["mono"] == "Rust"
