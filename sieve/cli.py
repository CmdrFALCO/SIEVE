#!/usr/bin/env python3
"""SIEVE CLI — Command-line interface for content filtering.

Usage:
    # Analyze a URL
    sieve url https://some-blog.com/post

    # Analyze pasted text
    sieve text "Most engineering software is about to become invisible..."

    # Analyze text from a file
    sieve file post.txt --author "Dr. Dirk Molitor" --source linkedin

    # Batch process URLs from a file (one per line)
    sieve batch urls.txt --output ./results

    # Generate prompt only (no API key needed)
    sieve prompt "Some text to analyze..."

    # Extract content only (no LLM)
    sieve extract https://some-blog.com/post
"""
import argparse
import json
import sys
from pathlib import Path


def cmd_url(args) -> None:
    """Process a single URL."""
    from .pipeline import SievePipeline
    pipe = SievePipeline(
        model=args.model,
        output_dir=args.output,
    )
    result = pipe.process_url(args.url, method=args.method)
    if result:
        _print_result(result, args)
        if args.save:
            pipe.save_results(prefix="url")


def cmd_text(args) -> None:
    """Process inline text."""
    from .models import ContentType
    from .pipeline import SievePipeline
    source_type = _resolve_source_type(args.source)
    pipe = SievePipeline(
        model=args.model,
        output_dir=args.output,
    )
    result = pipe.process_text(
        text=args.text,
        author=args.author,
        title=args.title or "",
        source_type=source_type,
    )
    if result:
        _print_result(result, args)
        if args.save:
            pipe.save_results(prefix="text")


def cmd_file(args) -> None:
    """Process text from a file."""
    args.text = Path(args.filepath).read_text(encoding="utf-8")
    cmd_text(args)


