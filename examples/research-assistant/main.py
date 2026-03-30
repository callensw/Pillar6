"""Pillar6 Reference App: Multi-Agent Research Assistant.

Usage:
    python -m examples.main "What are the latest developments in quantum computing?"
    python -m examples.main --interactive
    python -m examples.main --serve
    python -m examples.main --serve --port 8080
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pillar6 Multi-Agent Research Assistant",
    )
    parser.add_argument(
        "question",
        nargs="?",
        default=None,
        help="Research question to investigate",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Start an interactive REPL",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Start the FastAPI server for the dashboard",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for the API server (default: 8000)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for the API server (default: 127.0.0.1)",
    )
    return parser.parse_args()


async def _run_cli(question: str) -> None:
    """Run a single research question in CLI mode."""
    from pipeline import run_research
    from storage import create_storage

    storage = create_storage()

    print(f"\n{'=' * 60}")
    print(f"  Research Question: {question}")
    print(f"{'=' * 60}\n")

    async def on_event(job_id: str, event: dict[str, Any]) -> None:
        agent = event.get("agent", "system")
        msg = event.get("message", "")
        etype = event.get("event_type", "")
        print(f"  [{agent}] ({etype}) {msg}")

    job = await run_research(question, storage, on_event=on_event)

    print(f"\n{'=' * 60}")
    print(f"  Status: {job.status}")
    print(f"{'=' * 60}\n")

    if job.result:
        print(job.result)

    # Print cost summary if available
    if job.costs and job.costs.get("total_cost_usd"):
        print(
            f"\n--- Cost: ${job.costs['total_cost_usd']:.4f} "
            f"({job.costs.get('total_tokens', 0)} tokens) ---"
        )


async def _run_interactive() -> None:
    """Run an interactive REPL."""
    from pipeline import run_research
    from storage import create_storage

    storage = create_storage()

    print("\nPillar6 Research Assistant — Interactive Mode")
    print("Type a research question, or 'quit' to exit.\n")

    while True:
        try:
            question = input("research> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not question or question.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break

        async def on_event(job_id: str, event: dict[str, Any]) -> None:
            agent = event.get("agent", "system")
            msg = event.get("message", "")
            print(f"  [{agent}] {msg}")

        job = await run_research(question, storage, on_event=on_event)
        print(f"\n{job.result}\n")


def _run_server(host: str, port: int) -> None:
    """Start the FastAPI server."""
    try:
        import uvicorn
    except ImportError:
        print(
            "Error: uvicorn is required for server mode.\nInstall with: pip install uvicorn fastapi"
        )
        sys.exit(1)

    print(f"\nStarting Pillar6 Research Assistant API at http://{host}:{port}")
    print("Dashboard API endpoints:")
    print(f"  POST http://{host}:{port}/research")
    print(f"  GET  http://{host}:{port}/research/{{job_id}}")
    print(f"  GET  http://{host}:{port}/jobs")
    print(f"  WS   ws://{host}:{port}/ws/{{job_id}}")
    print()
    uvicorn.run(
        "server:app",
        host=host,
        port=port,
        reload=True,
    )


def main() -> None:
    """Entry point for the research assistant."""
    args = _parse_args()

    if args.serve:
        _run_server(args.host, args.port)
    elif args.interactive:
        asyncio.run(_run_interactive())
    elif args.question:
        asyncio.run(_run_cli(args.question))
    else:
        print("Usage: python -m examples.main <question>")
        print("       python -m examples.main --interactive")
        print("       python -m examples.main --serve")
        sys.exit(1)


if __name__ == "__main__":
    main()
