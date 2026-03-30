"""Configuration for the Multi-Agent Research Assistant.

All six Pillar6 pillars are configured here with role-appropriate settings
for each agent type (conductor, researcher, analyst).
"""

from __future__ import annotations

from pillar6.config.models import (
    AgentConfig,
    ContextConfig,
    EvalConfig,
    ObservabilityConfig,
    Pillar6Config,
    RouterConfig,
    SecurityConfig,
    ToolConfig,
)


def conductor_config() -> Pillar6Config:
    """Config for the Conductor (Supervisor) agent.

    - High token budget for orchestration context
    - No direct tool access (delegates to specialists)
    - Routes to Sonnet for quality orchestration
    """
    return Pillar6Config(
        context=ContextConfig(default_token_budget=8192),
        tools=ToolConfig(max_retries=0, timeout_ms=60_000),
        security=SecurityConfig(
            default_deny=True,
            enable_input_validation=True,
            enable_output_validation=False,
        ),
        router=RouterConfig(
            default_model="claude-sonnet-4-20250514",
            enable_caching=False,
        ),
        observability=ObservabilityConfig(enable_tracing=True),
        eval=EvalConfig(enable_auto_eval=False),
        agent=AgentConfig(
            agent_id="conductor",
            name="Conductor",
            system_prompt="You are a research coordinator.",
            temperature=0.3,
            max_tokens=2048,
        ),
    )


def researcher_config(agent_id: str = "researcher-1") -> Pillar6Config:
    """Config for a Researcher (ReAct) agent.

    - Moderate token budget
    - Can use web_search and read_url only
    - Routes to Haiku for cost efficiency
    """
    return Pillar6Config(
        context=ContextConfig(default_token_budget=4096),
        tools=ToolConfig(
            max_retries=3,
            timeout_ms=30_000,
            retry_base_delay_ms=500,
        ),
        security=SecurityConfig(
            default_deny=True,
            enable_input_validation=True,
            enable_output_validation=False,
        ),
        router=RouterConfig(
            default_model="claude-haiku-4-5-20251001",
            enable_caching=False,
        ),
        observability=ObservabilityConfig(enable_tracing=True),
        eval=EvalConfig(enable_auto_eval=False),
        agent=AgentConfig(
            agent_id=agent_id,
            name=f"Researcher ({agent_id})",
            system_prompt="You are a research specialist.",
            temperature=0.4,
            max_tokens=1024,
        ),
    )


def analyst_config() -> Pillar6Config:
    """Config for the Analyst (PlanExecute) agent.

    - High token budget for synthesis
    - Can use format_report and add_citation only
    - Routes to Sonnet for quality writing
    """
    return Pillar6Config(
        context=ContextConfig(default_token_budget=8192),
        tools=ToolConfig(
            max_retries=2,
            timeout_ms=30_000,
        ),
        security=SecurityConfig(
            default_deny=True,
            enable_input_validation=True,
            enable_output_validation=False,
        ),
        router=RouterConfig(
            default_model="claude-sonnet-4-20250514",
            enable_caching=False,
        ),
        observability=ObservabilityConfig(enable_tracing=True),
        eval=EvalConfig(enable_auto_eval=False),
        agent=AgentConfig(
            agent_id="analyst",
            name="Analyst",
            system_prompt="You are a research analyst and writer.",
            temperature=0.5,
            max_tokens=2048,
        ),
    )
