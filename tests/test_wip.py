"""Tests for WIP triage: gitops helpers and /api/wip endpoints."""

import subprocess
import sys

import pytest

from dcp.agents import gitops

PY = sys.executable.replace("\\", "/")


def git(path, *args):
    subprocess.run(["git", "-C", str(path), *args], capture_output=True, check=True)


@pytest.fixture
def repo_with_remote(tmp_path):
    """Repo with WIP + a local bare 'origin' so push works offline."""
    bare = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)],
                   capture_output=True, check=True)
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "main.py").write_text("print('v1')\n")
    git(proj, "init", "-q")
    git(proj, "add", "-A")
    git(proj, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init")
    git(proj, "remote", "add", "origin", str(bare))
    # WIP: one modification + one new file
    (proj / "main.py").write_text("print('v2')\n")
    (proj / "new_feature.py").write_text("pass\n")
    return proj


def test_dirty_files_and_diff(repo_with_remote):
    files = gitops.dirty_files(str(repo_with_remote))
    assert {f["path"] for f in files} == {"main.py", "new_feature.py"}
    diff = gitops.diff_text(str(repo_with_remote))
    assert "print('v2')" in diff
    assert "new_feature.py" in diff


def test_detect_test_command_prefers_dod(tmp_path):
    proj = tmp_path / "t"
    proj.mkdir()
    (proj / "dod.yaml").write_text(
        "assertions:\n  - name: tests pass\n    type: command\n"
        "    run: echo custom-tests\n"
    )
    assert gitops.detect_test_command(str(proj)) == "echo custom-tests"


def test_run_tests_reports_pass_fail(tmp_path):
    proj = tmp_path / "r"
    proj.mkdir()
    result = gitops.run_tests(str(proj), command=f'"{PY}" -c "exit(0)"')
    assert result["ran"] and result["passed"]
    result = gitops.run_tests(str(proj), command=f'"{PY}" -c "exit(2)"')
    assert result["ran"] and not result["passed"]
    result = gitops.run_tests(str(proj))  # nothing detected in empty dir
    assert result["ran"] is False


def test_commit_wip_to_branch_and_push(repo_with_remote):
    path = str(repo_with_remote)
    branch, sha = gitops.commit_wip_to_branch(
        path, "Triage: v2 + new feature", branch="dcp/test-wip"
    )
    assert branch == "dcp/test-wip" and sha
    assert gitops.dirty_files(path) == []          # tree clean
    assert gitops.current_branch(path) == branch   # stays on new branch

    push = gitops.push_branch(path, branch)
    assert push["pushed"] is True
    assert "pr_url" not in push  # local bare remote, not GitHub

    # Branch exists on the remote.
    res = subprocess.run(
        ["git", "-C", path, "ls-remote", "--heads", "origin", branch],
        capture_output=True, text=True, check=True,
    )
    assert branch in res.stdout


def test_commit_clean_tree_rejected(repo_with_remote):
    path = str(repo_with_remote)
    gitops.commit_wip_to_branch(path, "first")
    with pytest.raises(RuntimeError, match="clean"):
        gitops.commit_wip_to_branch(path, "second")


def test_discard_all_wip(repo_with_remote):
    path = str(repo_with_remote)
    result = gitops.discard_all_wip(path)
    assert result["discarded"] == 2
    assert gitops.dirty_files(path) == []
    assert (repo_with_remote / "main.py").read_text() == "print('v1')\n"
    assert not (repo_with_remote / "new_feature.py").exists()


def test_pr_url_only_for_github(tmp_path):
    proj = tmp_path / "gh"
    proj.mkdir()
    git(proj, "init", "-q")
    git(proj, "remote", "add", "origin",
        "https://github.com/Ishuin/demo.git")
    assert gitops.github_repo_slug(str(proj)) == "Ishuin/demo"


# --------------------------------------------------------------------- API
@pytest.fixture
def client(tmp_path):
    from fastapi.testclient import TestClient

    from dcp.api import create_app
    from dcp.config import Settings

    settings = Settings(db_path=str(tmp_path / "wip_api.db"), ai_enabled=False)
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def test_wip_api_flow(client, tmp_path):
    bare = tmp_path / "api_origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)],
                   capture_output=True, check=True)
    proj = tmp_path / "api_proj"
    proj.mkdir()
    (proj / "app.py").write_text("x = 1\n")
    git(proj, "init", "-q")
    git(proj, "add", "-A")
    git(proj, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init")
    git(proj, "remote", "add", "origin", str(bare))
    (proj / "app.py").write_text("x = 2\n")

    overview = client.get("/api/wip", params={"path": str(proj)}).json()
    assert overview["files"] and overview["remote"]

    diff = client.get("/api/wip/diff", params={"path": str(proj)}).json()
    assert "x = 2" in diff["diff"]

    res = client.post("/api/wip/test",
                      json={"path": str(proj),
                            "command": f'"{PY}" -c "exit(0)"'})
    assert res.json()["passed"] is True

    # Discard requires confirmation.
    assert client.post("/api/wip/discard",
                       json={"path": str(proj)}).status_code == 400

    res = client.post("/api/wip/commit",
                      json={"path": str(proj), "message": "triage", "push": True})
    body = res.json()
    assert res.status_code == 200
    assert body["pushed"] is True and body["branch"].startswith("dcp/wip-")

    # Second commit with clean tree → 409.
    res = client.post("/api/wip/commit",
                      json={"path": str(proj), "message": "again"})
    assert res.status_code == 409

    # Non-repo path → 400.
    plain = tmp_path / "plain"
    plain.mkdir()
    assert client.get("/api/wip", params={"path": str(plain)}).status_code == 400
