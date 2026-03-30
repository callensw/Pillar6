"""Agent assembly — builds the multi-agent research team.

Creates and wires together the Conductor, Researcher, and Analyst agents
with their tools, permissions, and configurations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from config import analyst_config, conductor_config, researcher_config
from tools.add_citation import add_citation
from tools.format_report import format_report
from tools.read_url import read_url
from tools.web_search import web_search

from pillar6.agents.patterns.plan_execute import PlanExecuteAgent
from pillar6.agents.patterns.react import ReActAgent, ReActConfig
from pillar6.agents.patterns.supervisor import SupervisorAgent, SupervisorConfig

if TYPE_CHECKING:
    from pillar6.core.eval import MockLLMAdapter

# Tool schemas -----------------------------------------------------------------

WEB_SEARCH_SCHEMA: dict[str, Any] = {
    "properties": {
        "query": {"type": "string", "description": "Search query"},
    },
    "required": ["query"],
}

READ_URL_SCHEMA: dict[str, Any] = {
    "properties": {
        "url": {"type": "string", "description": "URL to read"},
    },
    "required": ["url"],
}

FORMAT_REPORT_SCHEMA: dict[str, Any] = {
    "properties": {
        "sections": {
            "type": "array",
            "description": "List of {heading, content} dicts",
        },
    },
    "required": ["sections"],
}

ADD_CITATION_SCHEMA: dict[str, Any] = {
    "properties": {
        "text": {"type": "string", "description": "Text to annotate"},
        "source": {"type": "string", "description": "Source URL"},
    },
    "required": ["text", "source"],
}


def _build_researcher(
    agent_id: str,
    llm: MockLLMAdapter | None = None,
) -> ReActAgent:
    """Build a Researcher agent with web_search and read_url tools."""
    config = researcher_config(agent_id)
    agent = ReActAgent(
        react_config=ReActConfig(max_steps=6),
        config=config,
        llm=llm,
    )
    # Register tools
    agent.tool_registry.register("web_search", web_search, WEB_SEARCH_SCHEMA)
    agent.tool_registry.register("read_url", read_url, READ_URL_SCHEMA)
    # Grant permissions
    agent.guardrails.grant_permission(agent_id, "web_search")
    agent.guardrails.grant_permission(agent_id, "read_url")
    return agent


def _build_analyst(
    llm: MockLLMAdapter | None = None,
) -> PlanExecuteAgent:
    """Build an Analyst agent with format_report and add_citation tools."""
    config = analyst_config()
    agent = PlanExecuteAgent(config=config, llm=llm)
    # Register tools
    agent.tool_registry.register("format_report", format_report, FORMAT_REPORT_SCHEMA)
    agent.tool_registry.register("add_citation", add_citation, ADD_CITATION_SCHEMA)
    # Grant permissions
    agent.guardrails.grant_permission("analyst", "format_report")
    agent.guardrails.grant_permission("analyst", "add_citation")
    return agent


def build_research_team(
    *,
    conductor_llm: MockLLMAdapter | None = None,
    researcher_llm: MockLLMAdapter | None = None,
    analyst_llm: MockLLMAdapter | None = None,
    num_researchers: int = 2,
    parallel: bool = False,
) -> SupervisorAgent:
    """Assemble the full research team.

    Args:
        conductor_llm: LLM for the conductor (or None for echo mode).
        researcher_llm: LLM shared by all researchers.
        analyst_llm: LLM for the analyst.
        num_researchers: Number of researcher agents to create.
        parallel: Whether to run specialists in parallel.

    Returns:
        A configured SupervisorAgent ready to run.
    """
    config = conductor_config()
    conductor = SupervisorAgent(
        supervisor_config=SupervisorConfig(
            execution_mode="parallel" if parallel else "sequential",
            max_specialists_per_task=num_researchers + 1,
        ),
        config=config,
        llm=conductor_llm,
    )

    # Register researchers
    for i in range(1, num_researchers + 1):
        researcher = _build_researcher(f"researcher-{i}", llm=researcher_llm)
        conductor.register_specialist(
            f"researcher-{i}",
            researcher,
            f"Web researcher #{i}: searches the web and extracts information",
        )

    # Register analyst
    analyst = _build_analyst(llm=analyst_llm)
    conductor.register_specialist(
        "analyst",
        analyst,
        "Research analyst: synthesises findings into a structured report",
    )

    return conductor
