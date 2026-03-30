"""Tests for the Testing & Evaluation pillar."""

from __future__ import annotations

import pytest

from pillar6.config.models import EvalConfig
from pillar6.core.eval import ChaosToolWrapper, DefaultEvalSuite, MockLLMAdapter
from pillar6.types import EvalDataset, EvalItem, EvalReport, LLMRequest, Message, Role

# --- MockLLMAdapter ---


async def test_mock_adapter_returns_configured_response() -> None:
    adapter = MockLLMAdapter(responses={"hello": "Hi there!"})
    request = LLMRequest(messages=[Message(role=Role.USER, content="hello world")])
    response = await adapter.complete(request)
    assert response.content == "Hi there!"


async def test_mock_adapter_returns_default_for_unmatched() -> None:
    adapter = MockLLMAdapter(
        responses={"specific": "matched"},
        default_response="default answer",
    )
    request = LLMRequest(messages=[Message(role=Role.USER, content="something else")])
    response = await adapter.complete(request)
    assert response.content == "default answer"


async def test_mock_adapter_usage_tracking() -> None:
    adapter = MockLLMAdapter()
    request = LLMRequest(messages=[Message(role=Role.USER, content="test input")])
    response = await adapter.complete(request)
    assert response.usage.total_tokens > 0


# --- EvalDataset ---


def test_eval_dataset_from_list() -> None:
    cases = [
        {"input": "hi", "expected_output": "hello"},
        {"input": "bye", "expected_output": "goodbye"},
    ]
    dataset = EvalDataset.from_list(cases, name="test")
    assert dataset.name == "test"
    assert len(dataset.items) == 2
    assert dataset.items[0].input == "hi"


def test_eval_dataset_from_json(tmp_path: object) -> None:
    import json
    from pathlib import Path

    p = Path(str(tmp_path)) / "data.json"
    p.write_text(json.dumps([{"input": "a", "expected_output": "b"}]))
    dataset = EvalDataset.from_json(str(p))
    assert len(dataset.items) == 1


# --- DefaultEvalSuite ---


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


async def test_judge_contains_match(suite: DefaultEvalSuite) -> None:
    result = await suite.judge("The answer is 42, obviously", "42")
    assert result.score == pytest.approx(0.8)
    assert result.passed is True


async def test_judge_no_match(suite: DefaultEvalSuite) -> None:
    result = await suite.judge("completely wrong", "totally different")
    assert result.score < 1.0


async def test_judge_similarity_score(suite: DefaultEvalSuite) -> None:
    result = await suite.judge("the cat sat on the mat", "the dog sat on the mat")
    assert 0 < result.score < 1.0
    assert "similarity" in result.reasoning.lower()


# --- run_eval ---


async def test_run_eval_exact_match(suite: DefaultEvalSuite) -> None:
    from pillar6.agents.base import BaseAgent
    from pillar6.config.models import Pillar6Config

    agent = BaseAgent(config=Pillar6Config())

    dataset = EvalDataset(
        name="test-ds",
        items=[EvalItem(input="hi", expected_output="[echo] hi")],
    )
    report = await suite.run_eval(agent, dataset)
    assert report.dataset_name == "test-ds"
    assert report.total_cases == 1
    assert report.passed == 1
    assert report.results[0].passed is True


async def test_run_eval_handles_agent_error(suite: DefaultEvalSuite) -> None:
    """Agent errors should be counted as failures, not crash the eval."""
    from unittest.mock import AsyncMock

    from pillar6.agents.base import BaseAgent
    from pillar6.config.models import Pillar6Config

    agent = BaseAgent(config=Pillar6Config())
    agent.run = AsyncMock(side_effect=RuntimeError("oops"))  # type: ignore[method-assign]

    dataset = EvalDataset(
        name="error-ds",
        items=[EvalItem(input="test", expected_output="expected")],
    )
    report = await suite.run_eval(agent, dataset)
    assert report.failed == 1
    assert report.results[0].score == 0.0


async def test_run_eval_contains_match(suite: DefaultEvalSuite) -> None:
    from pillar6.agents.base import BaseAgent
    from pillar6.config.models import Pillar6Config

    agent = BaseAgent(config=Pillar6Config())

    dataset = EvalDataset(
        name="contains-ds",
        items=[EvalItem(input="test", expected_output="echo")],
    )
    report = await suite.run_eval(agent, dataset)
    # "[echo] test" contains "echo"
    assert report.results[0].score == pytest.approx(0.8)


async def test_run_eval_duration_tracked(suite: DefaultEvalSuite) -> None:
    from pillar6.agents.base import BaseAgent
    from pillar6.config.models import Pillar6Config

    agent = BaseAgent(config=Pillar6Config())
    dataset = EvalDataset(
        name="timing",
        items=[EvalItem(input="hi", expected_output="[echo] hi")],
    )
    report = await suite.run_eval(agent, dataset)
    assert report.total_duration_ms >= 0


# --- Compare ---


async def test_compare_improved(suite: DefaultEvalSuite) -> None:
    from pillar6.types import EvalResult

    report_a = EvalReport(
        dataset_name="v1",
        avg_score=0.5,
        pass_rate=0.5,
        results=[EvalResult(score=0.3), EvalResult(score=0.7)],
    )
    report_b = EvalReport(
        dataset_name="v2",
        avg_score=0.8,
        pass_rate=0.8,
        results=[EvalResult(score=0.8), EvalResult(score=0.8)],
    )
    comparison = await suite.compare(report_a, report_b)
    assert comparison.improved is True
    assert comparison.score_diff == pytest.approx(0.3)
    assert comparison.improved_cases >= 1


async def test_compare_regressed(suite: DefaultEvalSuite) -> None:
    from pillar6.types import EvalResult

    report_a = EvalReport(
        dataset_name="v1",
        avg_score=0.9,
        pass_rate=0.9,
        results=[EvalResult(score=0.9)],
    )
    report_b = EvalReport(
        dataset_name="v2",
        avg_score=0.5,
        pass_rate=0.5,
        results=[EvalResult(score=0.5)],
    )
    comparison = await suite.compare(report_a, report_b)
    assert comparison.improved is False
    assert comparison.regressed_cases >= 1


# --- ChaosToolWrapper ---


async def test_chaos_wrapper_passes_through() -> None:
    async def my_tool(x: int) -> int:
        return x * 2

    wrapper = ChaosToolWrapper(my_tool, failure_rate=0.0, delay_rate=0.0)
    result = await wrapper(x=5)
    assert result == 10


async def test_chaos_wrapper_injects_failures() -> None:
    async def my_tool(x: int) -> int:
        return x * 2

    wrapper = ChaosToolWrapper(my_tool, failure_rate=1.0)
    with pytest.raises(RuntimeError, match="Chaos injection"):
        await wrapper(x=5)


async def test_chaos_wrapper_sync_handler() -> None:
    def sync_tool(x: int) -> int:
        return x * 3

    wrapper = ChaosToolWrapper(sync_tool, failure_rate=0.0, delay_rate=0.0)
    result = await wrapper(x=4)
    assert result == 12
