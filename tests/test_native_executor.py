"""Native executor tests with a scripted fake chat model (no network)."""

import subprocess

import pytest
from langchain_core.messages import AIMessage

from dcp.agents.base import AgentUnavailable
from dcp.agents.native_executor import (
    NativeAgentExecutor, ProjectSandbox, ToolError, _safe_env,
)
from dcp.config import Settings


class ScriptedLLM:
    """Replays a fixed list of AIMessages, ignoring the prompt."""

    def __init__(self, replies):
        self.replies = list(replies)

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        return self.replies.pop(0)


def call(name, **args):
    return {"name": name, "args": args, "id": f"id-{name}"}


@pytest.fixture
def project(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "main.py").write_text("print('hi')\n")
    for args in (("init", "-q"), ("add", "-A"),
                 ("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "i")):
        subprocess.run(["git", "-C", str(proj), *args], capture_output=True, check=True)
    return proj


def test_agent_writes_file_and_reports_diff(project):
    llm = ScriptedLLM([
        AIMessage(content="", tool_calls=[call("write_file", path="NOTES.txt", content="x")]),
        AIMessage(content="done"),
    ])
    out = NativeAgentExecutor(Settings(), lambda s: llm).execute(str(project), "task")
    assert out.exit_code == 0 and out.report == "done"
    assert out.changed_files == ["NOTES.txt"]
    assert (project / "NOTES.txt").read_text() == "x"


def test_sandbox_blocks_escape_and_git(project):
    box = ProjectSandbox(str(project))
    with pytest.raises(ToolError):
        box.write_file("../evil.txt", "x")
    with pytest.raises(ToolError):
        box.write_file(".git/config", "x")
    with pytest.raises(ToolError):
        box.read_file("/etc/passwd")


def test_only_named_runners_allowed(project):
    box = ProjectSandbox(str(project))
    for bad in ("rm -rf /", "python -c pass", "pytest; calc"):
        with pytest.raises(ToolError):
            box.run_tests(bad)
    assert "exit=" in box.run_tests("pytest")


def test_child_env_has_no_secrets(monkeypatch):
    monkeypatch.setenv("DCP_LLM_API_KEY", "sk-secret")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secret2")
    env = _safe_env()
    assert "DCP_LLM_API_KEY" not in env and "ANTHROPIC_API_KEY" not in env


def test_tool_error_returned_to_model_not_raised(project):
    llm = ScriptedLLM([
        AIMessage(content="", tool_calls=[call("write_file", path="../x", content="x")]),
        AIMessage(content="gave up"),
    ])
    out = NativeAgentExecutor(Settings(), lambda s: llm).execute(str(project), "task")
    assert out.exit_code == 0 and out.changed_files == []


def test_missing_tool_argument_is_recoverable(project):
    llm = ScriptedLLM([
        AIMessage(content="", tool_calls=[call("write_file", path="a.txt")]),
        AIMessage(content="", tool_calls=[call("write_file", path="a.txt", content="ok")]),
        AIMessage(content="done"),
    ])
    out = NativeAgentExecutor(Settings(), lambda s: llm).execute(str(project), "task")
    assert out.exit_code == 0 and out.changed_files == ["a.txt"]


def test_unavailable_llm_fails_cleanly(project):
    def factory(_settings):
        raise AgentUnavailable("no key")

    out = NativeAgentExecutor(Settings(), factory).execute(str(project), "task")
    assert out.exit_code == 1 and "no key" in out.report


def test_step_limit(project, monkeypatch):
    monkeypatch.setattr("dcp.agents.native_executor.MAX_STEPS", 2)
    loop = AIMessage(content="", tool_calls=[call("list_files")])
    llm = ScriptedLLM([loop, loop, loop])
    out = NativeAgentExecutor(Settings(), lambda s: llm).execute(str(project), "task")
    assert "stopped after 2 steps" in out.report
