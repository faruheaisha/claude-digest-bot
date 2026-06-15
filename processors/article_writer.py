"""
Evening lead article: long-form tech analysis with auto proofreading.

Flow:
  1. DeepSeek generates 2000+ word technical blog post
  2. DeepSeek reviews and scores (1-10)
  3. If score < 7, DeepSeek revises
  4. huashu-proofreading auto-removes AI flavor
  5. Markdown converted to beautiful HTML
"""
import json
import os
import re
from anthropic import Anthropic
from fetchers.base import Article


def _deepseek_client() -> Anthropic:
    return Anthropic(
        api_key=os.environ["DEEPSEEK_API_KEY"],
        base_url="https://api.deepseek.com/anthropic",
    )


WRITE_SYSTEM = """你是一位资深的AI技术评论作家，文笔流畅、洞察深刻、有自己的观点。

任务：基于今日AI新闻，写一篇 3000-4000 字的深度长文。这是要让读者花至少 3 分钟认真读完的文章，必须有足够的信息密度和思考深度，不能浮于表面。

深度要求（这是重点，每条都要做到）：
1. **拆机制**：不只说"发生了什么"，要拆"为什么这样设计""背后的技术原理是什么"。比如不写"性能提升了"，而写清楚是靠什么手段、付出什么代价、有什么前提。
2. **给数据**：用具体数字、基准分数、参数规模、价格、时间线支撑判断，不要用"大幅""显著"这类空词。
3. **找关联**：把今天多条新闻串成一条暗线，揭示它们共同指向的趋势，而不是逐条罗列。
4. **有反方**：主动提出"但是"——这件事的风险、局限、被高估的地方、可能的反例。只唱赞歌的文章没价值。
5. **作类比**：用历史上类似的技术拐点/商业案例做类比，帮读者理解当下的位置。
6. **落到人**：分别说清楚这对不同角色（开发者 / 创业者 / 大厂 / 普通用户）各意味着什么。
7. **给判断**：结尾要有作者明确的预测或可执行的建议，敢于下结论。

结构（严格使用以下Markdown格式，5-6个部分，每部分 600-800 字）：
# 文章标题（具体、有钩子，能引发好奇）

[导言段落，200字左右，抛出核心论点和最反直觉的发现]

## 第一部分：背景与机制（发生了什么，技术上为什么这么做）

[600-800字，拆解技术机制，给数据]

## 第二部分：深层逻辑（这背后的真正动因和趋势暗线）

[600-800字，串联多条新闻，揭示规律]

## 第三部分：风险与反方（被高估了什么，有什么局限）

[600-800字，批判性视角，提出反面观点]

## 第四部分：对不同角色的影响（开发者/创业者/大厂/用户）

[600-800字，分角色具体分析]

## 第五部分：历史类比与前瞻（这是哪一类拐点，接下来会怎样）

[600-800字，类比+预测]

## 结语

[200字左右，明确的判断或行动建议，留一个值得思考的问题]

排版节奏要求（让文章错落有致、好看，不要一堵段落墙）：
- **每节金句**：在每一个 `## ` 小节标题的正下方，紧跟一句用 `> ` 标注的金句——它是这一节最尖锐、最值得被记住的一句判断，单独成行、凝练有力。若新闻中确有大佬原话可直接引用并署名（如 `> "原话" —— 人名`）；若无确切原话，则写成你对这一节核心观点的一句话凝练，**绝不编造不存在的人名或引语**。
- **额外引用**：正文中再用 `> ` 穿插 1-2 处精彩判断，让节奏跳动
- **列表**：至少 1-2 处用 `- ` 无序列表枚举要点（比如分角色影响、几个关键变化），不要全用段落
- **三级标题**：在较长的部分用 `### ` 切出小标题，帮读者喘气
- **加粗**：每个部分用 `**加粗**` 强调 2-3 个关键概念或数据
- 段落长短错落：有的段落 3-4 句，有的就一两句话点一下，不要每段都一样长

注意：
- 标题要具体，不要用"分析""探讨"这类空洞词
- 每个部分都要有真实的信息增量，禁止用车轱辘话凑字数
- 允许有争议性观点，比平铺直叙更有价值
- 全文字数务必达到 3000 字以上，这是硬性要求"""

