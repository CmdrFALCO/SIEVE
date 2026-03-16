"""Tests for the SIEVE LLM signal filter."""
import json
import pytest

from sieve.models import ExtractedContent, ContentType, SignalClass, Claim
from sieve.filter_prompt import (
    SYSTEM_PROMPT,
    build_filter_prompt,
    parse_filter_response,
)


# ─── Realistic mock response based on the Molitor LinkedIn post ──────────────

MOLITOR_RESPONSE_JSON = json.dumps({
    "signal_class": "moderate_signal",
    "signal_score": 0.58,
    "summary": (
        "Molitor used Claude Code + MathWorks MCP server to generate a Simulink "
        "closed-loop control model for a nonlinear servo press (his PhD topic). "
        "The model compiled and simulated in 45 minutes without manual Simulink "
        "interaction. The honest admission that earlier CAD/PCB/AUTOSAR demos "
        "were under-complex (outside his expertise) is the most credible part."
    ),
    "key_claims": [
        {
            "statement": "Claude Code generated a working Simulink model for nonlinear position control in 45 min via 3 prompts",
            "evidence_type": "anecdotal",
            "confidence": "medium",
            "verifiable": True,
        },
        {
            "statement": "Experts using AI tools will massively outperform those who don't",
            "evidence_type": "logical_argument",
            "confidence": "low",
            "verifiable": False,
        },
    ],
    "novel_insights": [
        "MathWorks MCP server enables programmatic Simulink model creation from Claude Code",
        "Domain expertise + AI context injection is the real multiplier, not AI alone",
    ],
    "open_questions": [
        "Did the generated controller actually produce physically valid behavior?",
        "What was in the 3 prompts?",
    ],
    "related_domains": ["Simulink", "MCP", "nonlinear control", "Claude Code"],
    "marketing_patterns": [
        "Dramatic pacing: 'What happened next honestly surprised me!'",
        "Vague superlative: 'pretty mind-blowing'",
    ],
    "engagement_bait": [
        "Engagement-bait closing question targeting broad audience",
    ],
    "unsubstantiated_claims": [
        "'Barriers between idea and implementation are collapsing' — not demonstrated",
    ],
    "knowledge_nodes": [
        {
            "concept": "MathWorks MCP Server",
            "type": "tool",
            "description": "MCP server enabling Claude Code to programmatically create Simulink models",
            "connections": ["Claude Code", "Simulink", "MCP"],
            "source_quality": "medium",
        },
    ],
    "connections_to_existing": ["MCP", "Claude Code", "Simulink"],
})


MOLITOR_CONTENT = ExtractedContent(
    url="https://linkedin.com/posts/dirk-molitor/vibe-engineering-simulink",
    title="Most engineering software is about to become invisible",
    text="Molitor post about vibe engineering with Simulink and Claude Code",
    author="Dr. Dirk Alexander Molitor",
    date="2026-03",
    source_type=ContentType.LINKEDIN_POST,
)


# ─── SYSTEM_PROMPT tests ────────────────────────────────────────────────────

class TestSystemPrompt:
    def test_is_nonempty_string(self) -> None:
        assert isinstance(SYSTEM_PROMPT, str)
        assert len(SYSTEM_PROMPT) > 100

    def test_contains_signal_keyword(self) -> None:
        assert "signal" in SYSTEM_PROMPT.lower()

    def test_contains_noise_keyword(self) -> None:
        assert "noise" in SYSTEM_PROMPT.lower()

    def test_contains_json_instruction(self) -> None:
        assert "JSON" in SYSTEM_PROMPT

    def test_ends_with_json_only(self) -> None:
        assert SYSTEM_PROMPT.strip().endswith(
            "Respond ONLY with valid JSON. No markdown, no preamble, no backticks."
        )

    def test_contains_framework_noise_indicator(self) -> None:
        assert "XYZ Framework" in SYSTEM_PROMPT


# ─── build_filter_prompt tests ───────────────────────────────────────────────

class TestBuildFilterPrompt:
    def test_contains_content_text(self) -> None:
        prompt = build_filter_prompt(MOLITOR_CONTENT)
        assert "Molitor post about vibe engineering" in prompt

    def test_contains_source_metadata(self) -> None:
        prompt = build_filter_prompt(MOLITOR_CONTENT)
        assert "linkedin_post" in prompt
        assert "Dr. Dirk Alexander Molitor" in prompt

    def test_contains_json_schema(self) -> None:
        prompt = build_filter_prompt(MOLITOR_CONTENT)
        assert '"signal_class"' in prompt
        assert '"knowledge_nodes"' in prompt
        assert '"evidence_type"' in prompt

    def test_truncates_long_content(self) -> None:
        long_content = ExtractedContent(
            url="https://example.com",
            title="Long Post",
            text="word " * 10000,  # 50000 chars
        )
        prompt = build_filter_prompt(long_content)
        # Content section should be capped at 8000 chars of the text
        assert len(prompt) < 10000


# ─── parse_filter_response tests ────────────────────────────────────────────

class TestParseFilterResponse:
    def test_parses_clean_json(self) -> None:
        result = parse_filter_response(MOLITOR_RESPONSE_JSON, MOLITOR_CONTENT)
        assert result.signal_class == SignalClass.MODERATE_SIGNAL
        assert result.signal_score == 0.58
        assert result.url == MOLITOR_CONTENT.url
        assert result.title == MOLITOR_CONTENT.title
        assert result.author == MOLITOR_CONTENT.author
        assert len(result.key_claims) == 2
        assert isinstance(result.key_claims[0], Claim)
        assert result.key_claims[0].evidence_type == "anecdotal"
        assert result.key_claims[1].verifiable is False
        assert len(result.novel_insights) == 2
        assert len(result.marketing_patterns) == 2
        assert len(result.knowledge_nodes) == 1
        assert result.knowledge_nodes[0]["concept"] == "MathWorks MCP Server"

    def test_parses_markdown_fenced_json(self) -> None:
        fenced = f"```json\n{MOLITOR_RESPONSE_JSON}\n```"
        result = parse_filter_response(fenced, MOLITOR_CONTENT)
        assert result.signal_class == SignalClass.MODERATE_SIGNAL
        assert result.signal_score == 0.58

    def test_parses_json_with_preamble(self) -> None:
        with_preamble = f"Here is the analysis:\n\n{MOLITOR_RESPONSE_JSON}"
        result = parse_filter_response(with_preamble, MOLITOR_CONTENT)
        assert result.signal_class == SignalClass.MODERATE_SIGNAL

    def test_raises_on_malformed_json(self) -> None:
        with pytest.raises(ValueError, match="Could not parse"):
            parse_filter_response("This is not JSON at all", MOLITOR_CONTENT)

    def test_unknown_signal_class_falls_back_to_low(self) -> None:
        """LLM returns unexpected signal_class string like 'medium'."""
        bad_class = json.dumps({
            "signal_class": "medium",
            "signal_score": 0.5,
            "summary": "Test",
        })
        result = parse_filter_response(bad_class, MOLITOR_CONTENT)
        assert result.signal_class == SignalClass.LOW_SIGNAL

    def test_missing_optional_fields_default_empty(self) -> None:
        minimal = json.dumps({
            "signal_class": "noise",
            "signal_score": 0.1,
            "summary": "Nothing useful.",
        })
        result = parse_filter_response(minimal, MOLITOR_CONTENT)
        assert result.signal_class == SignalClass.NOISE
        assert result.key_claims == []
        assert result.novel_insights == []
        assert result.marketing_patterns == []
        assert result.knowledge_nodes == []
