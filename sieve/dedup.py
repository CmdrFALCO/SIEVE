"""Content deduplication via fingerprinting.

Uses MinHash-style fingerprinting to detect near-duplicate content across
multiple runs. This prevents ATHENA from ingesting the same insight
from slightly different versions of the same post (e.g. cross-posted
LinkedIn → Medium → blog).
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Optional


def _normalize_text(text: str) -> str:
    """Normalize text for fingerprinting — lowercase, strip formatting."""
    t = text.lower()
    t = re.sub(r'[^\w\s]', '', t)        # Remove punctuation
    t = re.sub(r'\s+', ' ', t).strip()    # Collapse whitespace
    return t


def _shingle(text: str, n: int = 5) -> set[str]:
    """Generate n-grams (shingles) from normalized text."""
    words = text.split()
    if len(words) < n:
        return {" ".join(words)}
    return {" ".join(words[i:i+n]) for i in range(len(words) - n + 1)}


def content_fingerprint(text: str) -> str:
    """Generate a 16-char hex fingerprint for content text.

    Uses hash of normalized shingles. Two posts with >80% shingle
    overlap are considered duplicates.
    """
    normalized = _normalize_text(text)
    shingles = _shingle(normalized, n=5)
    # Hash each shingle and take min-hash signature
    hashes = sorted(sha256(s.encode()).hexdigest()[:8] for s in shingles)
    # Take first 20 hashes as the fingerprint
    sig = "|".join(hashes[:20])
    return sha256(sig.encode()).hexdigest()[:16]


def jaccard_similarity(text_a: str, text_b: str) -> float:
    """Compute Jaccard similarity between two texts.

    Returns 0.0 (completely different) to 1.0 (identical).
    """
    shingles_a = _shingle(_normalize_text(text_a))
    shingles_b = _shingle(_normalize_text(text_b))

    if not shingles_a or not shingles_b:
        return 0.0

    intersection = shingles_a & shingles_b
    union = shingles_a | shingles_b
    return len(intersection) / len(union)


class DeduplicationStore:
    """Persistent store for content fingerprints across runs.

    Stores fingerprints with metadata to detect when the same content
    appears from different sources or is re-posted.
    """

    def __init__(self, store_path: str = "./sieve_output/.dedup_store.json"):
        self.store_path = Path(store_path)
        self.entries: dict[str, dict] = {}  # fingerprint -> metadata
        self._load()

    def _load(self) -> None:
        """Load existing store from disk."""
        if self.store_path.exists():
            try:
                data = json.loads(self.store_path.read_text(encoding="utf-8"))
                self.entries = data.get("entries", {})
            except (json.JSONDecodeError, KeyError):
                self.entries = {}

    def _save(self) -> None:
        """Persist store to disk."""
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "updated_at": datetime.now().isoformat(),
            "count": len(self.entries),
            "entries": self.entries,
        }
        self.store_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def is_duplicate(self, text: str, threshold: float = 0.8) -> Optional[dict]:
        """Check if content is a near-duplicate of something we've seen.

        Returns the matching entry metadata if duplicate, None otherwise.

        For speed, first checks exact fingerprint match, then falls back
        to Jaccard similarity against last 500 entries.
        """
        fp = content_fingerprint(text)

        # Exact fingerprint match
        if fp in self.entries:
            return self.entries[fp]

        # Jaccard similarity check against recent entries (last 500)
        recent = sorted(
            self.entries.items(),
            key=lambda x: x[1].get("seen_at", ""),
            reverse=True,
        )[:500]

        for stored_fp, meta in recent:
            stored_text = meta.get("text_preview", "")
            if stored_text and jaccard_similarity(text, stored_text) >= threshold:
                return meta

        return None

    def register(
        self,
        text: str,
        url: str = "",
        title: str = "",
        author: Optional[str] = None,
    ) -> None:
        """Register content in the dedup store."""
        fp = content_fingerprint(text)
        self.entries[fp] = {
            "url": url,
            "title": title,
            "author": author,
            "text_preview": text[:500],
            "fingerprint": fp,
            "seen_at": datetime.now().isoformat(),
        }
        self._save()

    def stats(self) -> dict:
        """Get store statistics."""
        return {
            "total_entries": len(self.entries),
            "store_path": str(self.store_path),
        }
