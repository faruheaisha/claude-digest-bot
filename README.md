# claude-digest-bot

An automated AI news digest system that scrapes, filters, and delivers a daily briefing covering Claude/Anthropic, Chinese AI, and global AI events — twice a day, via WeChat.

## What it does

- **Morning brief** (07:30 Beijing): top 5 articles per zone, scored by importance
- **Evening digest** (21:00 Beijing): full daily report with cross-zone analysis and a 温故知新 lookback
- Generates both `.md` (for GitHub archiving) and `.html` (for WeChat delivery and future blog use)
- Uses DeepSeek API for importance scoring (`deepseek-chat`) and holistic daily insight (`deepseek-reasoner`)
- Delivers the HTML file to WeChat via ilink API

## Content zones

| Zone | Sources |
|------|---------|
| Claude / Anthropic | anthropic.com/news, anthropic.com/research, GitHub anthropics org |
| 国内 AI 动态 | 机器之心, 量子位, 36kr, 极客公园 |
| 全球 AI 大事件 | OpenAI blog, Google DeepMind, Hugging Face, The Verge AI, TechCrunch AI |

## Setup

### 1. Clone and install dependencies

```bash
git clone https://github.com/faruheaisha/claude-digest-bot
cd claude-digest-bot
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and fill in your keys:
#   DEEPSEEK_API_KEY  — from https://platform.deepseek.com
#   ILINK_TOKEN       — your ilink WeChat bridge token
#   WECHAT_UID        — your WeChat UID
#   GITHUB_TOKEN      — optional, increases GitHub API rate limit
```

### 3. Test with dry-run

```bash
python main.py --mode evening --dry-run
```

This generates files under `archive/YYYY/MM/` without sending to WeChat.

### 4. Schedule with cron (server, UTC timezone)

```cron
# Morning brief  07:30 Beijing = 23:30 UTC
30 23 * * * cd /path/to/claude-digest-bot && python main.py --mode morning >> logs/cron.log 2>&1

# Evening digest 21:00 Beijing = 13:00 UTC
0 13 * * * cd /path/to/claude-digest-bot && python main.py --mode evening >> logs/cron.log 2>&1
```

## Project structure

```
claude-digest-bot/
├── main.py                  # Entry point
├── config.yaml              # Source URLs, fetch limits, schedule config
├── fetchers/                # Per-source scrapers (RSS + HTML scrape)
├── processors/              # DeepSeek scoring, dedup, cross-zone linking
├── formatters/              # .md and .html output renderers
├── delivery/                # WeChat ilink file delivery
└── templates/               # Jinja2 HTML template
```

## WeChat delivery setup

This bot requires a running [wechat-claude-code](https://github.com/faruheaisha/wechat-claude-code) instance with a valid ilink token. See that project's README for setup instructions. Once configured, copy your `ILINK_TOKEN` and `WECHAT_UID` into `.env`.

## Archive

Generated digests are saved to `archive/YYYY/MM/YYYY-MM-DD-{morning,evening}.{md,html}`. The `archive/` directory is gitignored by default — add it to version control if you want a public historical record.

## License

MIT
