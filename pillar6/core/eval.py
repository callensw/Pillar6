"""Testing & Evaluation pillar — eval suites, judging, and comparison.

Provides the abstract interface and a default implementation for running
evaluation datasets against agents, scoring outputs, and comparing runs.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from pillar6.config.models import EvalConfig
from pillar6.types import ComparisonReport, EvalDataset, EvalReport, EvalResult

if TYPE_CHECKING:
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


class DefaultEvalSuite(EvalSuite):
    """Default evaluation suite using exact-match scoring.

    LLM-as-judge functionality will be added in Phase 1.
    """

    def __init__(self, config: EvalConfig | None = None) -> None:
        self._config = config or EvalConfig()

    async def run_eval(self, agent: BaseAgent, dataset: EvalDataset) -> EvalReport:
        """Run each dataset item through the agent and judge the outputs."""
        results: list[EvalResult] = []
        for item in dataset.items:
            output = await agent.run(item.input)
            result = await self.judge(output, item.expected_output, item.rubric)
            results.append(result)

        avg_score = sum(r.score for r in results) / max(len(results), 1)
        pass_rate = sum(1 for r in results if r.passed) / max(len(results), 1)

        return EvalReport(
            dataset_name=dataset.name,
            results=results,
            avg_score=avg_score,
            pass_rate=pass_rate,
        )

    async def judge(self, output: str, expected: str, rubric: str | None = None) -> EvalResult:
        """Judge output using normalised exact-match comparison."""
        normalised_output = output.strip().lower()
        normalised_expected = expected.strip().lower()
        match = normalised_output == normalised_expected

        score = 1.0 if match else 0.0
        passed = score >= self._config.pass_threshold

        return EvalResult(
            score=score,
            passed=passed,
            reasoning="Exact match" if match else "No match",
        )

    async def compare(self, results_a: EvalReport, results_b: EvalReport) -> ComparisonReport:
        """Compare two evaluation reports by average score and pass rate."""
        score_diff = results_b.avg_score - results_a.avg_score
        pass_diff = results_b.pass_rate - results_a.pass_rate

        return ComparisonReport(
            report_a_name=results_a.dataset_name,
            report_b_name=results_b.dataset_name,
            score_diff=score_diff,
            pass_rate_diff=pass_diff,
            improved=score_diff > 0,
        )
