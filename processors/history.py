"""Cross-day dedup: remember which articles already appeared in a past digest,
so the same news is never shown twice (Option A — repeats are dropped entirely).

State lives in seen.json at the repo root (gitignored). Entries older than
_RETAIN_DAYS are pruned, so a long-running story can resurface after a month.
"""
import json
from datetime import datetime, timedelta
from pathlib import Path

_SEEN_PATH = Path(__file__).parent.parent / "seen.json"
_RETAIN_DAYS = 30


def load_seen() -> dict:
    """Return {uid: 'YYYY-MM-DD'} of articles already covered. Empty on first run."""
    try:
        return json.loads(_SEEN_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def filter_unseen(articles: list, seen: dict) -> list:
    """Drop articles whose uid is already in seen (covered in a past digest)."""
    return [a for a in articles if a.uid not in seen]


def mark_seen(articles: list, seen: dict) -> None:
    """Record these article uids as covered today, prune stale entries, persist."""
    today = datetime.now().strftime("%Y-%m-%d")
    for a in articles:
        seen[a.uid] = today
    cutoff = (datetime.now() - timedelta(days=_RETAIN_DAYS)).strftime("%Y-%m-%d")
    seen = {uid: d for uid, d in seen.items() if d >= cutoff}
    _SEEN_PATH.write_text(json.dumps(seen, ensure_ascii=False), encoding="utf-8")
