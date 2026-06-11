from .base import Article, fetch_rss

AI_KEYWORDS = ["AI", "人工智能", "大模型", "LLM", "GPT", "Claude", "机器学习",
                "深度学习", "神经网络", "Anthropic", "OpenAI", "谷歌", "百度"]


def fetch_chinese_ai() -> list[Article]:
    sources = [
        ("https://www.jiqizhixin.com/rss", "机器之心", None),
        ("https://www.qbitai.com/feed", "量子位", None),
        ("https://36kr.com/feed", "36kr", AI_KEYWORDS),
        ("https://www.geekpark.net/rss", "极客公园", AI_KEYWORDS),
    ]
    articles = []
    for url, name, keywords in sources:
        fetched = fetch_rss(url, source_name=name, zone="chinese_ai", keywords=keywords)
        articles.extend(fetched[:6])
    return articles
