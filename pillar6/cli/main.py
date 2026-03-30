"""Pillar6 CLI — project scaffolding and utilities.

Usage:
    pillar6 init <project-name>   Scaffold a new Pillar6 project.
    pillar6 version               Print the installed version.
"""

from __future__ import annotations

import pathlib
import textwrap

import typer

import pillar6

app = typer.Typer(
    name="pillar6",
    help="Pillar6 — The production framework for agentic AI.",
    add_completion=False,
)


@app.command()
def version() -> None:
    """Print the Pillar6 version."""
    typer.echo(f"pillar6 {pillar6.__version__}")


@app.command()
def init(project_name: str) -> None:
    """Scaffold a new Pillar6 agent project.

    Creates a directory with a basic agent, configuration file, and example tool.
    """
    root = pathlib.Path(project_name)
    if root.exists():
        typer.echo(f"Error: directory '{project_name}' already exists.", err=True)
        raise typer.Exit(code=1)

    root.mkdir(parents=True)

    # --- config.yaml ---
    (root / "config.yaml").write_text(
        textwrap.dedent("""\
        # Pillar6 project configuration
        agent:
          agent_id: my-agent
          name: My Agent
          model: claude-sonnet-4-20250514
          system_prompt: "You are a helpful assistant."
          max_turns: 10
        """),
        encoding="utf-8",
    )

    # --- agent.py ---
    (root / "agent.py").write_text(
        textwrap.dedent("""\
        \"\"\"Example Pillar6 agent.\"\"\"

        import asyncio

        from pillar6 import BaseAgent, Pillar6Config


        async def main() -> None:
            config = Pillar6Config()
            agent = BaseAgent(config=config)
            result = await agent.run("Hello, world!")
            print(result)


        if __name__ == "__main__":
            asyncio.run(main())
        """),
        encoding="utf-8",
    )

    # --- tools.py ---
    (root / "tools.py").write_text(
        textwrap.dedent("""\
        \"\"\"Example tool for Pillar6.\"\"\"


        async def greet(name: str) -> str:
            \"\"\"Return a greeting for the given name.\"\"\"
            return f"Hello, {name}!"


        TOOL_SCHEMA = {
            "name": "greet",
            "description": "Return a greeting for the given name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name to greet"},
                },
                "required": ["name"],
            },
        }
        """),
        encoding="utf-8",
    )

    typer.echo(f"Created project '{project_name}' with:")
    typer.echo(f"  {project_name}/config.yaml")
    typer.echo(f"  {project_name}/agent.py")
    typer.echo(f"  {project_name}/tools.py")
    typer.echo("")
    typer.echo("Get started:")
    typer.echo(f"  cd {project_name}")
    typer.echo("  python agent.py")


if __name__ == "__main__":
    app()
