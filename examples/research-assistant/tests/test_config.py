"""Tests for research assistant configuration."""

from __future__ import annotations

import sys
from pathlib import Path

_APP_DIR = str(Path(__file__).resolve().parent.parent)
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

from config import analyst_config, conductor_config, researcher_config


class TestConfig:
    """Tests for agent configurations."""

    def test_conductor_config(self) -> None:
        cfg = conductor_config()
        assert cfg.context.default_token_budget == 8192
        assert cfg.agent.agent_id == "conductor"
        assert cfg.security.default_deny is True

    def test_researcher_config(self) -> None:
        cfg = researcher_config("researcher-1")
        assert cfg.context.default_token_budget == 4096
        assert cfg.agent.agent_id == "researcher-1"
        assert cfg.tools.max_retries == 3

    def test_analyst_config(self) -> None:
        cfg = analyst_config()
        assert cfg.context.default_token_budget == 8192
        assert cfg.agent.agent_id == "analyst"
        assert cfg.tools.max_retries == 2
