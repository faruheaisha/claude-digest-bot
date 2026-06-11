#!/usr/bin/env python3
"""
claude-digest-bot · entry point

Usage:
  python main.py --mode morning [--dry-run]
  python main.py --mode evening [--dry-run]

--dry-run  Generate files but skip WeChat delivery.
"""
import argparse
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Beijing time (UTC+8) ─────────────────────────────────────────────────────
TZ_BJ = timezone(timedelta(hours=8))


def _bj_now() -> datetime:
    return datetime.now(TZ_BJ)


def _lookback_link(archive_root: Path, date: datetime, mode: str) -> str:
    """Return file:// or web path to 7-days-ago digest, empty string if missing."""
    past = date - timedelta(days=7)
    suffix = "morning" if mode == "morning" else "evening"
    candidate = archive_root / past.strftime("%Y/%m") / f"{past.strftime('%Y-%m-%d')}-{suffix}.html"
    if candidate.exists():
        return candidate.as_uri()
    return ""


def run(mode: str, dry_run: bool) -> None:
    from fetchers.anthropic_fetcher import (
        fetch_anthropic_news, fetch_anthropic_research, fetch_anthropic_github,
    )
    from fetchers.chinese_ai import fetch_chinese_ai
    from fetchers.global_ai import fetch_global_ai
    from processors.dedup import dedup
    from processors.summarizer import score_articles, generate_insight
    from processors.linker import link_related
    from formatters.md_formatter import render_md
    from formatters.html_formatter import render_html

    now = _bj_now()
    print(f"[{now.strftime('%Y-%m-%d %H:%M')} BJ] Starting {mode} digest …")

    # ── 1. Fetch ──────────────────────────────────────────────────────────────
    print("Fetching sources …")
    articles = (
        fetch_anthropic_news() + fetch_anthropic_research() + fetch_anthropic_github()
        + fetch_chinese_ai() + fetch_global_ai()
    )
    print(f"  Raw articles: {len(articles)}")

    # ── 2. Dedup ──────────────────────────────────────────────────────────────
    articles = dedup(articles)
    print(f"  After dedup: {len(articles)}")

    if not articles:
        print("No articles found. Exiting.")
        sys.exit(0)

    # ── 3. Score with DeepSeek ────────────────────────────────────────────────
    print("Scoring articles …")
    articles = score_articles(articles)

    # filter low-importance
    articles = [a for a in articles if a.importance >= 3]
    print(f"  After importance filter (≥3): {len(articles)}")

    # ── 4. Global insight ─────────────────────────────────────────────────────
    print("Generating insight …")
    insight = generate_insight(articles)

    # ── 5. Cross-zone tagging ─────────────────────────────────────────────────
    articles = link_related(articles)

    # ── 6. Render ─────────────────────────────────────────────────────────────
    archive_root = Path(__file__).parent / "archive"
    archive_dir = archive_root / now.strftime("%Y/%m")
    archive_dir.mkdir(parents=True, exist_ok=True)

    stem = f"{now.strftime('%Y-%m-%d')}-{mode}"
    lookback = _lookback_link(archive_root, now, mode)

    md_text = render_md(articles, insight, mode, now, lookback)
    html_text = render_html(articles, insight, mode, now, lookback)

    md_path = archive_dir / f"{stem}.md"
    html_path = archive_dir / f"{stem}.html"

    md_path.write_text(md_text, encoding="utf-8")
    html_path.write_text(html_text, encoding="utf-8")
    print(f"  Saved → {md_path}")
    print(f"  Saved → {html_path}")

    # ── 7. Deliver ────────────────────────────────────────────────────────────
    if dry_run:
        print("[dry-run] Skipping WeChat delivery.")
        return

    from delivery.wechat_sender import send_file
    print("Sending to WeChat …")
    ok = send_file(str(html_path))
    if ok:
        print("  Delivered successfully.")
    else:
        print("  Delivery failed (check ilink API response).", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Digest Bot")
    parser.add_argument(
        "--mode",
        choices=["morning", "evening"],
        required=True,
        help="morning (07:30 BJ) or evening (21:00 BJ)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate files only, skip WeChat delivery",
    )
    args = parser.parse_args()
    run(args.mode, args.dry_run)


if __name__ == "__main__":
    main()
