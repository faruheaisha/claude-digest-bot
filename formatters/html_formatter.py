from datetime import datetime
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from fetchers.base import Article

_TEMPLATE_DIR = Path(__file__).parent.parent / "templates"

IMPORTANCE_ICONS = {5: "🔥🔥🔥", 4: "🔥🔥", 3: "🔥", 2: "⭐", 1: "📌"}
ZONE_ORDER = ["claude_anthropic", "chinese_ai", "global_ai"]


def _enrich(article: Article) -> Article:
    article.importance_icon = IMPORTANCE_ICONS.get(article.importance, "📌")
    return article


def render_html(
    articles: list[Article],
    insight: str,
    mode: str,
    date: datetime,
    lookback_link: str = "",
) -> str:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=True,
    )
    tmpl = env.get_template("digest.html.jinja")

    date_str = date.strftime("%Y-%m-%d")
    mode_label = "早报" if mode == "morning" else "晚报"
    max_per_zone = 3 if mode == "morning" else 5

    by_zone: dict[str, list[Article]] = {z: [] for z in ZONE_ORDER}
    for a in articles:
        if a.zone in by_zone:
            by_zone[a.zone].append(_enrich(a))

    def top(zone: str) -> list[Article]:
        return sorted(by_zone[zone], key=lambda x: -x.importance)[:max_per_zone]

    lookback_html = ""
    if lookback_link:
        lookback_html = (
            f'<a class="lookback__card" href="{lookback_link}" '
            f'target="_blank" rel="noopener">查看 7 天前今日的 AI 动态</a>'
        )

    return tmpl.render(
        date_str=date_str,
        mode_label=mode_label,
        insight=insight,
        claude_articles=top("claude_anthropic"),
        chinese_articles=top("chinese_ai"),
        global_articles=top("global_ai"),
        lookback_html=lookback_html,
    )
