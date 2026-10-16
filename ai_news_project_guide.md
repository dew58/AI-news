# 🗞️ AI Daily News Digest — Project Guide

## Overview

An automated AI-powered daily news digest that:
- **Collects** articles from RSS feeds, Hacker News, YouTube, LinkedIn, OpenAI & Anthropic blogs
- **Analyzes & ranks** content using Google Gemini LLM
- **Delivers** a beautifully formatted HTML email to your inbox every day
- **Runs** on Render (free tier) with a configurable schedule

---

## 🗂️ Project Structure

```
AI-news/
│
├── README.md
├── .env.example                  # Template for environment variables
├── .gitignore
├── requirements.txt              # Python dependencies
├── render.yaml                   # Render deployment config
│
├── config/
│   └── sources.yaml              # All news sources (RSS URLs, YouTube channels, etc.)
│
├── src/
│   ├── __init__.py
│   │
│   ├── collectors/               # Data collection modules
│   │   ├── __init__.py
│   │   ├── rss_collector.py      # RSS feeds (TechCrunch, ArXiv, Wired, etc.)
│   │   ├── hackernews_collector.py  # Hacker News Top Stories API
│   │   ├── youtube_collector.py  # YouTube Data API v3
│   │   ├── linkedin_collector.py # LinkedIn (via RSS or scraping)
│   │   └── blog_collector.py     # OpenAI & Anthropic official blogs
│   │
│   ├── analyzer/                 # LLM analysis with Google Gemini
│   │   ├── __init__.py
│   │   ├── gemini_client.py      # Gemini API wrapper
│   │   └── news_analyzer.py      # Ranking, summarizing, categorizing news
│   │
│   ├── digest/                   # Email digest generation
│   │   ├── __init__.py
│   │   ├── email_builder.py      # Build HTML email from ranked stories
│   │   └── templates/
│   │       └── digest.html       # Jinja2 HTML email template
│   │
│   ├── delivery/                 # Email delivery
│   │   ├── __init__.py
│   │   └── gmail_sender.py       # Gmail SMTP sender
│   │
│   └── pipeline.py               # Main pipeline orchestrating all steps
│
├── scheduler/
│   └── cron_runner.py            # Cron-style scheduler (APScheduler)
│
└── tests/
    ├── test_collectors.py
    ├── test_analyzer.py
    └── test_email.py
```

---

## ⚙️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11+ |
| News Collection | `feedparser`, `requests`, `youtube-data-api` |
| LLM Analysis | Google Gemini (`google-generativeai`) |
| Email Template | `Jinja2` |
| Email Delivery | Gmail SMTP via `smtplib` |
| Scheduling | `APScheduler` |
| Deployment | Render (free tier — cron job or background worker) |
| Config | `.env` + `sources.yaml` |

---

## 📡 Data Sources

### RSS / Articles
| Source | RSS URL |
|--------|---------|
| TechCrunch AI | `https://techcrunch.com/category/artificial-intelligence/feed/` |
| ArXiv CS.AI | `https://rss.arxiv.org/rss/cs.AI` |
| Wired | `https://www.wired.com/feed/rss` |
| MIT Tech Review | `https://www.technologyreview.com/feed/` |
| The Verge | `https://www.theverge.com/rss/index.xml` |

### Hacker News
- Top 30 stories via: `https://hacker-news.firebaseio.com/v0/topstories.json`

### YouTube
- Uses **YouTube Data API v3** (free, 10,000 units/day)
- Tracks specific channels you configure (e.g. Two Minute Papers, Andrej Karpathy, etc.)
- Gets latest videos + transcripts via `youtube-transcript-api`

