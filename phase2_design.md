# 🧠 Phase 2 — LLM Analyzer Design Plan

## What Phase 2 Does

Takes the **1,064 raw collected items** from Phase 1 and produces a
**structured, ranked digest payload** ready for Phase 3 to render into an email.

---

## Pipeline Flow

```
Phase 1 output (1,064 items)
        │
        ▼
┌─────────────────────┐
│  1. Keyword Filter  │  ← Drop clearly off-topic items (e.g. sports, politics)
│  (news_analyzer.py) │    ~1,064 → ~200–400 items remaining
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  2. Deduplication   │  ← Group items with identical/very similar titles
│  (news_analyzer.py) │    across sources (e.g. same story on HN + TechCrunch)
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  3. Gemini Analysis │  ← Send shortlist to Gemini Flash (cheap, fast)
│  (gemini_client.py) │    Gemini: ranks, categorizes, flags breaking news,
│  (news_analyzer.py) │    writes opinionated 2–3 sentence summaries
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  4. Build Output    │  ← Assemble structured digest dict:
│  (news_analyzer.py) │    top_stories (5), youtube_section, blog_spotlight
└────────┬────────────┘
         │
         ▼
  Structured digest dict  →  Phase 3 (email builder)
```

---

## Files to Build

### `src/ai_news/analyzer/gemini_client.py`  ← NEW (full code)
Thin wrapper around `google-generativeai` SDK.

**Responsibilities:**
- Load `GEMINI_API_KEY` from environment
- Configure the model (`gemini-2.0-flash` — free tier, 1M token context)
- Expose one method: `generate(prompt, system_instruction) → str`
- Handle rate limit / API errors with retry + exponential backoff
- Log token usage per call

---

### `src/ai_news/analyzer/news_analyzer.py`  ← NEW (full code)
The core analysis logic.

**Responsibilities:**

#### Step 1 — `keyword_filter(items) → items`
Keep only items whose title/summary contain at least one keyword from a
configurable whitelist. Default whitelist covers:
`AI, LLM, model, GPT, Claude, Gemini, machine learning, neural, robot,
research, paper, launch, open source, startup, chip, GPU, ...`

#### Step 2 — `deduplicate(items) → items`
Simple title-similarity dedup using fuzzy matching (`difflib`).
Groups near-duplicate titles and keeps only the highest-priority source
(blog > article > HN > YouTube).

#### Step 3 — `analyze_with_gemini(items) → digest_payload`
Sends the shortlist to Gemini with a structured prompt. Gemini returns
JSON with:
- `top_stories`: list of 5 ranked story objects
- `blog_spotlight`: any OpenAI/Anthropic/DeepMind posts (high priority)
- `breaking`: items published < 6 hours ago
- `youtube_summaries`: summaries of the YouTube items

#### Step 4 — `run(items) → digest_payload`
The public entry point that chains all 4 steps.

---

## Gemini Prompt Strategy

**Model:** `gemini-2.0-flash` (free tier: 15 req/min, 1M tokens/day)

**System instruction (fixed):**
> You are an expert AI/tech news curator and analyst. You have an opinionated,
> smart voice — like a brilliant colleague who's read everything and tells you
> what actually matters. Be direct, insightful, and occasionally witty.

**User prompt (per run):** Sends the filtered/deduped items as a JSON list
and asks Gemini to return a structured JSON response.

**Token budget:**
- Pre-filter brings ~1,064 → ~200–300 items
- Each item ~100 tokens avg = ~25,000 tokens input
- Well within `gemini-2.0-flash` free tier limits

---

## Output Schema (`digest_payload`)

```python
{
    "top_stories": [
        {
            "rank":     1,
            "title":    str,
            "url":      str,
            "source":   str,
            "category": str,   # "Research" | "Product Launch" | "Industry News" | "Opinion"
            "summary":  str,   # 2–3 sentence opinionated summary from Gemini
            "score":    int,   # 1–10 relevance score
            "breaking": bool,  # True if published < 6h ago
        },
        ...  # 5 total
    ],
    "blog_spotlight": [
        # OpenAI / Anthropic / DeepMind posts — always included if present
        { "title": str, "url": str, "source": str, "summary": str }
    ],
    "youtube_section": [
        { "title": str, "url": str, "channel": str, "summary": str }
    ],
    "stats": {
        "total_collected":  int,
        "after_filter":     int,
        "after_dedup":      int,
        "gemini_model":     str,
    }
}
```

---

## Files Changed / Created

| File | Action |
|------|--------|
| `src/ai_news/analyzer/gemini_client.py` | Full code (was stub) |
| `src/ai_news/analyzer/news_analyzer.py` | Full code (was stub) |
| `src/ai_news/analyzer/__init__.py` | Updated exports |
| `src/ai_news/pipeline.py` | Wire `analyze()` to call `news_analyzer.run()` |
| `tests/test_analyzer.py` | Tests for filter, dedup, and output schema |

> [!IMPORTANT]
> You need to add `GEMINI_API_KEY` to your `.env` file before Phase 2 will run.
> Get a free key at: https://aistudio.google.com

---

## What is NOT in Phase 2
- Email rendering (Phase 3)
- Sending email (Phase 4)
- Scheduling (Phase 4)
- LinkedIn analysis (depends on whether you configure RSS bridges)
