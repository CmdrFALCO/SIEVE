"""SIEVE Pipeline — Fetch → Extract → Filter → Output.

This is the main orchestrator. It can process:
- Raw text (e.g. pasted LinkedIn posts) — MVP path
- A single URL
- A batch of URLs

Output goes to ATHENA-compatible JSON and/or a readable markdown digest.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import (
    ExtractedContent, FilteredContent, ContentType, SignalClass
)
from .extractor import extract_content, extract_from_text
from .filter_prompt import filter_with_claude, filter_with_gemini, SYSTEM_PROMPT, build_filter_prompt
from .dedup import DeduplicationStore
from .athena_adapter import AthenaExporter


class SievePipeline:
    """Main pipeline for content filtering."""

    def __init__(
        self,
        model: str = "claude-haiku-4-5-20251001",
        api_key: Optional[str] = None,
        output_dir: str = "./sieve_output",
        min_signal: SignalClass = SignalClass.MODERATE_SIGNAL,
        dedup: bool = True,
    ):
        self.model = model
        self.api_key = api_key
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.min_signal = min_signal
        self.results: list[FilteredContent] = []

        # Deduplication
        self._dedup: Optional[DeduplicationStore] = None
        if dedup:
            self._dedup = DeduplicationStore(
                str(self.output_dir / ".dedup_store.json")
            )

        # ATHENA graph exporter
        self.athena = AthenaExporter()

    def process_url(
        self,
        url: str,
        method: str = "auto",
        source_type: Optional[ContentType] = None,
    ) -> Optional[FilteredContent]:
        """Full pipeline: fetch → extract → filter."""
        from .fetcher import fetch_url

        print(f"[SIEVE] Fetching: {url}")
        raw = fetch_url(url, method=method, source_type=source_type)
        if not raw:
            print(f"[SIEVE] Fetch failed: {url}")
            return None

        print("[SIEVE] Extracting content...")
        extracted = extract_content(raw)
        if not extracted:
            print(f"[SIEVE] Extraction failed: {url}")
            return None

        return self._filter(extracted)

    def process_text(
        self,
        text: str,
        url: str = "",
        title: str = "",
        author: Optional[str] = None,
        date: Optional[str] = None,
        source_type: ContentType = ContentType.LINKEDIN_POST,
    ) -> Optional[FilteredContent]:
        """Process raw text directly (for pasted content)."""
        extracted = extract_from_text(
            text=text, url=url, title=title,
            author=author, date=date, source_type=source_type,
        )
        return self._filter(extracted)

    def process_batch(
        self,
        urls: list[str],
        method: str = "auto",
    ) -> list[FilteredContent]:
        """Process multiple URLs."""
        results = []
        for i, url in enumerate(urls):
            print(f"\n[SIEVE] ({i+1}/{len(urls)}) Processing: {url}")
            result = self.process_url(url, method=method)
            if result:
                results.append(result)
        return results

    def _filter(self, extracted: ExtractedContent) -> Optional[FilteredContent]:
        """Run the LLM signal filter."""
        print(f"[SIEVE] Filtering: {extracted.title or extracted.url}")
        print(f"         ({extracted.word_count} words, {extracted.source_type.value})")

        # Dedup check before LLM call to save cost
        if self._dedup:
            dup = self._dedup.is_duplicate(extracted.text)
            if dup:
                print(f"         ⏭ Duplicate of: {dup.get('title', dup.get('url', 'unknown'))}")
                return None

        try:
            if self.model.startswith("gemini"):
                result = filter_with_gemini(
                    content=extracted,
                    model=self.model,
                    api_key=self.api_key,
                )
            else:
                result = filter_with_claude(
                    content=extracted,
                    model=self.model,
                    api_key=self.api_key,
                )
        except Exception as e:
            print(f"[SIEVE] Filter failed: {e}")
            return None

        # Signal indicator
        indicators = {
            SignalClass.HIGH_SIGNAL: "🟢",
            SignalClass.MODERATE_SIGNAL: "🟡",
            SignalClass.LOW_SIGNAL: "🟠",
            SignalClass.NOISE: "🔴",
        }
        icon = indicators.get(result.signal_class, "⚪")
        print(f"         {icon} {result.signal_class.value} (score: {result.signal_score:.2f})")

        if result.marketing_patterns:
            print(f"         BS detected: {len(result.marketing_patterns)} patterns")

        # Register in dedup store
        if self._dedup:
            self._dedup.register(
                text=extracted.text,
                url=extracted.url,
                title=extracted.title,
                author=extracted.author,
            )

        # ATHENA ingestion
        self.athena.ingest(result)

        self.results.append(result)
        return result

    def generate_digest(self, results: Optional[list[FilteredContent]] = None) -> str:
        """Generate a readable markdown digest of filtered results."""
        items = results or self.results
        if not items:
            return "# SIEVE Digest\n\nNo content processed yet."

        lines = [
            f"# SIEVE Digest — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"\nProcessed **{len(items)}** items.\n",
        ]

        # Group by signal class
        by_class: dict[SignalClass, list[FilteredContent]] = {}
        for item in items:
            by_class.setdefault(item.signal_class, []).append(item)

        # High signal first
        for signal_class in [SignalClass.HIGH_SIGNAL, SignalClass.MODERATE_SIGNAL,
                              SignalClass.LOW_SIGNAL, SignalClass.NOISE]:
            group = by_class.get(signal_class, [])
            if not group:
                continue

            icon = {"high_signal": "🟢", "moderate_signal": "🟡",
                    "low_signal": "🟠", "noise": "🔴"}.get(signal_class.value, "⚪")

            lines.append(f"\n## {icon} {signal_class.value.replace('_', ' ').title()} ({len(group)})\n")

            for item in sorted(group, key=lambda x: x.signal_score, reverse=True):
                lines.append(f"### [{item.title or 'Untitled'}]({item.url})")
                if item.author:
                    lines.append(f"*{item.author}*" + (f" — {item.date}" if item.date else ""))
                lines.append(f"\nScore: {item.signal_score:.2f} | Domains: {', '.join(item.related_domains)}\n")
                lines.append(f"**Summary:** {item.summary}\n")

                if item.novel_insights:
                    lines.append("**Novel insights:**")
                    for insight in item.novel_insights:
                        lines.append(f"- {insight}")
                    lines.append("")

                if item.marketing_patterns:
                    lines.append("**BS patterns detected:**")
                    for pattern in item.marketing_patterns:
                        lines.append(f"- _{pattern}_")
                    lines.append("")

                if item.open_questions:
                    lines.append("**Open questions:**")
                    for q in item.open_questions:
                        lines.append(f"- {q}")
                    lines.append("")

                if item.knowledge_nodes:
                    lines.append("**Knowledge nodes for ATHENA:**")
                    for node in item.knowledge_nodes:
                        conns = ", ".join(node.get("connections", []))
                        lines.append(
                            f"- `{node.get('concept', '?')}` "
                            f"({node.get('type', '?')}) → {conns}"
                        )
                    lines.append("")

                lines.append("---\n")

        return "\n".join(lines)

    def save_results(
        self,
        results: Optional[list[FilteredContent]] = None,
        prefix: str = "sieve",
    ) -> tuple[Path, Path, Path]:
        """Save results as JSON, markdown digest, and ATHENA graph."""
        items = results or self.results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # JSON
        json_path = self.output_dir / f"{prefix}_{timestamp}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(
                [item.to_dict() for item in items],
                f, indent=2, ensure_ascii=False,
            )
        print(f"[SIEVE] Saved JSON: {json_path}")

        # Markdown digest
        md_path = self.output_dir / f"{prefix}_{timestamp}.md"
        digest = self.generate_digest(items)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(digest)
        print(f"[SIEVE] Saved digest: {md_path}")

        # ATHENA graph
        athena_path = self.output_dir / f"{prefix}_{timestamp}_athena.json"
        self.athena.export_json(str(athena_path))

        return json_path, md_path, athena_path


# ─── Quick-use functions ─────────────────────────────────────────────────────

def sieve_text(text: str, **kwargs) -> Optional[FilteredContent]:
    """One-liner: filter pasted text."""
    pipe = SievePipeline()
    return pipe.process_text(text, **kwargs)


def get_filter_prompt_for_text(text: str, **kwargs) -> tuple[str, str]:
    """Get the system + user prompt for manual use (e.g. in claude.ai).

    Returns (system_prompt, user_prompt) tuple that you can paste
    into any Claude interface for analysis.
    """
    extracted = extract_from_text(text, **kwargs)
    return SYSTEM_PROMPT, build_filter_prompt(extracted)
