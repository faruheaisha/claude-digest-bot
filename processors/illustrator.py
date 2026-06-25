"""
小黑 (Xiaohei) hand-drawn illustrations for the evening lead article.

Pipeline:
  1. MiniMax-M3 reads the article and plans a shot list (1 cover + 4 knowledge points).
  2. Each shot is rendered TEXT-FREE by Agnes (agnes-image-2.1-flash) in the 小黑 style.

Text is deliberately suppressed: image models garble Chinese characters, and this is
an unattended cron pipeline with no human QA, so meaning is carried by the visual
metaphor plus the article section the image sits next to.

Style DNA distilled from github.com/helloianneo/ian-xiaohei-illustrations.
Env: AGNES_API_KEY (image gen), MINIMAX_API_KEY (shot planning).
"""
import json
import os
import requests
from anthropic import Anthropic

_AGNES_URL = "https://apihub.agnes-ai.com/v1/images/generations"

# Canonical 小黑 visual DNA, text-free variant for automation.
_XIAOHEI_DNA = (
    "Generate one standalone 16:9 horizontal hand-drawn illustration. "
    "Pure white background, minimalist black hand-drawn line art with slightly wobbly pen lines, "
    "lots of empty white space. A recurring IP character is required: 小黑 (Xiaohei) — a small "
    "solid-black absurd creature with white dot eyes, tiny thin legs, blank serious deadpan "
    "expression, slightly uneven hand-drawn body. 小黑 must perform the core conceptual action, "
    "not decorate the scene: serious, deadpan, slightly bizarre, never cute. "
    "Mostly black line art; a few sparse orange accents for the main flow/path/arrows, red only "
    "for a key problem, blue only for a secondary note. Keep the main subject 40-60% of the canvas "
    "with at least 35% blank white space. "
    "ABSOLUTELY NO TEXT of any kind anywhere: no words, no letters, no Chinese characters, no "
    "numbers, no labels, no title. "
    "No gradients, no shadows, no paper texture, no complex background, no commercial vector style, "
    "no PPT infographic look, no cute mascot poster, no children's illustration, no realistic UI. "
    "One image explains exactly one idea; invent a fresh visual metaphor."
)

_SHOTLIST_SYSTEM = """你是“小黑”手绘配图的视觉策划。读一篇 AI 技术长文，规划 5 张**无文字**的手绘隐喻配图：
- cover：封面图，概括全文最核心的一个判断/主题。
- 另外 4 张：对应文章里 4 个最重要的“认知锚点”（核心判断、转折、前后对比、机制、风险等），每张可视化一个知识点。

每张只给“画面描述”，描述小黑在做什么、有哪些主要物件、如何构图。隐喻要新鲜、怪诞但成立；不要 PPT、不要流程图、不要可爱卡通。**画面里不要出现任何文字**（模型画不准中文）。

严格输出 JSON（只输出 JSON）：
{
  "cover": "<封面图英文画面描述：小黑的核心动作 + 物件 + 构图>",
  "shots": [
    {"idea": "<这张图表达的知识点，中文>", "scene": "<英文画面描述>"}
  ]
}
shots 恰好 4 条。scene 用英文（喂给图像模型），idea 用中文。"""


def _minimax() -> Anthropic:
    return Anthropic(
        api_key=os.environ["MINIMAX_API_KEY"],
        base_url="https://api.minimaxi.com/anthropic",
    )


def _plan_shots(title: str, article_md: str) -> dict:
    client = _minimax()
    model = os.getenv("SUMMARIZE_MODEL", "MiniMax-M3")
    prompt = f"文章标题：{title}\n\n正文（节选）：\n{article_md[:4000]}"
    resp = client.messages.create(
        model=model, max_tokens=1500, temperature=0.6,
        system=_SHOTLIST_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    text = next((b.text for b in resp.content if hasattr(b, "text") and b.text), "").strip()
    if text.startswith("```"):
        text = text[text.index("\n"):text.rfind("```")].strip()
    return json.loads(text)


def _agnes_image(scene: str, timeout: int = 120) -> str:
    """Render one text-free 小黑 image; return its URL ('' on failure)."""
    try:
        r = requests.post(
            _AGNES_URL,
            headers={
                "Authorization": f"Bearer {os.environ['AGNES_API_KEY']}",
                "content-type": "application/json",
            },
            json={
                "model": os.getenv("AGNES_IMAGE_MODEL", "agnes-image-2.1-flash"),
                "prompt": _XIAOHEI_DNA + "\n\nScene: " + scene,
                "size": "1024x576",
                "extra_body": {"response_format": "url"},
            },
            timeout=timeout,
        )
        r.raise_for_status()
        data = r.json()
        return (data.get("data") or [{}])[0].get("url", "") or ""
    except Exception as e:
        print(f"  Agnes image failed: {e}")
        return ""


def generate_illustrations(title: str, article_md: str) -> dict:
    """Plan + render 小黑 illustrations for a lead article.

    Returns {"cover": url, "sections": [{"idea": str, "url": str}, ...]}.
    Any field may be empty on failure — callers must treat images as optional.
    """
    try:
        plan = _plan_shots(title, article_md)
    except Exception as e:
        print(f"  Shot planning failed: {e}")
        return {"cover": "", "sections": []}

    cover = _agnes_image(plan["cover"]) if plan.get("cover") else ""
    sections = []
    for shot in (plan.get("shots") or [])[:4]:
        scene = (shot or {}).get("scene", "")
        if scene:
            sections.append({"idea": (shot or {}).get("idea", ""), "url": _agnes_image(scene)})
    print(f"  Illustrations: cover={'ok' if cover else 'none'}, sections={sum(1 for s in sections if s['url'])}/{len(sections)}")
    return {"cover": cover, "sections": sections}
