# claude-digest-bot

[English](README.md) · **简体中文**

![claude-digest-bot](assets/promo-banner.svg)

一个自动化的 AI 新闻日报系统：抓取、筛选、并每天晚上通过微信推送一份覆盖 Claude/Anthropic、国内 AI、全球 AI 的深度简报。

## 它做什么

- **晚报**（北京时间 21:00）：一份完整报告，以一篇深度长文领衔，随后是三个新闻专区
- 同时生成 `.md`（归档用）和 `.html`（微信推送、未来博客复用）
- 内容生成可以提前数小时开始，但会**持有成品、等到设定时间点才推送**

## 推理后端：全部跑在 MiniMax API 上

**这个项目的所有 AI 生成——打分、富化、洞察、晚报长文——统一调用 MiniMax API**（通过 Anthropic SDK 的 `base_url` 指向 `https://api.minimaxi.com/anthropic`，默认模型 `MiniMax-M3`）。不依赖 Anthropic 官方额度，只需一个 `MINIMAX_API_KEY`。

## 多重评分与质量门控

日报的"含金量"来自一套分层的、带质量门控的多重评分流程，而不是一遍过：

1. **第一遍 · 重要性打分**：对全部约 60 条抓取条目逐条打 1–5 分（便宜、快速），低于阈值的直接淘汰（早报 ≥4，晚报 ≥3）。
2. **第二遍 · 深度富化**：只对将要展示的约 15 条做更贵的二次处理，生成 2–3 条关键句 + 约 200 字解读，并**质量门控**——信息量不足的结果会被丢弃，绝不硬凑。
3. **晚报长文 · 生成→评审→修订循环**：晚报头条长文先生成 3000+ 字，再由模型按 5 个维度打分（0–10），**低于 7 分就带着反馈重写**，最多两轮，取最高分版本。
4. **降 AI 味**：最后一遍按 huashu-proofreading 风格去掉 AI 腔，让文字更像人写的。

### 新闻卡片

每一条展示的文章渲染为一张纵向卡片：

1. **标题** + 重要性图标
2. **关键句**——2–3 条高亮要点
3. **摘要**——约 200 字的编辑式段落
4. **来源** + 标签 + **发布日期**

### 晚报领衔长文

晚报以一篇 3000+ 字的深度分析开篇，取材自当天头部新闻：

- 多段落结构，含小标题、金句引用、列表、加粗，营造视觉节奏
- 生成→打分→修订的质量循环在发布前把关
- 去 AI 味处理，声音更接近真人
- 全文控制在 4000 字以内

## 内容专区

| 专区 | 来源 |
|------|------|
| Claude / Anthropic | anthropic.com/news、anthropic.com/research、GitHub anthropics 组织 |
| 国内 AI 动态 | 机器之心、量子位、36kr、极客公园 |
| 全球 AI 大事件 | OpenAI、Google DeepMind、Hugging Face、The Verge AI、TechCrunch AI |

> 抓取源直接硬编码在 `fetchers/` 各模块里（清晰、可测、带类型），新增/调整源改对应 fetcher 即可。

## 快速开始

### 1. 克隆并安装依赖

```bash
git clone https://github.com/faruheaisha/claude-digest-bot
cd claude-digest-bot
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入你的密钥：
#   MINIMAX_API_KEY   — 从 https://platform.minimaxi.com 获取
#   ILINK_TOKEN       — 你的 ilink 微信桥 token
#   WECHAT_UID        — 接收日报的微信 UID
#   GITHUB_TOKEN      — 可选，提升 GitHub API 限额
```

### 3. 用 dry-run 测试

```bash
python main.py --mode evening --dry-run
```

会在 `archive/YYYY/MM/` 下生成文件，但**不**推送微信。

### 4. 用 cron 定时（服务器，UTC 时区）

```cron
# 晚报  北京 21:00 = UTC 13:00
0 13 * * * cd /path/to/claude-digest-bot && python main.py --mode evening >> logs/cron.log 2>&1
```

也可以让 cron 更早触发——程序生成完日报后，会**内部等待到设定的推送时间**再发送，所以触发时间早于目标时间也没问题。

## 项目结构

```
claude-digest-bot/
├── main.py                     # 入口 + 流水线编排
├── fetchers/                   # 各来源抓取器（RSS + HTML 抓取），源在此硬编码
├── processors/
│   ├── summarizer.py           # MiniMax 打分、富化（关键句 + 摘要）、每日洞察
│   ├── article_writer.py       # 晚报长文（生成 → 评审 → 降AI味 → 配图）
│   ├── dedup.py                # 去重
│   └── linker.py               # 跨专区标签关联
├── formatters/                 # .md 和 .html 输出渲染
├── delivery/                   # 微信 ilink 文件推送
└── templates/                  # Jinja2 HTML 模板（卡片 + 长文样式）
```

## 微信推送配置

本机器人需要一个运行中的 [wechat-claude-code](https://github.com/faruheaisha/wechat-claude-code) 实例提供有效的 ilink token。配置完成后，把 `ILINK_TOKEN` 和 `WECHAT_UID` 填入 `.env`。

## 安全

**绝不提交密钥。** 所有凭据（`MINIMAX_API_KEY`、`ILINK_TOKEN`、`WECHAT_UID`、`GITHUB_TOKEN`）都从环境变量 / `.env` 读取，且 `.env` 已被 gitignore。源码中不硬编码任何 token、服务器 IP 或个人标识。推送前先核对：

```bash
git diff --staged   # 审查即将提交的内容
```

`.gitignore` 已排除 `.env`、凭据文件、日志和本地 `archive/`。

## 归档

生成的日报保存在 `archive/YYYY/MM/YYYY-MM-DD-{morning,evening}.{md,html}`。`archive/` 默认被 gitignore——只有当你想要一份公开的历史记录时再纳入版本控制（且务必先确认其中不含隐私内容）。

## 许可

[MIT](LICENSE)
