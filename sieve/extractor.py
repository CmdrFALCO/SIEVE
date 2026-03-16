"""Content extraction from raw HTML using trafilatura.

Trafilatura handles the hard part of extracting article text from messy HTML.
It's much better than BeautifulSoup for this because it understands article
structure, handles boilerplate removal, and extracts metadata.
"""
from __future__ import annotations

from typing import Optional

import trafilatura
from trafilatura.settings import use_config

from .models import RawContent, ExtractedContent, ContentType


def _get_trafilatura_config():
    """Get optimized trafilatura config for our use case."""
    config = use_config()
    config.set("DEFAULT", "EXTRACTION_TIMEOUT", "30")
    config.set("DEFAULT", "MIN_EXTRACTED_SIZE", "100")
    config.set("DEFAULT", "MIN_OUTPUT_SIZE", "50")
    return config


def extract_content(raw: RawContent) -> Optional[ExtractedContent]:
    """Extract clean text and metadata from raw HTML.

    Returns None if extraction fails or content is too short to be useful.
    """
    config = _get_trafilatura_config()

    result = trafilatura.extract(
        raw.html,
        url=raw.url,
        include_comments=False,
        include_tables=True,
        include_links=False,
        include_images=False,
        output_format="txt",
        config=config,
    )

    if not result or len(result.strip()) < 50:
        return None

    metadata = trafilatura.extract_metadata(raw.html, default_url=raw.url)

    title = ""
    author = None
    date = None

    if metadata:
        title = metadata.title or ""
        author = metadata.author
        date = metadata.date

    return ExtractedContent(
        url=raw.url,
        title=title,
        text=result.strip(),
        author=author,
        date=date,
        source_type=raw.source_type,
        fetched_at=raw.fetched_at,
    )


def extract_from_html(
    html: str,
    url: str = "",
    source_type: ContentType = ContentType.GENERIC_WEB,
) -> Optional[ExtractedContent]:
    """Convenience: extract directly from HTML string."""
    raw = RawContent(url=url, html=html, source_type=source_type)
    return extract_content(raw)


def extract_from_text(
    text: str,
    url: str = "",
    title: str = "",
    author: Optional[str] = None,
    date: Optional[str] = None,
    source_type: ContentType = ContentType.LINKEDIN_POST,
) -> ExtractedContent:
    """Create ExtractedContent directly from plain text.

    Useful for content that's already been extracted (e.g., pasted LinkedIn posts,
    text from screenshots, manually copied content).
    """
    return ExtractedContent(
        url=url,
        title=title,
        text=text.strip(),
        author=author,
        date=date,
        source_type=source_type,
    )
