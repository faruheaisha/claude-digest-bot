from .base import Article, fetch_rss


def fetch_global_ai() -> list[Article]:
    sources = [
        ("https://openai.com/news/rss.xml", "OpenAI", None),
        ("https://deepmind.google/blog/rss.xml", "Google DeepMind", None),
        ("https://huggingface.co/blog/feed.xml", "Hugging Face", None),
        ("https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", "The Verge AI", None),
        ("https://techcrunch.com/category/artificial-intelligence/feed/", "TechCrunch AI", None),
    ]
    articles = []
    for url, name, keywords in sources:
        fetched = fetch_rss(url, source_name=name, zone="global_ai", keywords=keywords)
        articles.extend(fetched[:6])
    return articles
