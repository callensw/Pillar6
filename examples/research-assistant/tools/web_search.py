"""Web search tool — mock implementation for the reference app.

To use a real search API, replace the body of ``web_search`` with a call to
Tavily (https://tavily.com), SerpAPI (https://serpapi.com), or any other
search provider.  The function signature should stay the same.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_DATA_FILE = Path(__file__).parent / "search_data.json"
_CACHE: list[dict[str, Any]] | None = None


def _load_data() -> list[dict[str, Any]]:
    global _CACHE  # noqa: PLW0603
    if _CACHE is None:
        _CACHE = json.loads(_DATA_FILE.read_text(encoding="utf-8"))
    return _CACHE


async def web_search(query: str) -> list[dict[str, str]]:
    """Search the web for a query and return matching results.

    Args:
        query: The search query string.

    Returns:
        List of dicts with ``title``, ``url``, and ``snippet`` keys.
    """
    data = _load_data()
    query_lower = query.lower()
    query_words = set(query_lower.split())

    scored: list[tuple[int, dict[str, str]]] = []
    for entry in data:
        keywords: list[str] = entry.get("keywords", [])
        score = sum(1 for kw in keywords if kw in query_lower)
        score += sum(1 for w in query_words if w in entry["title"].lower())
        if score > 0:
            scored.append(
                (
                    score,
                    {
                        "title": entry["title"],
                        "url": entry["url"],
                        "snippet": entry["snippet"],
                    },
                )
            )

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:5]]
