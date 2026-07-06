import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from dcp.database import EventSourcingDB  # noqa: E402


@pytest.fixture
def db(tmp_path):
    database = EventSourcingDB(str(tmp_path / "test_fabric.db"))
    yield database
    database.close()


@pytest.fixture
def sample_tree(tmp_path):
    """A fake workspace: python project, node project, nested monorepo, noise."""
    py = tmp_path / "workspace" / "py_proj"
    py.mkdir(parents=True)
    (py / "requirements.txt").write_text("fastapi\n")
    (py / "app.py").write_text("print('hi')\n")
    (py / "tests").mkdir()
    (py / "README.md").write_text("# py_proj\n")

    node = tmp_path / "workspace" / "node_proj"
    node.mkdir()
    (node / "package.json").write_text("{}")

    mono = tmp_path / "workspace" / "mono"
    mono.mkdir()
    (mono / "Cargo.toml").write_text("[package]\n")
    # Independent repo nested inside → a real monorepo member.
    sub = mono / "web"
    sub.mkdir()
    (sub / "package.json").write_text("{}")
    (sub / ".git").mkdir()
    # Manifest-only subdir → project internals, NOT a separate project.
    engine = mono / "engine"
    engine.mkdir()
    (engine / "CMakeLists.txt").write_text("project(engine)\n")

    noise = tmp_path / "workspace" / "notes"
    noise.mkdir()
    (noise / "todo.txt").write_text("nothing\n")

    return tmp_path / "workspace"
