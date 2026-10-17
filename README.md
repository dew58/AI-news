# AI & Tech Daily News Digest

An automated Python application that gathers recent AI and technology news, analyzes and ranks it with Google Gemini, renders a responsive HTML digest, and can deliver it to an inbox through Gmail. It can also save a local preview or run on a daily schedule.

> **First run:** a real email requires internet access, a working Gemini API key, a Gmail App Password, and a recipient address. The test suite never contacts real APIs or sends email. If you want to inspect the layout before configuring Gmail, run preview mode.

## How it works

```text
config/sources.yaml + environment
			  ↓
Phase 1: RSS, blog, Hacker News, YouTube, optional LinkedIn RSS
			  ↓
Phase 2: normalize, deduplicate, filter, rank, summarize (Gemini + cache/fallback)
			  ↓
Phase 3: render digest_payload into HTML (Jinja2)
			  ↓
Phase 4: save preview OR send via Gmail SMTP_SSL OR run daily via APScheduler
```

### Project layout

- `src/ai_news/pipeline.py` — CLI and orchestration for collection through delivery.
- `src/ai_news/collectors/` — source-specific collectors.
- `src/ai_news/analyzer/` — Gemini client, analysis, validation, fallback, and SQLite cache.
- `src/ai_news/digest/` — Jinja2 HTML email rendering and template.
- `src/ai_news/delivery/gmail_sender.py` — Gmail SSL SMTP transport.
- `src/ai_news/scheduler/cron_runner.py` — daily scheduling with configured timezone.
- `config/sources.yaml` — feeds, channel IDs, and collection windows.
- `tests/` — unit and integration tests; network, Gemini, and SMTP are mocked where appropriate.
- `phase3_plan.md`, `phase4_plan.md` — implementation plans for the delivery phases.

### Phase handoff

Collectors produce item dictionaries (`title`, `url`, `source`, `summary`, `published`, `type`). The analyzer returns a `digest_payload` with `top_stories`, `blog_spotlight`, `youtube_section`, and `stats`. The renderer consumes that payload and returns HTML. Delivery accepts the HTML string and sends it separately. Preview mode stops before SMTP.

## Requirements

- Python 3.13 or newer (see `.python-version` and `pyproject.toml`).
- [`uv`](https://docs.astral.sh/uv/) for environment and dependency management (recommended).
- Internet access for live news collection and Gemini analysis.
- A Gemini API key for AI ranking/summaries.
- For actual mail: Gmail with 2-Step Verification and a Gmail App Password. Do not use your normal Google account password.

## Install

From the repository root:

```powershell
uv sync
Copy-Item .env.example .env
```

Edit `.env` and provide at least:

```dotenv
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.0-flash
GMAIL_ADDRESS=you@gmail.com
GMAIL_APP_PASSWORD=your_16_character_app_password
RECIPIENT_EMAIL=you@example.com
```

Create a Gemini key in [Google AI Studio](https://aistudio.google.com/). Create a Gmail App Password in your Google Account security settings after enabling 2-Step Verification. Store real values only in `.env` (already ignored by Git); never commit them or paste them into logs/issues. For Gmail, `GMAIL_ADDRESS` is the sending account and `RECIPIENT_EMAIL` is the destination; they may be the same.

Additional settings in `.env`:

| Variable | Default | Purpose |
| --- | --- | --- |
| `NEWS_ANALYZER_CANDIDATE_LIMIT` | `60` | Maximum candidate groups sent for analysis |
| `NEWS_ANALYZER_TOP_STORIES` | `5` | Maximum ranked top stories |
| `NEWS_ANALYZER_BREAKING_HOURS` | `6` | Recency window for the breaking label |
| `NEWS_ANALYZER_RETRY_LIMIT` | `3` | Bounded Gemini retry attempts |
| `YOUTUBE_API_KEY` | unset | Optional key for YouTube API collection, if required by collector configuration |
| `DIGEST_TIME` | `07:00` | Daily scheduler time in 24-hour `HH:MM` format |
| `DIGEST_TIMEZONE` | `UTC` | IANA timezone name, e.g. `Asia/Jerusalem` |

Review `config/sources.yaml` to add/remove feeds and YouTube channels or tune collection windows. LinkedIn is optional and requires a working RSS bridge URL. External feeds and public bridge availability can change independently of this application.

## Run it yourself

### 1. Inspect a local HTML digest (recommended first)

```powershell
uv run ai-news --preview
```

The command runs collection, analysis, and HTML rendering, then writes `digest-preview.html` in the current directory. It does **not** send email and does not require Gmail settings. Open the file in a browser. Gemini configuration/network is still needed for successful AI analysis; if Gemini is unavailable, the analyzer may use its documented local fallback.

Choose another output path if desired:

```powershell
uv run ai-news --preview .\output\tech-digest.html
```

### 2. Send an email now

After setting `GEMINI_API_KEY`, `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, and `RECIPIENT_EMAIL` in `.env`, run:

```powershell
uv run ai-news
```

This executes all phases and sends one HTML digest. It will fail with an actionable configuration error if required mail settings are absent. Gmail delivery uses TLS-protected SMTP on `smtp.gmail.com:465`.

### 3. Collection-only check

```powershell
uv run ai-news --test
```

This runs Phase 1 only and prints collected items as JSON. It needs network access but does not invoke Gemini, render the digest, or send email.

### 4. Run every day

Set `DIGEST_TIME` and `DIGEST_TIMEZONE` in `.env`, then start:

```powershell
uv run ai-news --schedule
```

Keep this process running for the scheduled job to execute. The first send happens at the next scheduled occurrence, not immediately. Stop with Ctrl+C. For an always-on deployment, configure a persistent worker and its environment secrets; `render.yaml` is only a placeholder and is not a ready-to-deploy service definition.

## Test

Run the complete suite:

```powershell
uv run pytest -q
```

The tests cover collectors/analyzer behavior and the Phase 2 → HTML → delivery/scheduler handoffs. SMTP and external analysis are mocked, so tests do not send mail, consume Gemini quota, or depend on live feeds. Some collector tests may contact public sources; check `tests/test_collectors.py` before running those in an offline environment.

## Troubleshooting

- **Missing mail setting:** ensure all three `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, and `RECIPIENT_EMAIL` values exist in the root `.env`.
- **Gmail authentication rejected:** verify 2-Step Verification is enabled and use a Gmail App Password, not your regular password. Remove spaces if copied; the sender strips spaces automatically.
- **Gemini key/model error or quota:** check the key, configured `GEMINI_MODEL`, account access, and current API quota. The model name in `.env.example` is an example and model availability can change.
- **No stories or incomplete sections:** feeds may have no recent items, a source may be unavailable, or the analyzer may fall back after API errors. Inspect application logs and the returned analyzer warnings.
- **Scheduler rejects configuration:** use `HH:MM` for `DIGEST_TIME` and a valid IANA timezone such as `UTC` or `Asia/Jerusalem`.
- **YouTube/LinkedIn is empty:** verify channel IDs/API access or RSS bridge URLs. These integrations depend on external services and optional configuration.

## Security and limitations

- The HTML template autoescapes content and only links absolute HTTP(S) URLs.
- Email/API credentials belong in local environment settings, not source control.
- Source collection and third-party APIs are best-effort; availability, quotas, and feed formats are not guaranteed.
- The analyzer's local fallback is not equivalent to Gemini analysis. Review run warnings before relying on a digest.
- The scheduler is a long-running local process; it is not a hosted service by itself.
