"""
Two-client architecture:
  score_articles   -> DeepSeek v4 Flash  (DEEPSEEK_API_KEY, cheap batch scoring ~60 articles)
  generate_insight -> DeepSeek v4 Flash  (DEEPSEEK_API_KEY, no OAuth needed)
"""
import json
import os
import pathlib
from anthropic import Anthropic
from fetchers.base import Article


def _get_scoring_client() -> Anthropic:
    """DeepSeek for batch scoring -- cheap, fast."""
    return Anthropic(
        api_key=os.environ["DEEPSEEK_API_KEY"],
        base_url="https://api.deepseek.com/anthropic",
    )


SCORE_SYSTEM = """你是一个专注于AI领域的信息分析师。
对用户提供的新闻条目进行评分和摘要。

输出严格的JSON格式（只输出JSON，不要其他内容）：
{
  "importance": <1-5整数，5=改变行业格局，1=日常更新>,
  "summary": "· 核心事实（30-50字）\\n· 影响或意义（30-50字）",
  "tags": ["<标签1>", "<标签2>"]
}

summary规则：
- 恰好2行，每行以"· "开头
- 第一行：核心事实（什么事/谁做了什么），说清楚来龙去脉，30-50字
- 第二行：影响或意义（为什么重要、对行业意味着什么），30-50字
- 内容要充实有信息量，不要为了简短而省略关键信息

评分标准：
5 = 重大突破/发布（新模型、重大安全事件、监管新政）
4 = 重要更新（融资、战略合作、重要功能）
3 = 值得关注（产品更新、研究成果、行业动态）
2 = 常规信息
1 = 轻微更新/噪音

tags最多2个，选自：模型发布 安全 开源 融资 监管 研究 工具 产品"""


def score_articles(articles: list[Article]) -> list[Article]:
    client = _get_scoring_client()
    model = os.getenv("SUMMARIZE_MODEL", "deepseek-v4-flash")
    results = []

    for a in articles:
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=300,
                temperature=0.2,
                system=SCORE_SYSTEM,
                messages=[
                    {"role": "user", "content": f"标题：{a.title}\n来源：{a.source}\n摘要：{a.summary[:200]}"},
                ],
            )
            text = next((b.text for b in resp.content if hasattr(b, "text") and b.text), "")
            text = text.strip()
            if not text:
                raise ValueError("empty response")
            if text.startswith("```"):
                text = text[text.index("\n"):text.rfind("```")].strip()
            data = json.loads(text)
            a.importance = int(data.get("importance", 3))
            a.ai_summary = data.get("summary", a.title)
            a.tags = data.get("tags", [])
        except Exception:
            a.importance = 3
            a.ai_summary = a.title
        results.append(a)
    return results


INSIGHT_SYSTEM = """你是AI领域的深度观察者。
基于今天的新闻条目，生成一段「今日洞察」：
- 找出今天条目中最重要的1-2个关联主题
- 指出这些动态对AI行业意味着什么
- 语言：简练、有观点，≤150字
- 不要罗列新闻，要提炼规律和趋势"""


def generate_insight(articles: list[Article]) -> str:
    client = _get_scoring_client()
    model = os.getenv("SUMMARIZE_MODEL", "deepseek-v4-flash")

    items = "\n".join(
        f"[{a.zone}] {a.source}: {a.ai_summary or a.title} (重要性:{a.importance})"
        for a in articles if a.importance >= 3
    )

    prompt = "今日AI动态：\n" + items

    try:
        resp = client.messages.create(
            model=model, max_tokens=200, temperature=0.3,
            system=INSIGHT_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        return next(
            (b.text for b in resp.content if hasattr(b, "text") and b.text),
            "今日AI动态丰富，详见各专区报道。"
        )
    except Exception:
        return "今日AI动态丰富，详见各专区报道。"


ENRICH_SYSTEM = """你是AI领域的资深编辑，为新闻条目撰写有深度的解读卡片。

输出严格的JSON格式（只输出JSON，不要其他内容）：
{
  "key_points": ["关键句一", "关键句二", "关键句三"],
  "summary": "约200字的总结摘要"
}

key_points规则：
- 2到3条，每条是一句完整、有信息量的话（15-30字）
- 提炼这条新闻最核心的事实/数据/亮点
- 不要空话套话，要具体（写"参数量从7B提升到12B"而非"性能提升"）

summary规则：
- 180-220字的连贯段落，不分点
- 讲清楚：发生了什么、为什么这样做、对行业意味着什么
- 有观点有判断，像一个真正的技术编辑在解读，不要平铺直叙
- 不要重复key_points的原话，要展开和补充

质量要求：宁缺毋滥。如果信息不足以支撑200字，就写真实有的内容，不要硬凑、不要编造数据。"""


def enrich_article(article: Article) -> dict:
    """Generate key_points (2-3) + rich summary (~200字) for a displayed article.
    Returns {"key_points": list, "summary": str, "quality": int}."""
    client = _get_scoring_client()
    model = os.getenv("SUMMARIZE_MODEL", "deepseek-v4-flash")

    context = f"标题：{article.title}\n来源：{article.source}\n原始摘要：{article.summary[:400]}"
    if article.ai_summary:
        context += f"\n已有要点：{article.ai_summary}"

    try:
        resp = client.messages.create(
            model=model, max_tokens=600, temperature=0.4,
            system=ENRICH_SYSTEM,
            messages=[{"role": "user", "content": context}],
        )
        text = next((b.text for b in resp.content if hasattr(b, "text") and b.text), "")
        text = text.strip()
        if text.startswith("```"):
            text = text[text.index("\n"):text.rfind("```")].strip()
        data = json.loads(text)
        key_points = [str(p).strip() for p in data.get("key_points", []) if str(p).strip()][:3]
        summary = str(data.get("summary", "")).strip()
        # Quality gate: need >=2 key points and a substantive summary
        quality = 0
        if len(key_points) >= 2:
            quality += 1
        if len(summary) >= 120:
            quality += 1
        if len(summary) >= 60:
            quality += 1
        return {"key_points": key_points, "summary": summary, "quality": quality}
    except Exception:
        return {"key_points": [], "summary": article.ai_summary, "quality": 0}
