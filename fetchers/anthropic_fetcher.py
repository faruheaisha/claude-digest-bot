import os
import requests
from .base import Article, fetch_page_titles, HEADERS

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")


def _is_content_link(href: str) -> bool:
    """Keep only links pointing to actual content pages, not nav/support/claude.ai."""
    from urllib.parse import urlparse
    # Accept absolute URLs on anthropic.com that point to content paths
    if href.startswith("http"):
        path = urlparse(href).path
        return any(path.startswith(p) for p in ("/news/", "/research/", "/policy-", "/features/", "/81k-"))
    # Accept relative paths on anthropic.com
    if href.startswith(("/news/", "/research/", "/policy-", "/features/", "/81k-")):
        # Exclude team/category index pages that are not individual articles
        if href.startswith("/research/team/"):
            return False
        return True
    return False


def fetch_anthropic_news() -> list[Article]:
    articles = fetch_page_titles(
        "https://www.anthropic.com/news",
        source_name="Anthropic News",
        zone="claude_anthropic",
    )
    return [a for a in articles if _is_content_link(a.url) and len(a.title) > 15][:10]


def fetch_anthropic_research() -> list[Article]:
    articles = fetch_page_titles(
        "https://www.anthropic.com/research",
        source_name="Anthropic Research",
        zone="claude_anthropic",
    )
    return [a for a in articles if _is_content_link(a.url) and len(a.title) > 15][:5]


def fetch_anthropic_github() -> list[Article]:
    headers = {**HEADERS, "Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    articles = []
    try:
        # Recent releases across anthropics org repos
        repos_resp = requests.get(
            "https://api.github.com/orgs/anthropics/repos?sort=updated&per_page=10",
            headers=headers, timeout=10
        )
        repos = repos_resp.json() if repos_resp.ok else []
        for repo in repos[:6]:
            name = repo.get("name", "")
            desc = repo.get("description", "") or ""
            pushed = repo.get("pushed_at", "")
            url = repo.get("html_url", "")
            if name and url:
                articles.append(Article(
                    title=f"[GitHub] {name}: {desc[:60]}" if desc else f"[GitHub] {name} updated",
                    url=url,
                    source="Anthropic GitHub",
                    zone="claude_anthropic",
                    summary=f"Repo: {name}. {desc}. Last push: {pushed[:10]}",
                ))
    except Exception:
        pass
    return articles
