"""Tests for research assistant tools."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure the research-assistant directory is on sys.path
_APP_DIR = str(Path(__file__).resolve().parent.parent)
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

from tools.add_citation import add_citation, reset_citations
from tools.format_report import format_report
from tools.read_url import read_url
from tools.web_search import web_search


class TestWebSearch:
    """Tests for the web_search mock tool."""

    @pytest.mark.asyncio
    async def test_returns_results_for_matching_query(self) -> None:
        results = await web_search("quantum computing")
        assert len(results) > 0
        assert all("title" in r and "url" in r and "snippet" in r for r in results)

    @pytest.mark.asyncio
    async def test_returns_empty_for_unrelated_query(self) -> None:
        results = await web_search("xyzzy nonsense gibberish")
        assert results == []

    @pytest.mark.asyncio
    async def test_results_limited_to_five(self) -> None:
        results = await web_search("ai artificial intelligence climate space")
        assert len(results) <= 5

    @pytest.mark.asyncio
    async def test_climate_query_returns_climate_results(self) -> None:
        results = await web_search("climate change arctic ice")
        assert len(results) > 0
        titles = " ".join(r["title"].lower() for r in results)
        assert "climate" in titles or "arctic" in titles or "carbon" in titles


class TestReadUrl:
    """Tests for the read_url mock tool."""

    @pytest.mark.asyncio
    async def test_returns_content_for_known_url(self) -> None:
        content = await read_url("https://example.com/quantum-error-correction-2025")
        assert "quantum" in content.lower()
        assert len(content) > 100

    @pytest.mark.asyncio
    async def test_returns_error_for_unknown_url(self) -> None:
        content = await read_url("https://example.com/nonexistent-page")
        assert "Could not retrieve" in content


class TestFormatReport:
    """Tests for the format_report tool."""

    @pytest.mark.asyncio
    async def test_formats_sections(self) -> None:
        sections = [
            {"heading": "Introduction", "content": "This is the intro."},
            {"heading": "Findings", "content": "Key findings here."},
        ]
        report = await format_report(sections)
        assert "# Research Report" in report
        assert "## Introduction" in report
        assert "## Findings" in report
        assert "Table of Contents" in report

    @pytest.mark.asyncio
    async def test_empty_sections(self) -> None:
        report = await format_report([])
        assert "No content provided" in report


class TestAddCitation:
    """Tests for the add_citation tool."""

    @pytest.mark.asyncio
    async def test_adds_footnote(self) -> None:
        reset_citations()
        result = await add_citation("Some fact.", "https://example.com")
        assert "[^1]" in result
        assert "https://example.com" in result

    @pytest.mark.asyncio
    async def test_increments_counter(self) -> None:
        reset_citations()
        r1 = await add_citation("First.", "https://a.com")
        r2 = await add_citation("Second.", "https://b.com")
        assert "[^1]" in r1
        assert "[^2]" in r2
