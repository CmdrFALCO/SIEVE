"""Tests for SIEVE URL fetcher."""
from sieve.fetcher import _detect_source_type, fetch_url
from sieve.models import ContentType


class TestDetectSourceType:
    def test_linkedin(self) -> None:
        assert _detect_source_type("https://www.linkedin.com/posts/someone/something") == ContentType.LINKEDIN_POST

    def test_medium(self) -> None:
        assert _detect_source_type("https://someone.medium.com/some-article") == ContentType.MEDIUM_ARTICLE

    def test_github(self) -> None:
        assert _detect_source_type("https://github.com/user/repo") == ContentType.GITHUB_README

    def test_arxiv(self) -> None:
        assert _detect_source_type("https://arxiv.org/abs/2301.00001") == ContentType.ARXIV_PAPER

    def test_generic(self) -> None:
        assert _detect_source_type("https://blog.example.com/post") == ContentType.GENERIC_WEB

    def test_case_insensitive(self) -> None:
        assert _detect_source_type("https://LINKEDIN.COM/in/someone") == ContentType.LINKEDIN_POST


class TestFetchUrl:
    def test_returns_none_for_invalid_url(self) -> None:
        result = fetch_url("http://this-domain-does-not-exist-xyz123.invalid/page")
        assert result is None

    def test_returns_none_for_garbage(self) -> None:
        result = fetch_url("not-a-url")
        assert result is None
