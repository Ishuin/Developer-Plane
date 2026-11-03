"""Native development agent (propose-only).

Drop-in replacement for CodeAgentExecutor that needs no external CLI: it
drives the configured LLM (Anthropic or OpenAI-compatible, see dcp.llm)
through a tool loop limited to the project directory. It never commits;
the before/after git delta feeds the same approve/discard flow.
"""

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Callable, List

from pydantic import ValidationError

from dcp.agents.base import AgentUnavailable
from dcp.agents.executor import ExecutionOutcome, _diff_stat, _git_state
from dcp.config import Settings
from dcp.llm import build_chat_model, message_text

logger = logging.getLogger(__name__)

MAX_STEPS = 25
MAX_READ_CHARS = 20_000
MAX_WRITE_CHARS = 200_000
MAX_LIST_ENTRIES = 300
MAX_COMMAND_OUTPUT_CHARS = 6_000
COMMAND_TIMEOUT_SECONDS = 120
REPORT_LIMIT = 8_000
PROTECTED_DIRS = {".git"}
SECRET_FILE_PREFIX = ".env"
SECRET_FILE_ALLOWED = {".env.example"}
SKIPPED_DIRS = {".git", "node_modules", "__pycache__", "venv", ".venv"}
# Fixed argv per runner name: the model picks a name, never free-form arguments,
# so it cannot reach `python -c`, `npx`, `go run`, etc.
TEST_COMMANDS = {
    "pytest": [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
    "npm": ["npm", "test", "--silent"],
    "cargo": ["cargo", "test"],
    "go": ["go", "test", "./..."],
    "dotnet": ["dotnet", "test"],
    "mvn": ["mvn", "-q", "test"],
    "gradle": ["gradle", "test"],
}
# Only these variables reach child processes, so API keys are never inherited.
SAFE_ENV_NAMES = ("PATH", "SYSTEMROOT", "COMSPEC", "PATHEXT", "TEMP", "TMP",
                  "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "JAVA_HOME")

SYSTEM_PROMPT = (
    "You are a careful software engineer working inside one project directory. "
    "Use the tools to inspect files, make the smallest correct change, and run "
    "the project's tests (run_tests) when possible. Never commit or push. Stop and give a "
    "short summary when the task is done or cannot be done."
)


class ToolError(ValueError):
    """Raised when a tool call violates the sandbox or its limits."""


def _is_secret_file(path: Path) -> bool:
    """True for .env and .env.* files (the template .env.example is allowed)."""
    name = path.name.casefold()  # .ENV is the same file on case-insensitive filesystems
    return name.startswith(SECRET_FILE_PREFIX) and name not in SECRET_FILE_ALLOWED


class ProjectSandbox:
    """File and command operations confined to one project root."""

    def __init__(self, root: str):
        self.root = Path(root).resolve()

    def _resolve(self, rel: str) -> Path:
        """Resolve rel inside the root; reject escapes and protected dirs."""
        target = (self.root / rel).resolve()
        if target != self.root and self.root not in target.parents:
            raise ToolError(f"path escapes the project: {rel}")
        if PROTECTED_DIRS & set(target.relative_to(self.root).parts):
            raise ToolError(f"path is protected: {rel}")
        if _is_secret_file(target):
            raise ToolError(f"path is protected: {rel}")
        return target

    def list_files(self, rel: str = ".") -> str:
        """List files under rel (relative paths, skipping vendor dirs)."""
        base = self._resolve(rel)
        if not base.is_dir():
            raise ToolError(f"not a directory: {rel}")
        found: List[str] = []
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in SKIPPED_DIRS]
            for name in filenames:
                if _is_secret_file(Path(name)):
                    continue
                found.append(str(Path(dirpath, name).relative_to(self.root)))
                if len(found) >= MAX_LIST_ENTRIES:
                    return "\n".join(found) + "\n…(truncated)"
        return "\n".join(found) or "(empty)"

    def read_file(self, rel: str) -> str:
        """Read a text file, truncated to MAX_READ_CHARS."""
        target = self._resolve(rel)
        if not target.is_file():
            raise ToolError(f"not a file: {rel}")
        return target.read_text(encoding="utf-8", errors="replace")[:MAX_READ_CHARS]

    def write_file(self, rel: str, content: str) -> str:
        """Create or overwrite a text file."""
        if len(content) > MAX_WRITE_CHARS:
            raise ToolError("content too large")
        target = self._resolve(rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"wrote {rel} ({len(content)} chars)"

    def run_tests(self, runner: str) -> str:
        """Run a fixed test command by runner name (no shell, scrubbed env)."""
        argv = TEST_COMMANDS.get(runner)
        if argv is None:
            raise ToolError(f"unknown runner {runner!r}; choose from {sorted(TEST_COMMANDS)}")
        try:
            res = subprocess.run(
                argv, cwd=self.root, capture_output=True, text=True,
                timeout=COMMAND_TIMEOUT_SECONDS, env=_safe_env(),
            )
        except subprocess.TimeoutExpired:
            return f"timed out after {COMMAND_TIMEOUT_SECONDS}s"
        except OSError as exc:
            raise ToolError(f"cannot run command: {exc}") from exc
        out = f"exit={res.returncode}\n{res.stdout}{res.stderr}"
        return out[-MAX_COMMAND_OUTPUT_CHARS:]


def _safe_env() -> dict:
    """Minimal environment for child processes (no API keys or DCP_* config)."""
    env = {k: os.environ[k] for k in SAFE_ENV_NAMES if k in os.environ}
    env["PYTHONDONTWRITEBYTECODE"] = "1"  # keep test runs from polluting the diff
    return env


def _build_tools(sandbox: ProjectSandbox):
    """Wrap sandbox operations as LangChain tools."""
    from langchain_core.tools import StructuredTool

    def list_files(path: str = ".") -> str:
        """List files in a project directory (relative path)."""
        return sandbox.list_files(path)

    def read_file(path: str) -> str:
        """Read a text file from the project (relative path)."""
        return sandbox.read_file(path)

    def write_file(path: str, content: str) -> str:
        """Create or overwrite a file in the project with the full content."""
        return sandbox.write_file(path, content)

    def run_tests(runner: str) -> str:
        """Run the project's tests. runner is one of: pytest, npm, cargo, go, dotnet, mvn, gradle."""
        return sandbox.run_tests(runner)

    return [StructuredTool.from_function(f)
            for f in (list_files, read_file, write_file, run_tests)]


def _dispatch(tools_by_name: dict, call: dict) -> str:
    """Execute one tool call; sandbox violations become messages for the model."""
    tool = tools_by_name.get(call["name"])
    if tool is None:
        return f"unknown tool: {call['name']}"
    try:
        return str(tool.invoke(call["args"]))
    except (ToolError, ValidationError, OSError) as exc:
        return f"error: {exc}"


def _run_loop(llm, tools: list, brief: str) -> str:
    """Run the tool-calling loop; return the model's final message."""
    from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

    bound = llm.bind_tools(tools)
    by_name = {t.name: t for t in tools}
    messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=brief)]
    for _ in range(MAX_STEPS):
        reply = bound.invoke(messages)
        messages.append(reply)
        if not reply.tool_calls:
            return message_text(reply.content)
        for call in reply.tool_calls:
            messages.append(ToolMessage(
                content=_dispatch(by_name, call), tool_call_id=call["id"]))
    return f"stopped after {MAX_STEPS} steps without a final answer"


class NativeAgentExecutor:
    """Same contract as CodeAgentExecutor.execute, backed by the LLM tool loop."""

    def __init__(self, settings: Settings,
                 llm_factory: Callable = build_chat_model):
        self.settings = settings
        self._llm_factory = llm_factory

    def execute(self, project_path: str, brief: str) -> ExecutionOutcome:
        before = _git_state(project_path)
        try:
            llm = self._llm_factory(self.settings)
            report = _run_loop(llm, _build_tools(ProjectSandbox(project_path)), brief)
            exit_code = 0
        except AgentUnavailable as exc:
            exit_code, report = 1, f"native agent unavailable: {exc}"
        except Exception as exc:  # provider SDKs raise many unrelated types
            logger.exception("Native agent failed in %s", project_path)
            key = self.settings.llm_api_key
            message = f"{type(exc).__name__}: {exc}"
            exit_code = 1
            report = message.replace(key, "***") if key else message
        after = _git_state(project_path)
        changed = sorted(set(after) - set(before))
        return ExecutionOutcome(
            exit_code, report[-REPORT_LIMIT:], _diff_stat(project_path, changed), changed)