REVIEW_SYSTEM = """你是严格的技术内容编辑。评审一篇深度长文，标准（总分10分）：
- 原创洞察（0-2分）：有没有超越新闻的独特见解
- 技术深度（0-2分）：是否拆解了机制、给了具体数据
- 思辨性（0-2分）：是否有反方观点、风险分析，不只唱赞歌
- 篇幅与信息密度（0-2分）：是否达到3000字以上且无注水
- 可读性与说服力（0-2分）：结构清晰、逻辑连贯、观点有支撑

输出JSON：{"score": <1-10>, "strengths": "...", "improvements": "具体指出哪部分太浅、该补什么"}
只输出JSON。如果文章不足3000字或某部分明显注水，扣分并在improvements里指出。"""


PROOFREAD_SYSTEM = """你是 huashu-proofreading 文字编辑，专长是去掉 AI 写作的生硬感和套路感。

改写要求：
- 去掉"首先/其次/综上所述/总而言之/值得注意的是/不仅如此"这类 AI 腔连接词
- 拆掉排比堆砌和工整到假的对仗，让句子长短错落
- 把"赋能/抓手/闭环/生态位"这类空洞黑话换成具体说法
- 保留全部事实、数据、Markdown 结构（# ## 标题、列表、引用、加粗都不动）
- 保留原文的篇幅和信息量，不要删减内容、不要缩写

只输出改写后的完整文章（含 Markdown 标记），不要任何说明或前言。"""


def _call_proofreading(text: str) -> str:
    """用 DeepSeek 执行 huashu-proofreading 降 AI 味（不依赖 OAuth）。"""
    try:
        client = _deepseek_client()
        model = os.getenv("SUMMARIZE_MODEL", "deepseek-v4-flash")
        resp = client.messages.create(
            model=model, max_tokens=8000, temperature=0.6,
            system=PROOFREAD_SYSTEM,
            messages=[{"role": "user", "content": text}],
        )
        out = next((b.text for b in resp.content if hasattr(b, "text") and b.text), "")
        out = out.strip()
        # Safety: only accept if it kept reasonable length (didn't truncate/refuse)
        return out if len(out) >= len(text) * 0.6 else text
    except Exception:
        return text


def _markdown_to_html(text: str) -> str:
    """Convert markdown to beautiful WeChat-style HTML."""
    lines = text.split("\n")
    html_parts = []
    i = 0
    in_list = False

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Empty line
        if not stripped:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            html_parts.append("")
            i += 1
            continue

        # H2 heading (section headers)
        if stripped.startswith("## "):
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            heading_text = _inline_format(stripped[3:].strip())
            html_parts.append(f'<h2 class="la-h2">{heading_text}</h2>')
            i += 1
            continue

        # H3 heading
        if stripped.startswith("### "):
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            heading_text = _inline_format(stripped[4:].strip())
            html_parts.append(f'<h3 class="la-h3">{heading_text}</h3>')
            i += 1
            continue

        # Horizontal rule
        if stripped in ("---", "***", "___"):
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            html_parts.append('<hr class="la-hr">')
            i += 1
            continue

        # Blockquote
        if stripped.startswith("> "):
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            quote_text = _inline_format(stripped[2:].strip())
            html_parts.append(f'<blockquote class="la-quote">{quote_text}</blockquote>')
            i += 1
            continue

        # Unordered list
        if stripped.startswith("- ") or stripped.startswith("* "):
            if not in_list:
                html_parts.append('<ul class="la-list">')
                in_list = True
            item_text = _inline_format(stripped[2:].strip())
            html_parts.append(f'<li>{item_text}</li>')
            i += 1
            continue

        # Regular paragraph
        if in_list:
            html_parts.append("</ul>")
            in_list = False
        para_text = _inline_format(stripped)
        html_parts.append(f'<p class="la-p">{para_text}</p>')
        i += 1

    if in_list:
        html_parts.append("</ul>")

    return "\n".join(html_parts)


def _inline_format(text: str) -> str:
    """Convert inline markdown (bold, italic, links, code) to HTML."""
    # Bold+italic: ***text***
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', text)
    # Bold: **text**
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    # Italic: *text*
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    # Inline code: `code`
    text = re.sub(r'`([^`]+)`', r'<code class="la-code">\1</code>', text)
    # Links: [text](url)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a class="la-link" href="\2" target="_blank" rel="noopener">\1</a>', text)
    return text


def _figure_html(url: str, source: str, title: str) -> str:
    """Build an inline figure with an accurate source caption."""
    import html as _html
    cap = "图：" + _html.escape(source or "来源未知")
    if title:
        cap += " · " + _html.escape(title[:40])
    return (
        '<figure class="la-figure">'
        f'<img class="la-img" src="{_html.escape(url)}" alt="" loading="lazy" '
        'onerror="this.parentNode.style.display=\'none\'">'
        f'<figcaption class="la-cap">{cap}</figcaption>'
        '</figure>'
    )


