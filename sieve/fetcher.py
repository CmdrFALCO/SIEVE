"""Web fetching layer — wraps httpx with optional scrapling upgrade.

httpx is the baseline HTTP client. Scrapling adds stealth fetching
for sites with anti-bot protection (LinkedIn, Cloudflare-protected).
When scrapling isn't installed, all methods fall back to httpx.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import httpx

from .models import RawContent, ContentType

# Detect optional scrapling
_HAS_SCRAPLING = False
try:
    from scrapling.fetchers import Fetcher, StealthyFetcher, DynamicFetcher
    _HAS_SCRAPLING = True
except ImportError:
    pass


def _detect_source_type(url: str) -> ContentType:
    """Infer content type from URL."""
    url_lower = url.lower()
    if "linkedin.com" in url_lower:
        return ContentType.LINKEDIN_POST
    elif "medium.com" in url_lower:
        return ContentType.MEDIUM_ARTICLE
    elif "github.com" in url_lower:
        return ContentType.GITHUB_README
    elif "arxiv.org" in url_lower:
        return ContentType.ARXIV_PAPER
    else:
        return ContentType.GENERIC_WEB


def fetch_url(
    url: str,
    method: str = "auto",
    source_type: Optional[ContentType] = None,
    timeout: int = 30,
) -> Optional[RawContent]:
    """Fetch a URL and return raw HTML content.

    Args:
        url: The URL to fetch.
        method: Fetching strategy:
            - "auto": Pick based on URL (stealthy for LinkedIn, fetcher for others)
            - "fetcher": Simple HTTP with browser TLS fingerprint (scrapling)
            - "stealthy": Full stealth mode with Cloudflare bypass (scrapling)
            - "dynamic": Full browser automation for JS-heavy sites (scrapling)
            - "httpx": Simple fallback (no anti-bot)
        source_type: Override automatic source type detection.
        timeout: Request timeout in seconds.

    Returns:
        RawContent or None if fetch fails.
    """
    if source_type is None:
        source_type = _detect_source_type(url)

    # Auto-select method based on target
    if method == "auto":
        if "linkedin.com" in url.lower():
            method = "stealthy"
        else:
            method = "fetcher"

    try:
        if method in ("fetcher", "stealthy", "dynamic") and _HAS_SCRAPLING:
            return _fetch_scrapling(url, method, source_type, timeout)
        else:
            return _fetch_httpx(url, source_type, timeout)
    except Exception as e:
        print(f"[SIEVE] Fetch failed for {url}: {e}")
        return None


def _fetch_scrapling(
    url: str, method: str, source_type: ContentType, timeout: int
) -> Optional[RawContent]:
    """Fetch using Scrapling."""
    if method == "stealthy":
        page = StealthyFetcher.fetch(
            url,
            headless=True,
            network_idle=True,
        )
    elif method == "dynamic":
        page = DynamicFetcher.fetch(
            url,
            headless=True,
            network_idle=True,
        )
    else:
        page = Fetcher.get(
            url,
            stealthy_headers=True,
            follow_redirects=True,
            timeout=timeout,
        )

    html = page.html_content if hasattr(page, 'html_content') else str(page)

    if not html or len(html) < 100:
        return None

    return RawContent(
        url=url,
        html=html,
        source_type=source_type,
        fetch_method=method,
    )


def _fetch_httpx(
    url: str, source_type: ContentType, timeout: int
) -> Optional[RawContent]:
    """Fetch using httpx."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
    }

    with httpx.Client(
        follow_redirects=True,
        timeout=timeout,
        headers=headers,
    ) as client:
        resp = client.get(url)
        resp.raise_for_status()

    return RawContent(
        url=url,
        html=resp.text,
        source_type=source_type,
        fetch_method="httpx",
    )


def fetch_batch(
    urls: list[str],
    method: str = "auto",
    source_type: Optional[ContentType] = None,
) -> list[RawContent]:
    """Fetch multiple URLs, skipping failures."""
    results = []
    for url in urls:
        raw = fetch_url(url, method=method, source_type=source_type)
        if raw:
            results.append(raw)
    return results
