import hashlib
from fetchers.base import Article


def dedup(articles: list[Article]) -> list[Article]:
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    result = []
    for a in articles:
        url_key = hashlib.md5(a.url.encode()).hexdigest()
        title_key = hashlib.md5(a.title.lower().strip().encode()).hexdigest()
        if url_key in seen_urls or title_key in seen_titles:
            continue
        seen_urls.add(url_key)
        seen_titles.add(title_key)
        result.append(a)
    return result
