"""LLM-based signal filter for content analysis.

This is the core of SIEVE — a structured prompt that classifies content
along multiple axes and extracts knowledge nodes for ATHENA.
"""
from __future__ import annotations

import json
import re
from typing import Optional

from .models import (
    ExtractedContent, FilteredContent, Claim,
    SignalClass, ContentType
)


# ─── The Signal Filter Prompt ────────────────────────────────────────────────
# This prompt is designed to be used with Claude (Haiku for volume, Sonnet for
# precision). It asks the model to think like a skeptical domain expert who's
# seen too many LinkedIn posts.

SYSTEM_PROMPT = """You are SIEVE, a content analysis system that separates signal from noise.

You evaluate technical content — blog posts, LinkedIn posts, articles, README files —
through the lens of a skeptical domain expert. Your job is to extract what's genuinely
useful and flag what's marketing, engagement bait, or recycled conventional wisdom.

Your evaluation framework:

SIGNAL INDICATORS (increase score):
- Specific technical details (code, math, architecture decisions)
- Evidence from direct experience ("I built X and found Y")
- Quantified results with methodology
- Novel connections between domains
- Honest acknowledgment of limitations
- References to verifiable sources
- Counterintuitive findings backed by evidence

NOISE INDICATORS (decrease score):
- Dramatic pacing for engagement ("What happened next shocked me")
- Vague superlatives ("game-changing", "revolutionary", "mind-blowing")
- Claims without evidence or methodology
- Recycled obvious insights presented as novel
- Self-promotional framing disguised as education
- "Thought leader" rhetorical patterns
- Engagement bait questions at the end
- Excessive emoji or formatting tricks
- Name-dropping without substance
- Consultant-speak that sounds impressive but says nothing specific
- Recycling well-known frameworks/acronyms as if they're original thinking (e.g. naming your obvious process "The XYZ Framework™")

CONTEXT MATTERS:
- A simple demo CAN be high signal if it honestly states its limitations
- Marketing IS the content for some posts — classify accurately, don't moralize
- Personal experience is valid evidence when labeled as such
- "I don't know" or "this is limited" are positive signals, not negative ones

Respond ONLY with valid JSON. No markdown, no preamble, no backticks."""


def build_filter_prompt(content: ExtractedContent) -> str:
    """Build the user prompt for content analysis."""
    return f"""Analyze this content and respond with a JSON object.

SOURCE: {content.source_type.value}
URL: {content.url}
TITLE: {content.title}
AUTHOR: {content.author or "Unknown"}
DATE: {content.date or "Unknown"}
WORD COUNT: {content.word_count}

--- CONTENT START ---
{content.text[:8000]}
--- CONTENT END ---

Return this exact JSON structure:
{{
  "signal_class": "high_signal" | "moderate_signal" | "low_signal" | "noise",
  "signal_score": 0.0 to 1.0,
  "summary": "2-3 sentences of actual substance only. No meta-commentary.",
  "key_claims": [
    {{
      "statement": "The specific claim made",
      "evidence_type": "anecdotal" | "data" | "expert_opinion" | "logical_argument" | "none",
      "confidence": "high" | "medium" | "low",
      "verifiable": true | false
    }}
  ],
  "novel_insights": ["Things that are genuinely new or non-obvious"],
  "open_questions": ["Questions this content raises but doesn't answer"],
  "related_domains": ["Technical domains this touches"],
  "marketing_patterns": ["Specific BS patterns detected, with quotes"],
  "engagement_bait": ["LinkedIn-style hooks detected"],
  "unsubstantiated_claims": ["Claims made without supporting evidence"],
  "knowledge_nodes": [
    {{
      "concept": "Core concept name",
      "type": "tool" | "method" | "claim" | "architecture" | "finding" | "person" | "project",
      "description": "Brief factual description",
      "connections": ["Related concepts this links to"],
      "source_quality": "high" | "medium" | "low"
    }}
  ],
  "connections_to_existing": ["Known concepts/tools this connects to (e.g. MCP, Claude Code, Simulink)"]
}}"""


def parse_filter_response(
    response_text: str,
    content: ExtractedContent,
) -> FilteredContent:
    """Parse the LLM response into a FilteredContent object.

    Parsing chain: json.loads → strip markdown fences + retry → regex
    extract {…} → ValueError. Three tries before giving up — Haiku
    occasionally wraps JSON in preamble text.
    """
    cleaned = response_text.strip()

    # Attempt 1: direct parse
    data = _try_json_loads(cleaned)

    # Attempt 2: strip markdown code fences and retry
    if data is None:
        stripped = re.sub(r'^```(?:json)?\s*', '', cleaned)
        stripped = re.sub(r'\s*```$', '', stripped)
        data = _try_json_loads(stripped)

    # Attempt 3: regex fallback — find first {…} block
    if data is None:
        match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if match:
            data = _try_json_loads(match.group())

    if data is None:
        raise ValueError(f"Could not parse LLM response as JSON: {cleaned[:200]}")

    # Parse claims
    claims = []
    for c in data.get("key_claims", []):
        claims.append(Claim(
            statement=c.get("statement", ""),
            evidence_type=c.get("evidence_type", "none"),
            confidence=c.get("confidence", "low"),
            verifiable=c.get("verifiable", False),
        ))

    # Map signal class — unknown values fall back to LOW_SIGNAL
    signal_map = {
        "high_signal": SignalClass.HIGH_SIGNAL,
        "moderate_signal": SignalClass.MODERATE_SIGNAL,
        "low_signal": SignalClass.LOW_SIGNAL,
        "noise": SignalClass.NOISE,
    }
    signal_class = signal_map.get(
        data.get("signal_class", "low_signal"),
        SignalClass.LOW_SIGNAL,
    )

    return FilteredContent(
        url=content.url,
        title=content.title,
        author=content.author,
        date=content.date,
        source_type=content.source_type,
        signal_class=signal_class,
        signal_score=float(data.get("signal_score", 0.0)),
        summary=data.get("summary", ""),
        key_claims=claims,
        novel_insights=data.get("novel_insights", []),
        open_questions=data.get("open_questions", []),
        related_domains=data.get("related_domains", []),
        marketing_patterns=data.get("marketing_patterns", []),
        engagement_bait=data.get("engagement_bait", []),
        unsubstantiated_claims=data.get("unsubstantiated_claims", []),
        knowledge_nodes=data.get("knowledge_nodes", []),
        connections_to_existing=data.get("connections_to_existing", []),
    )


def _try_json_loads(text: str) -> Optional[dict]:
    """Try to parse JSON, return None on failure."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None


# ─── Convenience: run filter with anthropic SDK ─────────────────────────────

def filter_with_claude(
    content: ExtractedContent,
    model: str = "claude-haiku-4-5-20251001",
    api_key: Optional[str] = None,
) -> FilteredContent:
    """Run the signal filter using the Anthropic API.

    Uses Haiku by default for cost efficiency on high-volume filtering.
    For high-stakes single-article analysis where classification precision
    matters more than cost, pass model="claude-sonnet-4-6" instead.
    """
    try:
        import anthropic
    except ImportError:
        raise ImportError("pip install anthropic")

    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": build_filter_prompt(content),
        }],
    )

    response_text = response.content[0].text
    return parse_filter_response(response_text, content)
