"""Data models for the SIEVE content filtering pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Optional
import json


class SignalClass(str, Enum):
    """Classification of content signal quality."""
    HIGH_SIGNAL = "high_signal"        # Novel insight, evidence-backed, domain expertise
    MODERATE_SIGNAL = "moderate_signal" # Some useful info, mixed with fluff
    LOW_SIGNAL = "low_signal"          # Mostly marketing, engagement bait, recycled ideas
    NOISE = "noise"                     # Pure self-promotion, no substance


class ContentType(str, Enum):
    """Type of content source."""
    LINKEDIN_POST = "linkedin_post"
    BLOG_POST = "blog_post"
    MEDIUM_ARTICLE = "medium_article"
    GITHUB_README = "github_readme"
    ARXIV_PAPER = "arxiv_paper"
    RSS_ITEM = "rss_item"
    GENERIC_WEB = "generic_web"


@dataclass
class RawContent:
    """Raw fetched content before extraction."""
    url: str
    html: str
    fetched_at: datetime = field(default_factory=datetime.now)
    source_type: ContentType = ContentType.GENERIC_WEB
    fetch_method: str = "unknown"  # e.g. "stealthy", "fetcher", "dynamic"


@dataclass
class ExtractedContent:
    """Clean extracted content from a web page."""
    url: str
    title: str
    text: str
    author: Optional[str] = None
    date: Optional[str] = None
    source_type: ContentType = ContentType.GENERIC_WEB
    word_count: int = 0
    language: Optional[str] = None
    fetched_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        if not self.word_count and self.text:
            self.word_count = len(self.text.split())


@dataclass
class Claim:
    """A specific claim or assertion extracted from content."""
    statement: str
    evidence_type: str  # "anecdotal", "data", "expert_opinion", "logical_argument", "none"
    confidence: str     # "high", "medium", "low"
    verifiable: bool = False


@dataclass
class FilteredContent:
    """Content after LLM signal filtering."""
    url: str
    title: str
    author: Optional[str]
    date: Optional[str]
    source_type: ContentType

    # Signal classification
    signal_class: SignalClass
    signal_score: float  # 0.0 to 1.0

    # Content analysis
    summary: str                         # 2-3 sentence summary of actual substance
    key_claims: list[Claim] = field(default_factory=list)
    novel_insights: list[str] = field(default_factory=list)  # What's genuinely new here?
    open_questions: list[str] = field(default_factory=list)  # Questions this raises
    related_domains: list[str] = field(default_factory=list) # e.g. ["CAD", "AI agents", "MCP"]

    # BS detection
    marketing_patterns: list[str] = field(default_factory=list)  # Detected BS patterns
    engagement_bait: list[str] = field(default_factory=list)     # LinkedIn-style hooks
    unsubstantiated_claims: list[str] = field(default_factory=list)

    # For ATHENA
    knowledge_nodes: list[dict] = field(default_factory=list)  # Structured for graph ingestion
    connections_to_existing: list[str] = field(default_factory=list)  # Links to known concepts

    filtered_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["signal_class"] = self.signal_class.value
        d["source_type"] = self.source_type.value
        d["filtered_at"] = self.filtered_at.isoformat()
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


@dataclass
class SourceConfig:
    """Configuration for a content source to monitor."""
    name: str
    urls: list[str] = field(default_factory=list)
    feed_url: Optional[str] = None  # RSS/Atom feed
    source_type: ContentType = ContentType.GENERIC_WEB
    fetch_method: str = "fetcher"   # "fetcher", "stealthy", "dynamic"
    check_interval_hours: int = 24
    tags: list[str] = field(default_factory=list)
