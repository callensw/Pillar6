"""Report formatting tool — real implementation."""

from __future__ import annotations

from typing import Any


async def format_report(sections: list[dict[str, Any]]) -> str:
    """Format a list of sections into a clean markdown report.

    Args:
        sections: List of dicts with ``heading`` and ``content`` keys.

    Returns:
        A formatted markdown string with title, table of contents,
        sections, and a references placeholder.
    """
    if not sections:
        return "# Research Report\n\n*No content provided.*\n"

    lines: list[str] = []

    # Title — use the first section heading or a generic title
    title = "Research Report"
    lines.append(f"# {title}")
    lines.append("")

    # Table of contents
    lines.append("## Table of Contents")
    lines.append("")
    for i, section in enumerate(sections, 1):
        heading = section.get("heading", f"Section {i}")
        anchor = heading.lower().replace(" ", "-").replace(":", "")
        lines.append(f"{i}. [{heading}](#{anchor})")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Sections
    for section in sections:
        heading = section.get("heading", "Untitled Section")
        content = section.get("content", "")
        lines.append(f"## {heading}")
        lines.append("")
        lines.append(content)
        lines.append("")

    # References placeholder
    lines.append("---")
    lines.append("")
    lines.append("## References")
    lines.append("")
    lines.append("*See inline citations for sources.*")
    lines.append("")

    return "\n".join(lines)
