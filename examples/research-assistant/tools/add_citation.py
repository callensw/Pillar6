"""Citation tool — real implementation."""

from __future__ import annotations

# Module-level counter for unique footnote numbering within a session.
_citation_counter: int = 0


def reset_citations() -> None:
    """Reset the citation counter (useful between research runs)."""
    global _citation_counter  # noqa: PLW0603
    _citation_counter = 0


async def add_citation(text: str, source: str) -> str:
    """Append a markdown footnote citation to the given text.

    Args:
        text: The text to annotate.
        source: The source URL for the citation.

    Returns:
        The text with a footnote reference and definition appended.
    """
    global _citation_counter  # noqa: PLW0603
    _citation_counter += 1
    ref = _citation_counter
    return f"{text} [^{ref}]\n\n[^{ref}]: {source}"