### LinkedIn
- Uses **RSS bridges** or curated profile feeds (LinkedIn doesn't have a public API)
- Alternatively, tracks company pages via `linkedin-api` (unofficial)

### Official Blogs
| Source | URL |
|--------|-----|
| OpenAI Blog | `https://openai.com/news/rss.xml` |
| Anthropic Blog | `https://www.anthropic.com/rss.xml` |
| Google DeepMind | `https://deepmind.google/blog/rss.xml` |

---

## 🤖 LLM Analysis Pipeline (Gemini)

The analyzer will receive all collected articles and perform:

1. **Deduplication** — remove duplicate stories across sources
2. **Importance Ranking** — LLM scores each story 1–10 for relevance to your topics (AI & Tech)
3. **Summarization** — 2–3 sentence summary per story
4. **YouTube Summary** — brief summary of new videos from tracked channels
5. **LinkedIn Highlights** — key posts from tracked profiles/companies
6. **OpenAI / Anthropic Spotlights** — dedicated section for official announcements

> [!IMPORTANT]
> The LLM prompt is **fully customizable** — you'll define exactly how stories are ranked, what counts as "important," and the tone/format of summaries. You said you'll provide this prompt later, so we'll leave a clear `PROMPT_TEMPLATE` placeholder in the code.

---

## 📧 Email Digest Format

The email will have clearly separated sections:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🗞️  AI & Tech Daily Digest — Oct 16, 2026
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔥 TOP STORIES (Ranked by AI)
  1. [Story Title] — Source
     Summary...

📺 YOUTUBE HIGHLIGHTS
  - [Video Title] — Channel Name
    Summary...

💼 LINKEDIN HIGHLIGHTS
  - Post highlight...

🧠 OPENAI & ANTHROPIC NEWS
  - [Announcement Title]
    Summary...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 🚀 Deployment on Render (Free Tier)

1. Push project to **GitHub**
2. Create a **Render Background Worker** (free tier)
3. Set environment variables in Render dashboard
4. Use `APScheduler` inside the worker to run the pipeline at your custom time

> [!NOTE]
> Render free tier spins down after inactivity. For a cron job, use **Render Cron Job** service type instead — it's designed for scheduled tasks and stays free.

---

## 🔐 Environment Variables (`.env`)

```env
# Google Gemini
GEMINI_API_KEY=your_gemini_api_key

# Gmail SMTP
GMAIL_ADDRESS=your@gmail.com
GMAIL_APP_PASSWORD=your_app_password   # Not your regular password!
RECIPIENT_EMAIL=your@gmail.com

# YouTube Data API
YOUTUBE_API_KEY=your_youtube_api_key

# Schedule (24h format, e.g. "07:00" or "19:00")
DIGEST_TIME=07:00
DIGEST_TIMEZONE=Asia/Jerusalem          # Your local timezone
```

---

## 📋 Development Phases

### Phase 1 — Collectors ✅
- [ ] RSS feed collector
- [ ] Hacker News collector
- [ ] YouTube collector
- [ ] OpenAI & Anthropic blog collector
- [ ] LinkedIn collector (basic)

### Phase 2 — LLM Analyzer ✅
- [ ] Gemini API client
- [ ] News analysis & ranking (prompt placeholder ready)
- [ ] Story deduplication

### Phase 3 — Email Digest ✅
- [ ] HTML email template (Jinja2)
- [ ] Gmail SMTP sender
- [ ] Test email delivery

### Phase 4 — Scheduling & Deployment ✅
- [ ] APScheduler integration
- [ ] Render deployment config (`render.yaml`)
- [ ] GitHub Actions CI (optional lint/test)

### Phase 5 — LLM Prompt (Your Input) 🔜
- [ ] You provide your custom ranking/analysis prompt
- [ ] We integrate it into `news_analyzer.py`

---

## 🔑 API Keys You'll Need

| Service | Where to Get It | Cost |
|---------|----------------|------|
| **Google Gemini** | [aistudio.google.com](https://aistudio.google.com) | Free tier available |
| **YouTube Data API v3** | [Google Cloud Console](https://console.cloud.google.com) | Free (10k units/day) |
| **Gmail App Password** | Google Account → Security → 2FA → App Passwords | Free |

---

## 🛑 Limitations & Notes

> [!WARNING]
> **LinkedIn** does not have an official public API for post scraping. We'll use RSS bridges or curated profile monitoring. This may be limited.

> [!NOTE]
> **YouTube transcripts** are only available for videos that have auto-generated or manual captions enabled. Most major channels have them.

> [!TIP]
> Start by testing the pipeline locally with `python src/pipeline.py --test` before deploying to Render.
