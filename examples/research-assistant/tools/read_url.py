"""URL reader tool — mock implementation for the reference app.

To use a real URL reader, replace the body with ``httpx`` fetching + HTML
extraction (e.g. via ``trafilatura`` or ``beautifulsoup4``).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_DATA_FILE = Path(__file__).parent / "search_data.json"
_CACHE: dict[str, str] | None = None


def _load_content() -> dict[str, str]:
    global _CACHE  # noqa: PLW0603
    if _CACHE is None:
        data: list[dict[str, Any]] = json.loads(_DATA_FILE.read_text(encoding="utf-8"))
        _CACHE = {entry["url"]: entry["content"] for entry in data}
    return _CACHE


async def read_url(url: str) -> str:
    """Read and extract text content from a URL.

    Args:
        url: The URL to read.

    Returns:
        Extracted text content from the page.
    """
    content_map = _load_content()
    content = content_map.get(url)
    if content:
        return content
    return f"[Could not retrieve content from {url}]"
