"""Tests for SIEVE data models."""
import json
from sieve.models import (
    SignalClass,
    ContentType,
    ExtractedContent,
    Claim,
    FilteredContent,
)


class TestSignalClass:
    def test_enum_values(self) -> None:
        assert SignalClass.HIGH_SIGNAL.value == "high_signal"
        assert SignalClass.MODERATE_SIGNAL.value == "moderate_signal"
        assert SignalClass.LOW_SIGNAL.value == "low_signal"
        assert SignalClass.NOISE.value == "noise"

    def test_enum_is_str(self) -> None:
        assert isinstance(SignalClass.HIGH_SIGNAL, str)
        assert SignalClass.HIGH_SIGNAL == "high_signal"


class TestContentType:
    def test_enum_values(self) -> None:
        assert ContentType.LINKEDIN_POST.value == "linkedin_post"
        assert ContentType.BLOG_POST.value == "blog_post"
        assert ContentType.MEDIUM_ARTICLE.value == "medium_article"
        assert ContentType.GITHUB_README.value == "github_readme"
        assert ContentType.ARXIV_PAPER.value == "arxiv_paper"
        assert ContentType.RSS_ITEM.value == "rss_item"
        assert ContentType.GENERIC_WEB.value == "generic_web"


class TestExtractedContent:
    def test_word_count_auto_computed(self) -> None:
        content = ExtractedContent(
            url="https://example.com",
            title="Test",
            text="This is a test with seven words here",
        )
        assert content.word_count == 8

    def test_word_count_not_overridden(self) -> None:
        content = ExtractedContent(
            url="https://example.com",
            title="Test",
            text="This is a test",
            word_count=99,
        )
        assert content.word_count == 99

    def test_empty_text_word_count(self) -> None:
        content = ExtractedContent(
            url="https://example.com",
            title="Test",
            text="",
        )
        assert content.word_count == 0


class TestClaim:
    def test_instantiation(self) -> None:
        claim = Claim(
            statement="AI will replace all jobs",
            evidence_type="none",
            confidence="low",
            verifiable=False,
        )
        assert claim.statement == "AI will replace all jobs"
        assert claim.evidence_type == "none"
        assert claim.confidence == "low"
        assert claim.verifiable is False

    def test_default_verifiable(self) -> None:
        claim = Claim(
            statement="Test claim",
            evidence_type="data",
            confidence="high",
        )
        assert claim.verifiable is False


class TestFilteredContent:
    def _make_filtered(self) -> FilteredContent:
        return FilteredContent(
            url="https://example.com/post",
            title="Test Post",
            author="Test Author",
            date="2026-01-15",
            source_type=ContentType.BLOG_POST,
            signal_class=SignalClass.HIGH_SIGNAL,
            signal_score=0.85,
            summary="A substantive post about testing.",
            key_claims=[
                Claim(
                    statement="Testing improves quality",
                    evidence_type="data",
                    confidence="high",
                    verifiable=True,
                )
            ],
            novel_insights=["New testing approach"],
            marketing_patterns=["Uses buzzwords"],
        )

    def test_to_dict(self) -> None:
        fc = self._make_filtered()
        d = fc.to_dict()
        assert d["signal_class"] == "high_signal"
        assert d["source_type"] == "blog_post"
        assert d["signal_score"] == 0.85
        assert d["url"] == "https://example.com/post"
        assert isinstance(d["filtered_at"], str)  # ISO format string
        assert len(d["key_claims"]) == 1
        assert d["key_claims"][0]["statement"] == "Testing improves quality"

    def test_to_json(self) -> None:
        fc = self._make_filtered()
        j = fc.to_json()
        parsed = json.loads(j)
        assert parsed["signal_class"] == "high_signal"
        assert parsed["title"] == "Test Post"

    def test_to_json_ensure_ascii_false(self) -> None:
        fc = self._make_filtered()
        fc.summary = "Enthält deutsche Umlaute: äöü"
        j = fc.to_json()
        assert "äöü" in j  # Not escaped

    def test_default_lists(self) -> None:
        fc = FilteredContent(
            url="https://example.com",
            title="Test",
            author=None,
            date=None,
            source_type=ContentType.GENERIC_WEB,
            signal_class=SignalClass.NOISE,
            signal_score=0.1,
            summary="Nothing here.",
        )
        assert fc.key_claims == []
        assert fc.novel_insights == []
        assert fc.open_questions == []
        assert fc.marketing_patterns == []
        assert fc.knowledge_nodes == []
