from datetime import datetime
from fetchers.base import Article

IMPORTANCE_STARS = {5: "🔥🔥🔥", 4: "🔥🔥", 3: "🔥", 2: "⭐", 1: "📌"}
ZONE_LABELS = {
    "claude_anthropic": "🤖 Claude / Anthropic",
    "chinese_ai": "🇨🇳 国内 AI 动态",
    "global_ai": "🌍 全球 AI 大事件",
}
ZONE_ORDER = ["claude_anthropic", "chinese_ai", "global_ai"]


def render_md(
    articles: list[Article],
    insight: str,
    mode: str,  # "morning" | "evening"
    date: datetime,
    lookback_link: str = "",
) -> str:
    date_str = date.strftime("%Y-%m-%d")
    mode_label = "早报" if mode == "morning" else "晚报"
    lines = [
        f"# AI 日报 · {date_str} {mode_label}",
        "",
        "## 今日洞察",
        f"> {insight}",
        "",
    ]

    by_zone: dict[str, list[Article]] = {z: [] for z in ZONE_ORDER}
    for a in articles:
        if a.zone in by_zone:
            by_zone[a.zone].append(a)

    max_per_zone = 5 if mode == "morning" else 999

    for zone in ZONE_ORDER:
        items = sorted(by_zone[zone], key=lambda x: -x.importance)[:max_per_zone]
        if not items:
            continue
        lines.append(f"## {ZONE_LABELS[zone]}")
        lines.append("")
        for a in items:
            stars = IMPORTANCE_STARS.get(a.importance, "📌")
            tags_str = "  ".join(f"`{t}`" for t in a.tags) if a.tags else ""
            lines.append(f"### {stars} [{a.title}]({a.url})")
            lines.append(f"> {a.ai_summary}")
            if tags_str:
                lines.append(f"> {tags_str} · 来源：{a.source}")
            else:
                lines.append(f"> 来源：{a.source}")
            lines.append("")

    if lookback_link:
        lines += [
            "---",
            "## 🔁 温故知新",
            f"[查看7天前今日的 AI 动态]({lookback_link})",
            "",
        ]

    lines += [
        "---",
        f"*由 [claude-digest-bot](https://github.com/faruheaisha/claude-digest-bot) 自动生成 · {date_str}*",
    ]
    return "\n".join(lines)
