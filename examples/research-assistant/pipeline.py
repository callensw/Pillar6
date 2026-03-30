"""Research pipeline — runs the multi-agent research flow.

Orchestrates the full research lifecycle: create a job, run agents,
collect traces and costs, and store the result.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

logger = logging.getLogger(__name__)

from agents import build_research_team

from pillar6.core.eval import MockLLMAdapter

if TYPE_CHECKING:
    from storage import ResearchJob, Storage


def _default_mock_llms() -> tuple[MockLLMAdapter, MockLLMAdapter, MockLLMAdapter]:
    """Create mock LLMs for demo mode (no real API keys)."""
    conductor_llm = MockLLMAdapter(
        responses={
            # The conductor delegates to researchers and analyst
            "research": (
                '[{"specialist": "researcher-1", "sub_task": '
                '"Search for recent developments and key findings"}, '
                '{"specialist": "researcher-2", "sub_task": '
                '"Search for industry impact and future outlook"}, '
                '{"specialist": "analyst", "sub_task": '
                '"Synthesise all findings into a structured report"}]'
            ),
        },
        default_response=(
            '[{"specialist": "researcher-1", "sub_task": '
            '"Research the main topic"}, '
            '{"specialist": "analyst", "sub_task": '
            '"Write a summary report"}]'
        ),
    )

    researcher_llm = MockLLMAdapter(
        responses={
            "search": (
                "Thought: I need to search for information.\n"
                "Action: web_search\n"
                'Action Input: {"query": "latest developments"}'
            ),
            "Observation": (
                "Thought: I found useful information from the search "
                "results. Let me compile my findings.\n"
                "Final Answer: Based on my research, I found several key "
                "developments. The field is advancing rapidly with major "
                "breakthroughs in technology, significant market growth, "
                "and increasing global investment. Multiple sources confirm "
                "the trend toward practical applications and real-world "
                "impact."
            ),
        },
        default_response=(
            "Thought: I have gathered sufficient information.\n"
            "Final Answer: My research indicates significant progress "
            "in this area. Key findings include advancing technology, "
            "growing investment, and expanding real-world applications. "
            "Experts predict continued rapid development over the "
            "next decade."
        ),
    )

    analyst_llm = MockLLMAdapter(
        responses={
            "plan": (
                "1. Review all research findings\n"
                "2. Identify key themes and patterns\n"
                "3. Write the final report"
            ),
        },
        default_response=(
            "# Research Report\n\n"
            "## Key Findings\n\n"
            "Based on comprehensive research from multiple sources, "
            "the following key themes emerged:\n\n"
            "1. **Technological Progress**: The field is experiencing "
            "rapid advancement with significant breakthroughs.\n"
            "2. **Market Growth**: Industry analysts project substantial "
            "market expansion over the coming decade.\n"
            "3. **Global Investment**: Major public and private "
            "investments are accelerating development.\n"
            "4. **Real-World Impact**: Applications are moving from "
            "laboratory research to practical deployment.\n\n"
            "## Conclusion\n\n"
            "The evidence suggests this area will continue to be a "
            "major driver of innovation and economic growth."
        ),
    )

    return conductor_llm, researcher_llm, analyst_llm


async def run_research(
    question: str,
    storage: Storage,
    *,
    on_event: Any | None = None,
) -> ResearchJob:
    """Run a full research pipeline for the given question.

    Args:
        question: The research question.
        storage: Storage backend for persisting results.
        on_event: Optional async callback ``(job_id, event_dict) -> None``
                  for streaming real-time events.

    Returns:
        The completed ResearchJob.
    """
    job = await storage.create_job(question)
    job.status = "running"
    await storage.update_job(job)

    async def emit(event_type: str, agent: str, message: str) -> None:
        event = {
            "timestamp": time.time(),
            "agent": agent,
            "event_type": event_type,
            "message": message,
        }
        await storage.add_event(job.id, event)
        if on_event:
            await on_event(job.id, event)

    try:
        await emit("start", "conductor", f"Starting research: {question}")

        # Build the team with mock LLMs
        conductor_llm, researcher_llm, analyst_llm = _default_mock_llms()
        team = build_research_team(
            conductor_llm=conductor_llm,
            researcher_llm=researcher_llm,
            analyst_llm=analyst_llm,
            num_researchers=2,
            parallel=True,
        )

        await emit("delegation", "conductor", "Delegating to research team")

        # Run the pipeline
        result = await team.run(question)

        await emit("complete", "conductor", "Research complete")

        # Collect traces and costs
        trace_data: dict[str, Any] = {}
        cost_data: dict[str, Any] = {}
        try:
            obs = team.observability
            for wf_id in list(getattr(obs, "_completed_traces", {}).keys()):
                trace_data[wf_id] = await obs.export_trace(wf_id)
            cost_summary = await team.router.get_cost_summary()
            cost_data = cost_summary.model_dump()
        except Exception as trace_exc:
            logger.debug("Failed to collect traces/costs: %s", trace_exc)

        job.status = "complete"
        job.result = result
        job.trace = trace_data
        job.costs = cost_data
        job.completed_at = time.time()
        await storage.update_job(job)

    except Exception as exc:
        await emit("error", "conductor", f"Research failed: {exc}")
        job.status = "failed"
        job.result = f"Error: {exc}"
        job.completed_at = time.time()
        await storage.update_job(job)

    return job
