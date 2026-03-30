"""Tests for the Testing & Evaluation pillar."""

from __future__ import annotations

import pytest

from pillar6.config.models import EvalConfig
from pillar6.core.eval import DefaultEvalSuite
from pillar6.types import EvalDataset, EvalItem, EvalReport


@pytest.fixture
def suite() -> DefaultEvalSuite:
    return DefaultEvalSuite(EvalConfig(pass_threshold=0.5))


async def test_judge_exact_match(suite: DefaultEvalSuite) -> None:
    result = await suite.judge("Hello", "Hello")
    assert result.score == 1.0
    assert result.passed is True


async def test_judge_case_insensitive_match(suite: DefaultEvalSuite) -> None:
    result = await suite.judge("HELLO", "hello")
    assert result.score == 1.0


async def test_judge_no_match(suite: DefaultEvalSuite) -> None:
    result = await suite.judge("Hello", "Goodbye")
    assert result.score == 0.0
    assert result.passed is False


async def test_compare_improved(suite: DefaultEvalSuite) -> None:
    report_a = EvalReport(dataset_name="v1", avg_score=0.5, pass_rate=0.5)
    report_b = EvalReport(dataset_name="v2", avg_score=0.8, pass_rate=0.8)
    comparison = await suite.compare(report_a, report_b)
    assert comparison.improved is True
    assert comparison.score_diff == pytest.approx(0.3)


async def test_compare_regressed(suite: DefaultEvalSuite) -> None:
    report_a = EvalReport(dataset_name="v1", avg_score=0.9, pass_rate=0.9)
    report_b = EvalReport(dataset_name="v2", avg_score=0.5, pass_rate=0.5)
    comparison = await suite.compare(report_a, report_b)
    assert comparison.improved is False


async def test_run_eval_with_agent(suite: DefaultEvalSuite) -> None:
    from pillar6.agents.base import BaseAgent
    from pillar6.config.models import Pillar6Config

    agent = BaseAgent(config=Pillar6Config())

    dataset = EvalDataset(
        name="test-ds",
        items=[
            EvalItem(input="hi", expected_output="[echo] hi"),
        ],
    )
    report = await suite.run_eval(agent, dataset)
    assert report.dataset_name == "test-ds"
    assert len(report.results) == 1
    assert report.results[0].passed is True
