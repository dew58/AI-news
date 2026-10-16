"""
AI News Pipeline
----------------
Orchestrates all phases of the digest:
  Phase 1 ✅ — Collect raw news items from all sources
  Phase 2 🔜 — Analyze & rank with Google Gemini
  Phase 3 🔜 — Build the HTML email digest
  Phase 4 🔜 — Send via Gmail SMTP

Run locally for testing:
    python -m ai_news.pipeline          # full run
    python -m ai_news.pipeline --test   # collection only, prints results
"""

import argparse
import json
import logging
import os
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
#  PHASE 2 — Analysis  (stub — implemented in Phase 2)
# ─────────────────────────────────────────────────────────────────────────────

def analyze(items: list[dict]) -> list[dict]:
    """
    [Phase 2 — NOT YET IMPLEMENTED]
    Send collected items to Google Gemini for ranking and summarization.
    """
    logger.info("━━━  Phase 2: Analysis  (stub — coming soon)  ━━━━━━━━━━━━━")
    return items  # pass-through until Phase 2 is built


# ─────────────────────────────────────────────────────────────────────────────
#  PHASE 3 — Digest Build  (stub — implemented in Phase 3)
# ─────────────────────────────────────────────────────────────────────────────

def build_digest(items: list[dict]) -> str:
    """
    [Phase 3 — NOT YET IMPLEMENTED]
    Render the Jinja2 HTML email template from ranked items.
    """
    logger.info("━━━  Phase 3: Build Digest  (stub — coming soon)  ━━━━━━━━━")
    return ""  # empty until Phase 3 is built


# ─────────────────────────────────────────────────────────────────────────────
#  PHASE 4 — Delivery  (stub — implemented in Phase 4)
# ─────────────────────────────────────────────────────────────────────────────

def send(html: str) -> None:
    """
    [Phase 4 — NOT YET IMPLEMENTED]
    Send the HTML digest via Gmail SMTP.
    """
    logger.info("━━━  Phase 4: Send Email  (stub — coming soon)  ━━━━━━━━━━━")


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
    args = parser.parse_args()

    sources = _load_sources()

    # Phase 1
    items = collect(sources)

    if args.test:
        # Write UTF-8 directly to stdout binary buffer to avoid Windows cp1252 errors
        output = json.dumps(items, indent=2, ensure_ascii=False)
        sys.stdout.buffer.write(output.encode("utf-8"))
        sys.stdout.buffer.write(b"\n")
        logger.info("--test mode: stopping after collection.")
        return

    # Phase 2
    ranked = analyze(items)

    # Phase 3
    html = build_digest(ranked)

    # Phase 4
    send(html)

    logger.info("✅  Pipeline complete.")


if __name__ == "__main__":
    main()
