"""Testing & Evaluation pillar — eval suites, judging, comparison, and chaos testing.

Provides the abstract interface and a default implementation for running
evaluation datasets against agents, scoring outputs with exact-match and
similarity heuristics, comparing runs, and injecting chaos for resilience testing.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from pillar6.adapters.base import LLMAdapter
from pillar6.config.models import EvalConfig
from pillar6.types import (
    ComparisonReport,
    EvalDataset,
    EvalReport,
    EvalResult,
    LLMRequest,
    LLMResponse,
    TokenUsage,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from pillar6.agents.base import BaseAgent

logger = logging.getLogger(__name__)


class EvalSuite(ABC):
    """Abstract base class for evaluation suites."""

    @abstractmethod
    async def run_eval(self, agent: BaseAgent, dataset: EvalDataset) -> EvalReport:
        """Run an evaluation dataset against an agent.

        Args:
            agent: The agent to evaluate.
            dataset: Dataset containing input/expected pairs.

        Returns:
            Aggregated evaluation report.
        """

    @abstractmethod
    async def judge(self, output: str, expected: str, rubric: str | None = None) -> EvalResult:
        """Judge a single output against an expected answer.

        Args:
            output: The agent's actual output.
            expected: The expected output.
            rubric: Optional rubric for scoring.

        Returns:
            Evaluation result with score and reasoning.
        """

    @abstractmethod
    async def compare(self, results_a: EvalReport, results_b: EvalReport) -> ComparisonReport:
        """Compare two evaluation reports.

        Args:
            results_a: First evaluation report.
            results_b: Second evaluation report.

        Returns:
            Comparison report detailing differences.
        """


# ---------------------------------------------------------------------------
# MockLLMAdapter
# ---------------------------------------------------------------------------


class MockLLMAdapter(LLMAdapter):
    """A mock LLM adapter that returns predetermined responses for testing.

    Args:
        responses: Dict mapping input pattern substrings to response strings.
        default_response: Response to return when no pattern matches.
    """

    def __init__(
        self,
        responses: dict[str, str] | None = None,
        default_response: str = "Mock response",
    ) -> None:
        self._responses: dict[str, str] = responses or {}
        self._default_response = default_response

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Return a predetermined response based on input matching."""
        last_user_msg = ""
        for msg in reversed(request.messages):
            if msg.role.value == "user":
                last_user_msg = msg.content
                break

        content = self._default_response
        for pattern, response in self._responses.items():
            if pattern in last_user_msg:
                content = response
                break

        return LLMResponse(
            content=content,
            model=request.model or "mock",
            usage=TokenUsage(
                prompt_tokens=len(last_user_msg.split()),
                completion_tokens=len(content.split()),
                total_tokens=len(last_user_msg.split()) + len(content.split()),
            ),
        )

    def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        """Stream is not supported for the mock adapter."""
        raise NotImplementedError("MockLLMAdapter does not support streaming")


# ---------------------------------------------------------------------------
# ChaosToolWrapper
# ---------------------------------------------------------------------------


class ChaosToolWrapper:
    """Wraps a tool handler and randomly injects failures for resilience testing.

    Args:
        handler: The original tool handler (sync or async callable).
        failure_rate: Probability (0-1) of injecting a failure per call.
        delay_ms: Additional delay (ms) to inject when not failing.
        delay_rate: Probability (0-1) of injecting a delay per call.
    """

    def __init__(
        self,
        handler: Callable[..., Any],
        failure_rate: float = 0.1,
        delay_ms: float = 500.0,
        delay_rate: float = 0.1,
    ) -> None:
        self._handler = handler
        self._failure_rate = failure_rate
        self._delay_ms = delay_ms
        self._delay_rate = delay_rate

    async def __call__(self, **kwargs: Any) -> Any:
        """Execute the wrapped handler with random chaos injection."""
        # Random failure
        if random.random() < self._failure_rate:  # noqa: S311
            raise RuntimeError("Chaos injection: random failure")

        # Random delay
        if random.random() < self._delay_rate:  # noqa: S311
            await asyncio.sleep(self._delay_ms / 1000)

        # Execute the real handler
        if asyncio.iscoroutinefunction(self._handler):
            return await self._handler(**kwargs)
        return self._handler(**kwargs)