def cmd_batch(args) -> None:
    """Process URLs from a file."""
    from .pipeline import SievePipeline
    urls = [
        line.strip()
        for line in Path(args.filepath).read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    print(f"[SIEVE] Found {len(urls)} URLs to process")

    pipe = SievePipeline(
        model=args.model,
        output_dir=args.output,
    )
    results = pipe.process_batch(urls, method=args.method)

    print("\n" + pipe.generate_digest(results))
    pipe.save_results(results, prefix="batch")


def cmd_prompt(args) -> None:
    """Generate filter prompt for manual use (no API needed)."""
    from .pipeline import get_filter_prompt_for_text
    source_type = _resolve_source_type(args.source)

    # Read from stdin if text is "-"
    text = sys.stdin.read() if args.text == "-" else args.text

    system, user = get_filter_prompt_for_text(
        text=text,
        author=args.author,
        source_type=source_type,
    )

    if args.prompt_format == "combined":
        print("=== SYSTEM PROMPT ===")
        print(system)
        print("\n=== USER PROMPT ===")
        print(user)
    elif args.prompt_format == "json":
        print(json.dumps({
            "system": system,
            "user": user,
        }, indent=2))
    else:
        # Just the user prompt (system is static)
        print(user)


def cmd_extract(args) -> None:
    """Just extract content from a URL (no LLM filtering)."""
    from .extractor import extract_content
    from .fetcher import fetch_url

    raw = fetch_url(args.url, method="httpx")
    if not raw:
        print("Fetch failed", file=sys.stderr)
        sys.exit(1)

    result = extract_content(raw)
    if result:
        if args.format == "json":
            print(json.dumps({
                "url": result.url,
                "title": result.title,
                "author": result.author,
                "date": result.date,
                "word_count": result.word_count,
                "text": result.text,
            }, indent=2, ensure_ascii=False))
        else:
            print(f"Title: {result.title}")
            print(f"Author: {result.author}")
            print(f"Date: {result.date}")
            print(f"Words: {result.word_count}")
            print("---")
            print(result.text)
    else:
        print("Extraction failed", file=sys.stderr)
        sys.exit(1)


def _resolve_source_type(source: str):
    """Map CLI source string to ContentType enum."""
    from .models import ContentType
    source_map = {
        "linkedin": ContentType.LINKEDIN_POST,
        "blog": ContentType.BLOG_POST,
        "medium": ContentType.MEDIUM_ARTICLE,
        "github": ContentType.GITHUB_README,
        "arxiv": ContentType.ARXIV_PAPER,
    }
    return source_map.get(source, ContentType.GENERIC_WEB)


def _print_result(result, args) -> None:
    """Print a single filtered result."""
    if args.format == "json":
        print(result.to_json())
    else:
        icons = {
            "high_signal": "🟢", "moderate_signal": "🟡",
            "low_signal": "🟠", "noise": "🔴",
        }
        icon = icons.get(result.signal_class.value, "⚪")

        print(f"\n{'=' * 60}")
        print(f"{icon}  {result.signal_class.value} (score: {result.signal_score:.2f})")
        print(f"{'=' * 60}")
        print(f"Title:   {result.title}")
        print(f"Author:  {result.author or 'Unknown'}")
        print(f"Domains: {', '.join(result.related_domains)}")
        print(f"\nSummary: {result.summary}")

        if result.novel_insights:
            print("\nNovel insights:")
            for i in result.novel_insights:
                print(f"  + {i}")

        if result.marketing_patterns:
            print("\nBS patterns detected:")
            for p in result.marketing_patterns:
                print(f"  ⚠ {p}")

        if result.engagement_bait:
            print("\nEngagement bait:")
            for b in result.engagement_bait:
                print(f"  🎣 {b}")

        if result.unsubstantiated_claims:
            print("\nUnsubstantiated claims:")
            for c in result.unsubstantiated_claims:
                print(f"  ❓ {c}")

        if result.key_claims:
            print("\nKey claims:")
            for c in result.key_claims:
                ev = c.evidence_type
                conf = c.confidence
                print(f"  [{ev}/{conf}] {c.statement}")

        if result.knowledge_nodes:
            print("\nATHENA nodes:")
            for n in result.knowledge_nodes:
                conns = ", ".join(n.get("connections", []))
                print(f"  📌 {n.get('concept')} ({n.get('type')}) → {conns}")

        if result.open_questions:
            print("\nOpen questions:")
            for q in result.open_questions:
                print(f"  ? {q}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="sieve",
        description="SIEVE — Content signal filter for ATHENA",
    )
    parser.add_argument(
        "--model", default="claude-haiku-4-5-20251001",
        help="Claude model to use (default: haiku)",
    )
    parser.add_argument(
        "--output", default="./sieve_output",
        help="Output directory",
    )
    parser.add_argument(
        "--format", choices=["text", "json"], default="text",
        help="Output format",
    )

    sub = parser.add_subparsers(dest="command")

    # url
    p_url = sub.add_parser("url", help="Process a URL")
    p_url.add_argument("url")
    p_url.add_argument("--method", default="auto",
                       choices=["auto", "fetcher", "stealthy", "dynamic", "httpx"])
    p_url.add_argument("--save", action="store_true")

    # text
    p_text = sub.add_parser("text", help="Process inline text")
    p_text.add_argument("text")
    p_text.add_argument("--author", default=None)
    p_text.add_argument("--title", default=None)
    p_text.add_argument("--source", default="generic",
                        choices=["linkedin", "blog", "medium", "github", "arxiv", "generic"])
    p_text.add_argument("--save", action="store_true")

    # file
    p_file = sub.add_parser("file", help="Process text from file")
    p_file.add_argument("filepath")
    p_file.add_argument("--author", default=None)
    p_file.add_argument("--title", default=None)
    p_file.add_argument("--source", default="generic",
                        choices=["linkedin", "blog", "medium", "github", "arxiv", "generic"])
    p_file.add_argument("--save", action="store_true")

    # batch
    p_batch = sub.add_parser("batch", help="Process URLs from file")
    p_batch.add_argument("filepath")
    p_batch.add_argument("--method", default="auto")

    # prompt
    p_prompt = sub.add_parser("prompt", help="Generate prompt (no API needed)")
    p_prompt.add_argument("text", help="Text to analyze (use - for stdin)")
    p_prompt.add_argument("--author", default=None)
    p_prompt.add_argument("--source", default="generic")
    p_prompt.add_argument("--format", choices=["combined", "user", "json"],
                          default="combined", dest="prompt_format")

    # extract
    p_extract = sub.add_parser("extract", help="Extract content only (no LLM)")
    p_extract.add_argument("url")
    p_extract.add_argument("--format", choices=["text", "json"], default="text")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "url": cmd_url,
        "text": cmd_text,
        "file": cmd_file,
        "batch": cmd_batch,
        "prompt": cmd_prompt,
        "extract": cmd_extract,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
