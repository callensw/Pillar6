"""Pillar6 — Production infrastructure for agentic AI.

Any framework. Full visibility.

Add observability, security, cost tracking, and evaluation to any AI agent
in one line of code.  Works with LangChain, CrewAI, AutoGen, raw SDKs,
or any custom agent.

Pillars:
    1. Context Management
    2. Tool Orchestration
    3. Security & Guardrails
    4. Efficiency & Routing
    5. Observability
    6. Testing & Evaluation
"""

# Primary API — framework-agnostic wrappers
# Agent building (advanced usage)
from pillar6.agents.base import BaseAgent

# Configuration
from pillar6.config.models import Pillar6Config
from pillar6.wrappers.core import pillar6_monitor, pillar6_wrap

__version__ = "0.1.0"
__all__ = [
    "BaseAgent",
    "Pillar6Config",
    "__version__",
    "pillar6_monitor",
    "pillar6_wrap",
]