# ---------------------------------------------------------------------------
# Default implementation
# ---------------------------------------------------------------------------


def _word_similarity(output: str, expected: str) -> float:
    """Compute a simple word-overlap similarity score between 0 and 1.

    Score = |common words| / |total unique words|
    """
    output_words = set(output.strip().lower().split())
    expected_words = set(expected.strip().lower().split())
    if not output_words and not expected_words:
        return 1.0
    union = output_words | expected_words
    if not union:
        return 0.0
    common = output_words & expected_words
    return len(common) / len(union)


class DefaultEvalSuite(EvalSuite):
    """Default evaluation suite with exact-match, contains-match, and similarity scoring.

    LLM-as-judge functionality can be plugged in by subclassing and overriding
    the ``judge()`` method to call an actual LLM.
    """

    def __init__(self, config: EvalConfig | None = None) -> None:
        self._config = config or EvalConfig()

    async def run_eval(self, agent: BaseAgent, dataset: EvalDataset) -> EvalReport:
        """Run each dataset item through the agent and judge the outputs."""
        results: list[EvalResult] = []
        start = time.monotonic()

        for item in dataset.items:
            try:
                output = await agent.run(item.input)
            except Exception as exc:
                results.append(
                    EvalResult(
                        score=0.0,
                        passed=False,
                        reasoning=f"Agent error: {exc}",
                    )
                )
                continue
            result = await self.judge(output, item.expected_output, item.rubric)
            results.append(result)

        duration = (time.monotonic() - start) * 1000
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        avg_score = sum(r.score for r in results) / max(total, 1)
        pass_rate = passed / max(total, 1)

        return EvalReport(
            dataset_name=dataset.name,
            results=results,
            avg_score=avg_score,
            pass_rate=pass_rate,
            total_cases=total,
            passed=passed,
            failed=total - passed,
            total_duration_ms=duration,
        )

    async def judge(self, output: str, expected: str, rubric: str | None = None) -> EvalResult:
        """Judge output using exact match, contains match, and word similarity.

        Scoring:
        - Exact match (case-insensitive, stripped): score = 1.0
        - Contains match (expected is a substring of output): score = 0.8
        - Otherwise: word similarity score (0-1)
        """
        norm_output = output.strip().lower()
        norm_expected = expected.strip().lower()

        if norm_output == norm_expected:
            score = 1.0
            reasoning = "Exact match"
        elif norm_expected and norm_expected in norm_output:
            score = 0.8
            reasoning = "Contains match"
        else:
            score = _word_similarity(output, expected)
            reasoning = f"Word similarity: {score:.2f}"

        passed = score >= self._config.pass_threshold

        return EvalResult(
            score=score,
            passed=passed,
            reasoning=reasoning,
        )

    async def compare(self, results_a: EvalReport, results_b: EvalReport) -> ComparisonReport:
        """Compare two evaluation reports with per-case analysis."""
        score_diff = results_b.avg_score - results_a.avg_score
        pass_diff = results_b.pass_rate - results_a.pass_rate

        improved = 0
        regressed = 0
        unchanged = 0
        min_len = min(len(results_a.results), len(results_b.results))
        for i in range(min_len):
            a_score = results_a.results[i].score
            b_score = results_b.results[i].score
            if b_score > a_score:
                improved += 1
            elif b_score < a_score:
                regressed += 1
            else:
                unchanged += 1

        return ComparisonReport(
            report_a_name=results_a.dataset_name,
            report_b_name=results_b.dataset_name,
            score_diff=score_diff,
            pass_rate_diff=pass_diff,
            improved=score_diff > 0,
            improved_cases=improved,
            regressed_cases=regressed,
            unchanged_cases=unchanged,
        )
