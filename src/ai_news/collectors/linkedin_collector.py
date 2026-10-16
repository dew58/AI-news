"""
LinkedIn Collector
------------------
LinkedIn does NOT provide a public API for reading posts or company feeds.

This collector uses RSS bridges — lightweight services that expose LinkedIn
company/profile pages as an RSS feed. The recommended approach is RSSHub,
which you can either self-host or use via a public instance.

How to set up:
    1. Find a company's LinkedIn slug (e.g. "openai" from linkedin.com/company/openai)
    2. Build an RSSHub URL:
         https://rsshub.app/linkedin/company/<slug>
       Or self-host RSSHub: https://docs.rsshub.app/deploy/

    3. Add the URL to config/sources.yaml under `linkedin_feeds:`, e.g.:
         linkedin_feeds:
           OpenAI Company: "https://rsshub.app/linkedin/company/openai"

⚠️  NOTE: Public RSSHub instances may be rate-limited or unavailable.
    Self-hosting RSSHub (free, via Docker) is the most reliable option.

If no feeds are configured, this collector returns an empty list and logs
an informational message — it will NOT raise an error.
"""

import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, List

import feedparser

logger = logging.getLogger(__name__)

DEFAULT_LINKEDIN_FEEDS: Dict[str, str] = {}  # Empty by default — user configures
DEFAULT_MAX_AGE_HOURS = 24


def _parse_date(entry) -> datetime | None:
    for attr in ("published_parsed", "updated_parsed"):
        value = getattr(entry, attr, None)
        if value:
            try:
                return datetime(*value[:6], tzinfo=timezone.utc)
            except Exception:
                continue
    return None


def _clean_text(raw: str, max_chars: int = 400) -> str:
    """Strip HTML tags and truncate."""
    text = re.sub(r"<[^>]+>", "", raw or "")
    return text[:max_chars].strip()


def fetch_linkedin_feed(
    name: str,
    url: str,
    max_age_hours: int = DEFAULT_MAX_AGE_HOURS,
) -> List[Dict]:
    """
    Fetch posts from a single LinkedIn RSS bridge feed.

    Args:
        name:          Human-readable label (e.g. "OpenAI Company").
        url:           RSSHub or equivalent RSS bridge URL.
        max_age_hours: Ignore posts older than this many hours.

    Returns:
        List of post dicts following the collectors schema.
    """
    posts: List[Dict] = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)

    try:
        feed = feedparser.parse(url)

        if feed.bozo and not feed.entries:
            logger.warning("[LinkedIn] %s — feed error: %s", name, feed.bozo_exception)
            return posts

        for entry in feed.entries:
            published = _parse_date(entry)

            if published and published < cutoff:
                continue

            title = (entry.get("title") or "").strip()
            link  = (entry.get("link")  or "").strip()
            if not link:
                continue

            # LinkedIn posts often have no title — use first line of summary
            if not title:
                summary = _clean_text(entry.get("summary", ""))
                title = summary[:80] + "…" if len(summary) > 80 else summary

            posts.append({
                "source":    f"LinkedIn — {name}",
                "title":     title,
                "url":       link,
                "summary":   _clean_text(entry.get("summary", "")),
                "published": published.isoformat() if published else None,
                "type":      "linkedin",
            })

        logger.info("[LinkedIn] %-25s → %d posts", name, len(posts))

    except Exception as exc:
        logger.error("[LinkedIn] Failed to fetch '%s' (%s): %s", name, url, exc)

    return posts


def collect_all(
    feeds: Dict[str, str] | None = None,
    max_age_hours: int = DEFAULT_MAX_AGE_HOURS,
) -> List[Dict]:
    """
    Collect posts from all configured LinkedIn RSS bridges.

    Args:
        feeds:         Dict of {page_name: rss_bridge_url}.
                       If None, falls back to DEFAULT_LINKEDIN_FEEDS (empty).
        max_age_hours: Posts older than this are ignored.

    Returns:
        Combined list of post dicts, or [] if no feeds are configured.
    """
    feeds = feeds or DEFAULT_LINKEDIN_FEEDS

    if not feeds:
        logger.info(
            "[LinkedIn] No feeds configured. "
            "Add RSSHub URLs to config/sources.yaml under 'linkedin_feeds' to enable."
        )
        return []

    all_posts: List[Dict] = []
    for name, url in feeds.items():
        all_posts.extend(fetch_linkedin_feed(name, url, max_age_hours))

    logger.info("[LinkedIn] Total collected: %d posts", len(all_posts))
    return all_posts