def _inject_images(body_html: str, articles: list) -> str:
    """Insert up to 3 accurate source images (with captions) before section headers."""
    imgs = []
    seen = set()
    for a in articles:
        img = getattr(a, "og_image", "")
        if img and img not in seen:
            seen.add(img)
            imgs.append((img, a.source, a.title))
        if len(imgs) >= 2:
            break
    if not imgs:
        return body_html

    parts = re.split(r'(<h2 class="la-h2">)', body_html)
    result = []
    h2_count = 0
    img_idx = 0
    for seg in parts:
        if seg == '<h2 class="la-h2">':
            h2_count += 1
            # insert one image before each section header from the 2nd onward
            if h2_count >= 2 and img_idx < len(imgs):
                url, source, title = imgs[img_idx]
                result.append(_figure_html(url, source, title))
                img_idx += 1
        result.append(seg)

    # If body had too few sections, append a remaining image at the end
    if img_idx == 0 and imgs:
        url, source, title = imgs[0]
        result.append(_figure_html(url, source, title))

    return "".join(result)


def generate_lead_article(articles: list[Article]) -> dict:
    """
    Generate 2000+ word tech blog article with auto proofreading.
    Returns: {"title": str, "body": str, "score": int}
    """
    top_articles = sorted(articles, key=lambda a: -a.importance)[:15]
    news_items = "\n".join(
        f"[{a.zone}] {a.source}: {a.ai_summary or a.title} (重要性:{a.importance})"
        for a in top_articles
    )

    prompt = f"今日AI新闻条目：\n{news_items}\n\n基于这些新闻，写一篇深度技术分析文章。"
    ds_client = _deepseek_client()
    ds_model = os.getenv("SUMMARIZE_MODEL", "deepseek-v4-flash")

    article_text = ""
    try:
        resp = ds_client.messages.create(
            model=ds_model,
            max_tokens=8000,
            temperature=0.5,
            system=WRITE_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        article_text = next((b.text for b in resp.content if hasattr(b, "text") and b.text), "")
    except Exception as e:
        return {"title": "技术更新", "body": f"<p>文章生成失败: {str(e)[:100]}</p>", "score": 0}

    best_text = article_text
    best_score = 0

    # Quality loop: review and revise
    for round_num in range(2):
        try:
            review_prompt = f"请评审以下文章：\n\n{article_text}"
            resp = ds_client.messages.create(
                model=ds_model, max_tokens=300, temperature=0.2,
                system=REVIEW_SYSTEM,
                messages=[{"role": "user", "content": review_prompt}],
            )
            text = next((b.text for b in resp.content if hasattr(b, "text") and b.text), "")
            text = text.strip()
            if text.startswith("```"):
                text = text[text.index("\n"):text.rfind("```")].strip()
            review = json.loads(text)
            score = int(review.get("score", 6))

            if score > best_score:
                best_score = score
                best_text = article_text

            if score >= 7:
                break

            improvements = review.get("improvements", "")
            revise_prompt = (
                f"根据以下反馈修改文章（评分 {score}/10）：{improvements}\n\n原文：\n{article_text}"
            )
            resp = ds_client.messages.create(
                model=ds_model, max_tokens=8000, temperature=0.5,
                system=WRITE_SYSTEM,
                messages=[{"role": "user", "content": revise_prompt}],
            )
            article_text = next((b.text for b in resp.content if hasattr(b, "text") and b.text), "")
        except Exception:
            break

    # Fallback score: if review never produced a valid score, judge by length
    if best_score == 0 and best_text:
        best_score = 7 if len(best_text) > 1200 else 5

    # Auto proofreading: remove AI flavor
    print("应用 huashu-proofreading 去 AI 味...")
    best_text = _call_proofreading(best_text)

    # Parse title and body
    lines_raw = best_text.strip().split("\n")
    title = ""
    body_lines = []
    for line in lines_raw:
        stripped = line.strip()
        if not title and stripped.startswith("# "):
            title = stripped[2:].strip()
        elif not title and stripped.startswith("#"):
            title = stripped.lstrip("#").strip()
        else:
            body_lines.append(line)

    if not title:
        title = "今日 AI 技术动向"

    body_md = "\n".join(body_lines).strip()
    # Convert markdown to beautiful HTML
    body_html = _markdown_to_html(body_md)
    # Inject accurate source images with captions
    body_html = _inject_images(body_html, sorted(articles, key=lambda a: -a.importance))

    return {"title": title, "body": body_html, "score": best_score}
