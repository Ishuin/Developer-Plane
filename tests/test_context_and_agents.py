"""Tests for the context assembler and the agents layer."""

import pytest

from dcp.agents import HealthCheckAgent, LangGraphAdvisorAgent
from dcp.agents.base import AgentUnavailable
from dcp.config import Settings
from dcp.cortex import AgentRouter, ContextAssembler


@pytest.fixture
def assembled(db, sample_tree):
    py_proj = str(sample_tree / "py_proj")
    db.log_signal("FileChanged", {"src_path": "app.py"}, project_id=py_proj)
    return ContextAssembler(db).assemble(py_proj)


def test_context_payload_shape(assembled):
    assert set(assembled) >= {"project", "genome", "recent_signals", "recent_inferences"}
    assert assembled["genome"]["type"] == "Python"
    assert assembled["recent_signals"]


def test_context_prompt_rendering(assembled):
    prompt = ContextAssembler.to_prompt(assembled)
    assert "Project Context" in prompt
    assert "Stack: Python" in prompt
    assert "Recent activity" in prompt


def test_health_check_agent_offline(assembled):
    result = HealthCheckAgent().run(assembled)
    assert result.agent == "health-check"
    assert result.summary
    # Sample project has no git/CI → concrete recommendations expected.
    assert any("git" in r.lower() for r in result.recommendations)
    assert any("ci" in r.lower() for r in result.recommendations)


def test_langgraph_agent_unavailable_without_config(assembled):
    settings = Settings(ai_enabled=False)
    with pytest.raises(AgentUnavailable):
        LangGraphAdvisorAgent(settings).run(assembled)


def test_router_falls_back_to_tier0(db, assembled):
    router = AgentRouter(db)
    router.register(HealthCheckAgent())
    router.register(LangGraphAdvisorAgent(Settings(ai_enabled=False)))

    result = router.run("advisor", assembled)
    assert result.agent == "health-check"
    assert any("fell back" in note for note in result.notes)
    # Router logs the run as a decision.
    assert db.get_decisions()[0].decision_type == "AgentRun"


def test_router_unknown_agent_raises(db, assembled):
    router = AgentRouter(db)
    with pytest.raises(KeyError):
        router.run("nope", assembled)
