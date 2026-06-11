"""Tag articles that share themes so the HTML formatter can visually link them."""
from collections import defaultdict
from fetchers.base import Article

# If 2+ articles share a tag, assign them the same link_group color index
LINK_COLORS = ["#7C3AED", "#0891B2", "#15803D", "#B45309", "#9D174D"]


def link_related(articles: list[Article]) -> list[Article]:
    tag_to_articles: dict[str, list[Article]] = defaultdict(list)
    for a in articles:
        for tag in a.tags:
            tag_to_articles[tag].append(a)

    color_idx = 0
    assigned: dict[str, str] = {}  # tag -> color

    for tag, group in tag_to_articles.items():
        if len(group) >= 2:
            color = LINK_COLORS[color_idx % len(LINK_COLORS)]
            assigned[tag] = color
            color_idx += 1

    for a in articles:
        a._link_colors = {}  # tag -> color for this article
        for tag in a.tags:
            if tag in assigned:
                a._link_colors[tag] = assigned[tag]

    return articles
