"""SIEVE — Content Signal Filter."""

__version__ = "0.1.0"

from sieve.models import (
    SignalClass,
    ContentType,
    RawContent,
    ExtractedContent,
    Claim,
    FilteredContent,
    SourceConfig,
)
from sieve.extractor import extract_from_text, extract_from_html
from sieve.filter_prompt import SYSTEM_PROMPT, filter_with_claude
from sieve.fetcher import fetch_url, fetch_batch
from sieve.dedup import content_fingerprint, jaccard_similarity, DeduplicationStore
from sieve.athena_adapter import AthenaExporter, AthenaNode, AthenaEdge
from sieve.pipeline import SievePipeline, sieve_text, get_filter_prompt_for_text

__all__ = [
    "SignalClass",
    "ContentType",
    "RawContent",
    "ExtractedContent",
    "Claim",
    "FilteredContent",
    "SourceConfig",
    "extract_from_text",
    "extract_from_html",
    "SYSTEM_PROMPT",
    "filter_with_claude",
    "fetch_url",
    "fetch_batch",
    "content_fingerprint",
    "jaccard_similarity",
    "DeduplicationStore",
    "AthenaExporter",
    "AthenaNode",
    "AthenaEdge",
    "SievePipeline",
    "sieve_text",
    "get_filter_prompt_for_text",
]
