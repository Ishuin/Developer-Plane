"""Tier 1 agent: LangGraph advisory workflow.

Lazy-imports langgraph/langchain so the control plane runs fine without
them installed or configured (AI-Optional principle). The graph is a
simple three-node pipeline: summarize -> assess risks -> recommend.
"""

from typing import Any, Dict

from dcp.agents.base import Agent, AgentResult, AgentUnavailable
from dcp.config import Settings


class LangGraphAdvisorAgent(Agent):
    name = "advisor"
    tier = 1
    description = "LLM advisory workflow (LangGraph) — needs DCP_AI_ENABLED=1 and LLM credentials."

    def __init__(self, settings: Settings):
        self.settings = settings

    def _build_llm(self):
        if not self.settings.ai_enabled:
            raise AgentUnavailable("AI tier disabled (set DCP_AI_ENABLED=1)")
        if not (self.settings.llm_api_key and self.settings.llm_model):
            raise AgentUnavailable("LLM credentials missing (DCP_LLM_API_KEY / DCP_LLM_MODEL)")
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as exc:
            raise AgentUnavailable("langchain-openai not installed") from exc
        kwargs: Dict[str, Any] = {
            "model": self.settings.llm_model,
            "api_key": self.settings.llm_api_key,
            "temperature": 0.2,
        }
        if self.settings.llm_api_base:
            kwargs["base_url"] = self.settings.llm_api_base
        return ChatOpenAI(**kwargs)

    def _build_graph(self, llm):
        try:
            from langgraph.graph import END, StateGraph
        except ImportError as exc:
            raise AgentUnavailable("langgraph not installed") from exc
        from typing_extensions import TypedDict

        class AdvisorState(TypedDict, total=False):
            prompt: str
            summary: str
            risks: str
            recommendations: str

        def summarize(state: AdvisorState) -> AdvisorState:
            msg = llm.invoke(
                "Summarize this project's state in 3 sentences:\n" + state["prompt"]
            )
            return {"summary": msg.content}

        def assess(state: AdvisorState) -> AdvisorState:
            msg = llm.invoke(
                "List the top 3 risks for this project, one line each:\n"
                + state["prompt"]
            )
            return {"risks": msg.content}

        def recommend(state: AdvisorState) -> AdvisorState:
            msg = llm.invoke(
                "Given this summary and risks, give 3 concrete next actions, "
                "one line each.\nSummary: " + state.get("summary", "")
                + "\nRisks: " + state.get("risks", "")
            )
            return {"recommendations": msg.content}

        graph = StateGraph(AdvisorState)
        graph.add_node("summarize", summarize)
        graph.add_node("assess", assess)
        graph.add_node("recommend", recommend)
        graph.set_entry_point("summarize")
        graph.add_edge("summarize", "assess")
        graph.add_edge("assess", "recommend")
        graph.add_edge("recommend", END)
        return graph.compile()

    def run(self, context: Dict[str, Any]) -> AgentResult:
        from dcp.cortex.context import ContextAssembler  # local import: avoid cycle

        llm = self._build_llm()
        app = self._build_graph(llm)
        prompt = ContextAssembler.to_prompt(context)
        final = app.invoke({"prompt": prompt})
        recommendations = [
            line.strip("-• ").strip()
            for line in (final.get("recommendations") or "").splitlines()
            if line.strip()
        ]
        return AgentResult(
            agent=self.name,
            summary=final.get("summary", "").strip(),
            recommendations=recommendations,
            notes=[f"risks: {final.get('risks', '').strip()}"] if final.get("risks") else [],
        )
