"""
DeepSeek API: OpenAI-compatible.
  summarize_model = deepseek-chat   (fast, batch scoring)
  analyze_model   = deepseek-reasoner (deep, single call for insights)
"""
import json
import os
from openai import OpenAI
from fetchers.base import Article

_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=os.environ["DEEPSEEK_API_KEY"],
            base_url="https://api.deepseek.com",
        )
    return _client


SCORE_SYSTEM = """你是一个专注于AI领域的信息分析师。
对用户提供的新闻条目进行评分和摘要。

输出严格的JSON格式：
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
    model = os.getenv("SUMMARIZE_MODEL", "deepseek-chat")
    results = []

    for a in articles:
        prompt = f"标题：{a.title}\n来源：{a.source}\n摘要：{a.summary[:200]}"
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SCORE_SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                max_tokens=200,
                temperature=0.2,
            )
            data = json.loads(resp.choices[0].message.content)
            a.importance = int(data.get("importance", 3))
            a.ai_summary = data.get("summary", a.title)
            a.tags = data.get("tags", [])
        except Exception as e:
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
    model = os.getenv("ANALYZE_MODEL", "deepseek-reasoner")

    items = "\n".join(
        f"[{a.zone}] {a.source}: {a.ai_summary or a.title} (重要性:{a.importance})"
        for a in articles if a.importance >= 3
    )

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": INSIGHT_SYSTEM},
                {"role": "user", "content": f"今日AI动态：\n{items}"},
            ],
            max_tokens=300,
            temperature=0.7,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return "今日AI动态丰富，详见各专区报道。"
