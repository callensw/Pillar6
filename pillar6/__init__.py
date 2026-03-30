"""Pillar6 — The production framework for agentic AI.

Six pillars. Zero guesswork.

Pillars:
    1. Context Management
    2. Tool Orchestration
    3. Security & Guardrails
    4. Efficiency & Routing
    5. Observability
    6. Testing & Evaluation
"""

from pillar6.agents.base import BaseAgent
from pillar6.config.models import Pillar6Config

__version__ = "0.1.0"
__all__ = ["BaseAgent", "Pillar6Config", "__version__"]
