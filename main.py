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

    # ── 2.5. Cross-day dedup: drop news already covered in a past digest ───────
    from processors.history import load_seen, filter_unseen
    seen = load_seen()
    before = len(articles)
    articles = filter_unseen(articles, seen)
    print(f"  After cross-day dedup: {len(articles)} (dropped {before - len(articles)} already covered)")

    if not articles:
        print("No fresh articles today. Exiting.")
        sys.exit(0)

    # ── 3. Score with MiniMax ─────────────────────────────────────────────────
    print("Scoring articles …")
    articles = score_articles(articles)

    # filter low-importance: keep worth-knowing (≥3)
    threshold = 3
    articles = [a for a in articles if a.importance >= threshold]
    print(f"  After importance filter (≥{threshold}): {len(articles)}")

    # ── 4. Global insight ─────────────────────────────────────────────────────
    print("Generating insight …")
    insight = generate_insight(articles)

    # ── 4.5. Select display set (top-per-zone) and enrich it ──────────────────────────────────
    from processors.summarizer import enrich_article

    max_per_zone = 5
    zones = ["claude_anthropic", "chinese_ai", "global_ai"]
    display_set = []
    for z in zones:
        zone_arts = sorted(
            [a for a in articles if a.zone == z], key=lambda x: -x.importance
        )[:max_per_zone]
        display_set.extend(zone_arts)

    print(f"Enriching {len(display_set)} display articles (key points + summary) …")
    for a in display_set:
        # key points + ~200字 summary (quality gated)
        enriched = enrich_article(a)
        if enriched["quality"] >= 2:
            a.key_points = enriched["key_points"]
            if enriched["summary"]:
                a.ai_summary = enriched["summary"]
        else:
            # quality too low: keep concise key points if any, fall back to short summary
            a.key_points = enriched.get("key_points", [])[:2]

    # ── 4.6. Evening lead article (multi-model loop) ────────────────────────────────────────────
    lead_article = None
    if mode == "evening":
        from processors.article_writer import generate_lead_article
        print("Generating evening lead article ...")
        try:
            lead_article = generate_lead_article(articles)
            score = lead_article.get("score", 0); print(f"  Lead article score: {score}/10")
        except Exception as e:
            print(f"  Lead article failed: {e}")

    # ── 5. Cross-zone tagging ─────────────────────────────────────────────────
    articles = link_related(articles)

    # ── 6. Render ─────────────────────────────────────────────────────────────
    archive_root = Path(__file__).parent / "archive"
    archive_dir = archive_root / now.strftime("%Y/%m")
    archive_dir.mkdir(parents=True, exist_ok=True)

    stem = f"{now.strftime('%Y-%m-%d')}-{mode}"
    lookback = _lookback_link(archive_root, now, mode)

    md_text = render_md(articles, insight, mode, now, lookback)
    html_text = render_html(articles, insight, mode, now, lookback, lead_article=lead_article)

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
    import time
    
    # Wait until scheduled send time before delivery
    send_time_hm = (21, 0)
    while True:
        now = _bj_now()
        target = now.replace(hour=send_time_hm[0], minute=send_time_hm[1], second=0, microsecond=0)
        if now >= target:
            break
        wait_secs = (target - now).total_seconds()
        if wait_secs > 0:
            wait_mins = wait_secs / 60
            print(f"等待发送时间... 还需 {wait_mins:.1f} 分钟")
            time.sleep(min(wait_secs, 60))  # Check every 60s
    
    print("Sending to WeChat …")
    ok = send_file(str(html_path))
    if ok:
        print("  Delivered successfully.")
        # Mark displayed news as covered so it never repeats in a future digest
        from processors.history import mark_seen
        mark_seen(display_set, seen)
    else:
        print("  Delivery failed (check ilink API response).", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Digest Bot")
    parser.add_argument(
        "--mode",
        choices=["evening"],
        default="evening",
        help="evening digest (21:00 BJ)",
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
