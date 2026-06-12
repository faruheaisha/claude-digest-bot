"""
Scoring + insight via Anthropic SDK (routes through proxy, supports any model).
  summarize_model = deepseek-v4-flash   (fast, batch scoring, deepseek cheap)
  analyze_model   = claude-sonnet-4-6   (insight, Claude subscription)
"""
import json
import os
from anthropic import Anthropic
from fetchers.base import Article


def _get_client() -> Anthropic:
    return Anthropic(
        api_key=os.environ["ANTHROPIC_AUTH_TOKEN"],
        base_url=os.environ["ANTHROPIC_BASE_URL"],
    )


SCORE_SYSTEM = """你是一个专注于AI领域的信息分析师。
对用户提供的新闻条目进行评分和摘要。

输出严格的JSON格式（只输出JSON，不要其他内容）：
{
  "importance": <1-5整数，5=改变行业格局，1=日常更新>,
  "summary": "· 要点一（≤25字）\n· 要点二（≤25字）",
  "tags": ["<标签1>", "<标签2>"]
}

summary规则：
- 必须是恰好2行，每行以"· "开头
- 第一行：核心事实（什么事/谁做了什么）
- 第二行：影响或意义（为什么重要）
- 每行不超过25字

评分标准：
5 = 重大突破/发布（新模型、重大安全事件、监管新政）
4 = 重要更新（融资、战略合作、重要功能）
3 = 值得关注（产品更新、研究成果、行业动态）
2 = 常规信息
1 = 轻微更新/噪音

tags最多2个，选自：模型发布 安全 开源 融资 监管 研究 工具 产品"""


def score_articles(articles: list[Article]) -> list[Article]:
    client = _get_client()
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
            # Skip ThinkingBlock — find the first TextBlock
            text = next((b.text for b in resp.content if hasattr(b, "text") and b.text), "")
            text = text.strip()
            if not text:
                raise ValueError("empty text response")
            # strip markdown code fence if present
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
    client = _get_client()
    model = os.getenv("ANALYZE_MODEL", "claude-sonnet-4-6")

    items = "\n".join(
        f"[{a.zone}] {a.source}: {a.ai_summary or a.title} (重要性:{a.importance})"
        for a in articles if a.importance >= 3
    )

    try:
        resp = client.messages.create(
            model=model,
            max_tokens=500,
            temperature=0.7,
            system=INSIGHT_SYSTEM,
            messages=[
                {"role": "user", "content": f"今日AI动态：\n{items}"},
            ],
        )
        text = next((b.text for b in resp.content if hasattr(b, "text") and b.text), "")
        return text.strip() if text else "今日AI动态丰富，详见各专区报道。"
    except Exception:
        return "今日AI动态丰富，详见各专区报道。"
