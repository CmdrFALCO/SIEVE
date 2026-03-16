"""Tests for SIEVE extractor and pipeline."""
import os

import pytest

from sieve.models import (
    ExtractedContent, FilteredContent, ContentType, SignalClass, Claim,
)
from sieve.extractor import extract_from_text, extract_from_html
from sieve.pipeline import SievePipeline, get_filter_prompt_for_text


# ─── extract_from_text ──────────────────────────────────────────────────────

class TestExtractFromText:
    def test_creates_extracted_content(self) -> None:
        ec = extract_from_text(
            "AI is transforming engineering workflows significantly.",
            url="https://example.com",
            title="AI in Engineering",
            author="Test Author",
            date="2026-03",
        )
        assert isinstance(ec, ExtractedContent)
        assert ec.title == "AI in Engineering"
        assert ec.author == "Test Author"
        assert ec.source_type == ContentType.LINKEDIN_POST  # default

    def test_auto_word_count(self) -> None:
        ec = extract_from_text("one two three four five")
        assert ec.word_count == 5

    def test_strips_whitespace(self) -> None:
        ec = extract_from_text("  hello world  \n")
        assert ec.text == "hello world"

    def test_custom_source_type(self) -> None:
        ec = extract_from_text("content", source_type=ContentType.BLOG_POST)
        assert ec.source_type == ContentType.BLOG_POST


# ─── extract_from_html ──────────────────────────────────────────────────────

REALISTIC_HTML = """<html><head><title>Test Article</title></head><body>
<article><p>This is a detailed article about engineering tools and how they are being
transformed by artificial intelligence agents that can interact with CAD software
and simulation environments. The implications for product development workflows
are significant and deserve careful analysis.</p></article></body></html>"""


class TestExtractFromHtml:
    def test_extracts_from_valid_html(self) -> None:
        result = extract_from_html(REALISTIC_HTML, url="https://example.com/article")
        assert result is not None
        assert isinstance(result, ExtractedContent)
        assert len(result.text) > 50
        assert result.word_count > 0

    def test_returns_none_for_garbage(self) -> None:
        result = extract_from_html("<div>hi</div>")
        assert result is None

    def test_returns_none_for_empty(self) -> None:
        result = extract_from_html("")
        assert result is None


# ─── get_filter_prompt_for_text ──────────────────────────────────────────────

class TestGetFilterPromptForText:
    def test_returns_two_strings(self) -> None:
        sys_prompt, user_prompt = get_filter_prompt_for_text(
            "AI is changing engineering.", author="Test"
        )
        assert isinstance(sys_prompt, str)
        assert isinstance(user_prompt, str)
        assert len(sys_prompt) > 100
        assert len(user_prompt) > 100

    def test_user_prompt_contains_content(self) -> None:
        _, user_prompt = get_filter_prompt_for_text("Unique test content xyz123")
        assert "Unique test content xyz123" in user_prompt

    def test_system_prompt_is_sieve_prompt(self) -> None:
        from sieve.filter_prompt import SYSTEM_PROMPT
        sys_prompt, _ = get_filter_prompt_for_text("anything")
        assert sys_prompt is SYSTEM_PROMPT


# ─── SievePipeline ──────────────────────────────────────────────────────────

class TestSievePipeline:
    def test_init_creates_output_dir(self, tmp_path) -> None:
        out = tmp_path / "test_output"
        pipe = SievePipeline(output_dir=str(out))
        assert out.exists()
        assert out.is_dir()
        assert pipe.results == []

    def test_generate_digest_empty(self) -> None:
        pipe = SievePipeline()
        digest = pipe.generate_digest(results=[])
        assert "# SIEVE Digest" in digest
        assert "No content processed yet" in digest

    def test_generate_digest_with_results(self) -> None:
        pipe = SievePipeline()
        mock_result = FilteredContent(
            url="https://example.com/post",
            title="Test Post",
            author="Test Author",
            date="2026-03",
            source_type=ContentType.LINKEDIN_POST,
            signal_class=SignalClass.HIGH_SIGNAL,
            signal_score=0.85,
            summary="A substantive post about testing.",
            novel_insights=["New testing approach"],
            marketing_patterns=["Vague superlative: 'game-changing'"],
            open_questions=["Does this scale?"],
            related_domains=["testing", "AI"],
            knowledge_nodes=[{
                "concept": "Testing",
                "type": "method",
                "connections": ["CI/CD"],
            }],
        )
        digest = pipe.generate_digest(results=[mock_result])
        assert "# SIEVE Digest" in digest
        assert "🟢" in digest
        assert "Test Post" in digest
        assert "Test Author" in digest
        assert "0.85" in digest
        assert "A substantive post about testing." in digest
        assert "New testing approach" in digest
        assert "game-changing" in digest
        assert "Does this scale?" in digest
        assert "`Testing`" in digest

    def test_save_results(self, tmp_path) -> None:
        pipe = SievePipeline(output_dir=str(tmp_path))
        mock_result = FilteredContent(
            url="https://example.com",
            title="Save Test",
            author=None,
            date=None,
            source_type=ContentType.GENERIC_WEB,
            signal_class=SignalClass.NOISE,
            signal_score=0.1,
            summary="Nothing here.",
        )
        json_path, md_path, athena_path = pipe.save_results(results=[mock_result], prefix="test")
        assert json_path.exists()
        assert md_path.exists()
        assert athena_path.exists()
        assert json_path.suffix == ".json"
        assert md_path.suffix == ".md"
        assert athena_path.name.endswith("_athena.json")

        import json
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["signal_class"] == "noise"


# ─── Live API test (skipped without key) ─────────────────────────────────────

@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="No API key",
)
def test_process_text_live() -> None:
    pipe = SievePipeline()
    result = pipe.process_text(
        "Most engineering software is about to become invisible. "
        "Engineers who know how to inject the right context into AI systems "
        "will massively outperform those who don't.",
        author="Dr. Dirk Molitor",
        source_type=ContentType.LINKEDIN_POST,
    )
    assert result is not None
    assert result.signal_class in list(SignalClass)
    assert 0.0 <= result.signal_score <= 1.0
