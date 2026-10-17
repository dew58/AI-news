"""
AI News Pipeline
----------------
Orchestrates all phases of the digest:
  Phase 1 ✅ — Collect raw news items from all sources
  Phase 2 ✅ — Analyze & rank with Google Gemini
    Phase 3 ✅ — Build the HTML email digest
    Phase 4 ✅ — Send via Gmail SMTP (or schedule daily runs)

Run locally for testing:
    python -m ai_news.pipeline          # full run and email delivery
    python -m ai_news.pipeline --test   # collection only, prints results
    python -m ai_news.pipeline --preview [digest.html]  # render without sending
    python -m ai_news.pipeline --schedule  # run daily at DIGEST_TIME
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

# ── Setup ─────────────────────────────────────────────────────────────────────
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Collectors (Phase 1) ──────────────────────────────────────────────────────
from ai_news.collectors import (  # noqa: E402
    blog_collector,
    hackernews_collector,
    linkedin_collector,
    rss_collector,
    youtube_collector,
)

# ── Config loader ─────────────────────────────────────────────────────────────
_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "sources.yaml"


def _load_sources() -> dict:
    """Load sources.yaml. Returns empty dict if the file doesn't exist."""
    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    logger.warning("sources.yaml not found at %s — using collector defaults.", _CONFIG_PATH)
    return {}


# ─────────────────────────────────────────────────────────────────────────────
#  PHASE 1 — Collection
# ─────────────────────────────────────────────────────────────────────────────

def collect(sources: dict) -> list[dict]:
    """
    Run all collectors and return a combined list of raw news items.

    Args:
        sources: Parsed sources.yaml config dict.

    Returns:
        List of item dicts (see collectors/__init__.py for the schema).
    """
    settings = sources.get("settings", {})

    rss_age    = int(settings.get("rss_max_age_hours",  24))
    blog_age   = int(settings.get("blog_max_age_hours", 72))
    hn_limit   = int(settings.get("hn_top_stories",     30))
    yt_max     = int(settings.get("youtube_max_per_ch",  5))

    logger.info("━━━  Phase 1: Collection  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    items: list[dict] = []

    # RSS articles
    rss_feeds = sources.get("rss_feeds") or None
    items += rss_collector.collect_all(feeds=rss_feeds, max_age_hours=rss_age)

    # Hacker News
    items += hackernews_collector.collect_all(limit=hn_limit)

    # Official AI blogs
    blog_feeds = sources.get("blog_feeds") or None
    items += blog_collector.collect_all(feeds=blog_feeds, max_age_hours=blog_age)

    # YouTube
    yt_channels = sources.get("youtube_channels") or None
    items += youtube_collector.collect_all(channels=yt_channels, max_results=yt_max)

    # LinkedIn (optional — needs RSS bridge config)
    li_feeds = sources.get("linkedin_feeds") or {}
    items += linkedin_collector.collect_all(feeds=li_feeds)

    logger.info("━━━  Collection complete: %d items total  ━━━━━━━━━━━━━━━━━", len(items))
    return items


# ─────────────────────────────────────────────────────────────────────────────
#  PHASE 2 — Analysis
# ─────────────────────────────────────────────────────────────────────────────

def analyze(items: list[dict]) -> dict:
    from ai_news.analyzer.news_analyzer import run

    logger.info("━━━  Phase 2: Analysis  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    return run(items)


# ─────────────────────────────────────────────────────────────────────────────
#  PHASE 3 — Digest Build
# ─────────────────────────────────────────────────────────────────────────────

def build_digest(digest_payload: dict) -> str:
    """Render the Phase 2 digest payload into an HTML email."""
    from ai_news.digest.email_builder import build_email

    logger.info("━━━  Phase 3: Build Digest  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    return build_email(digest_payload)


# ─────────────────────────────────────────────────────────────────────────────
#  PHASE 4 — Delivery  (stub — implemented in Phase 4)
# ─────────────────────────────────────────────────────────────────────────────

def send(html: str) -> None:
    """Send the rendered digest via Gmail SMTP."""
    from ai_news.delivery.gmail_sender import send_digest

    logger.info("━━━  Phase 4: Send Email  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    send_digest(html)


def run_pipeline(send_email: bool = True, preview_path: str | None = None) -> str:
    """Run collection through rendering, then send or save an HTML preview."""
    sources = _load_sources()
    items = collect(sources)
    digest_payload = analyze(items)
    html = build_digest(digest_payload)
    if preview_path is not None:
        output_path = Path(preview_path).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
        logger.info("HTML digest preview saved to %s", output_path)
    elif send_email:
        send(html)
    return html


def run_schedule() -> None:
    """Start a daily scheduler using DIGEST_TIME and DIGEST_TIMEZONE."""
    from ai_news.scheduler.cron_runner import run_daily

    run_daily(run_pipeline)


# ─────────────────────────────────────────────────────────────────────────────
#  Entry Point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="AI Daily News Digest Pipeline")
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run Phase 1 only and print collected items as JSON",
    )
    parser.add_argument(
        "--preview", nargs="?", const="digest-preview.html", metavar="PATH",
        help="Run collection, analysis, and rendering; save HTML without sending (default: digest-preview.html)",
    )
    parser.add_argument("--schedule", action="store_true", help="Schedule daily email using DIGEST_TIME and DIGEST_TIMEZONE")
    args = parser.parse_args()

    if args.schedule:
        run_schedule()
        return

    # Phase 1
    if args.preview is not None:
        run_pipeline(send_email=False, preview_path=args.preview)
        return

    items = collect(_load_sources())

    if args.test:
        # Write UTF-8 directly to stdout binary buffer to avoid Windows cp1252 errors
        output = json.dumps(items, indent=2, ensure_ascii=False)
        sys.stdout.buffer.write(output.encode("utf-8"))
        sys.stdout.buffer.write(b"\n")
        logger.info("--test mode: stopping after collection.")
        return

    digest_payload = analyze(items)
    html = build_digest(digest_payload)
    send(html)

    logger.info("✅  Pipeline complete.")


if __name__ == "__main__":
    main()
