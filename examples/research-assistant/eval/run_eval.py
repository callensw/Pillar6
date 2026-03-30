#!/usr/bin/env python3
"""Evaluation runner for the Research Assistant.

Runs the research pipeline against a dataset of questions and scores the
outputs using Pillar6's EvalSuite.

Usage:
    cd examples/research-assistant
    PYTHONPATH=../../:. python eval/run_eval.py
    PYTHONPATH=../../:. python eval/run_eval.py --dataset eval/dataset.json
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Ensure app root is on path
_APP_DIR = str(Path(__file__).resolve().parent.parent)
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

from pipeline import run_research
from storage import InMemoryStorage

from pillar6.core.eval import DefaultEvalSuite
from pillar6.types import EvalDataset


class _ResearchAgent:
    """Adapter that wraps the research pipeline as a callable for EvalSuite."""

    def __init__(self) -> None:
        self.storage = InMemoryStorage()

    async def run(self, task: str) -> str:
        """Run a research question and return the result text."""
        job = await run_research(task, self.storage)
        return job.result


async def main(dataset_path: str) -> None:
    """Run evaluation against the dataset."""
    print(f"\nLoading dataset from {dataset_path}...")
    dataset = EvalDataset.from_json(dataset_path)
    print(f"Loaded {len(dataset.items)} evaluation cases.\n")

    suite = DefaultEvalSuite()
    agent = _ResearchAgent()

    print("Running evaluation...\n")
    report = await suite.run_eval(agent, dataset)  # type: ignore[arg-type]

    print("=" * 60)
    print("  EVALUATION REPORT")
    print("=" * 60)
    print(f"  Dataset:     {report.dataset_name}")
    print(f"  Total cases: {report.total_cases}")
    print(f"  Passed:      {report.passed}")
    print(f"  Failed:      {report.failed}")
    print(f"  Pass rate:   {report.pass_rate:.0%}")
    print(f"  Avg score:   {report.avg_score:.2f}")
    print(f"  Duration:    {report.total_duration_ms:.0f}ms")
    print("=" * 60)

    # Per-case breakdown
    print("\nPer-case results:")
    for i, (item, result) in enumerate(zip(dataset.items, report.results, strict=True), 1):
        status = "PASS" if result.passed else "FAIL"
        print(f"  {i:2d}. [{status}] score={result.score:.2f} | {item.input[:50]}...")
        if not result.passed:
            print(f"      Reason: {result.reasoning}")

    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run research assistant eval")
    parser.add_argument(
        "--dataset",
        default=str(Path(__file__).parent / "dataset.json"),
        help="Path to evaluation dataset JSON",
    )
    args = parser.parse_args()
    asyncio.run(main(args.dataset))
