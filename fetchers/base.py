from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import hashlib
import feedparser
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "claude-digest-bot/1.0 (github.com/faruheaisha/claude-digest-bot)"}


@dataclass
class Article:
    title: str
    url: str
    source: str
    zone: str           # "claude_anthropic" | "chinese_ai" | "global_ai"
    published: Optional[datetime] = None
    summary: str = ""   # raw excerpt, before AI processing
    importance: int = 0  # 1-5, filled by summarizer
    ai_summary: str = ""  # AI-generated rich summary (~200 chars, for displayed articles)
    key_points: list = field(default_factory=list)  # 2-3 key sentences, for displayed articles
    tags: list = field(default_factory=list)

    @property
    def uid(self) -> str:
        return hashlib.md5(self.url.encode()).hexdigest()[:12]


def fetch_rss(url: str, source_name: str, zone: str, keywords: list = None) -> list[Article]:
    try:
        feed = feedparser.parse(url, request_headers=HEADERS)
    except Exception:
        return []

    articles = []
    for entry in feed.entries[:15]:
        title = entry.get("title", "").strip()
        link = entry.get("link", "")
        if not title or not link:
            continue

        if keywords:
            combined = (title + entry.get("summary", "")).lower()
            if not any(kw.lower() in combined for kw in keywords):
                continue

        published = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                published = datetime(*entry.published_parsed[:6])
            except Exception:
                pass

        raw_summary = BeautifulSoup(entry.get("summary", ""), "html.parser").get_text()[:300]

        articles.append(Article(
            title=title,
            url=link,
            source=source_name,
            zone=zone,
            published=published,
            summary=raw_summary,
        ))
    return articles


def fetch_page_titles(url: str, source_name: str, zone: str) -> list[Article]:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception:
        return []

    articles = []
    for a in soup.find_all("a", href=True)[:30]:
        title = a.get_text(strip=True)
        href = a["href"]
        if len(title) < 10:
            continue
        if href.startswith("/"):
            from urllib.parse import urlparse
            base = urlparse(url)
            href = f"{base.scheme}://{base.netloc}{href}"
        if not href.startswith("http"):
            continue
        articles.append(Article(title=title, url=href, source=source_name, zone=zone))
    return articles[:10]
