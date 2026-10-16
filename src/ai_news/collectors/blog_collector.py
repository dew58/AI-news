"""
Official AI Company Blog Collector
------------------------------------
Fetches recent posts from the official blogs of major AI companies
(OpenAI, Anthropic, Google DeepMind, Hugging Face, Mistral, etc.).

These are treated as high-priority items in the digest and get their
own dedicated section, separate from general RSS articles.

Uses feedparser just like the RSS collector, but:
  - A wider time window (72 h default) because AI blogs post infrequently.
  - Items are tagged with type="blog" so downstream analysis can surface
    them in the "Company Announcements" section.
"""

import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, List

import feedparser

logger = logging.getLogger(__name__)

# ── Default blog feeds (overridable via sources.yaml) ────────────────────────
DEFAULT_BLOG_FEEDS: Dict[str, str] = {
    "OpenAI":         "https://openai.com/news/rss.xml",
    # Anthropic has no official RSS — using a community RSSHub mirror
    "Anthropic":      "https://rsshub.app/anthropic/news",
    "Google DeepMind":"https://deepmind.google/blog/rss.xml",
    "Hugging Face":   "https://huggingface.co/blog/feed.xml",
    "Mistral AI":     "https://mistral.ai/news/rss/",
}

DEFAULT_MAX_AGE_HOURS = 72  # wider window — these blogs don't post every day


def _parse_date(entry) -> datetime | None:
    """Safely extract a tz-aware datetime from a feedparser entry."""
    for attr in ("published_parsed", "updated_parsed"):
        value = getattr(entry, attr, None)
        if value:
            try:
                return datetime(*value[:6], tzinfo=timezone.utc)
            except Exception:
                continue
    return None


def _clean_summary(raw: str, max_chars: int = 600) -> str:
    """Strip HTML tags and truncate."""
    text = re.sub(r"<[^>]+>", "", raw or "")
    return text[:max_chars].strip()


def fetch_blog(
    company: str,
    url: str,
    max_age_hours: int = DEFAULT_MAX_AGE_HOURS,
) -> List[Dict]:
    """
    Fetch recent posts from a single company blog feed.

    Args:
        company:       Human-readable company name (e.g. "OpenAI").
        url:           RSS/Atom feed URL.
        max_age_hours: Ignore posts older than this many hours.

    Returns:
        List of blog post dicts following the collectors schema.
    """
    posts: List[Dict] = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)

    try:
        feed = feedparser.parse(url)

        if feed.bozo and not feed.entries:
            logger.warning("[Blog] %s — feed error: %s", company, feed.bozo_exception)
            return posts

        for entry in feed.entries:
            published = _parse_date(entry)

            if published and published < cutoff:
                continue

            title = (entry.get("title") or "").strip()
            link  = (entry.get("link")  or "").strip()
            if not title or not link:
                continue

            posts.append({
                "source":    f"{company} Blog",
                "title":     title,
                "url":       link,
                "summary":   _clean_summary(entry.get("summary", "")),
                "published": published.isoformat() if published else None,
                "type":      "blog",
            })

        logger.info("[Blog]  %-20s → %d posts", company, len(posts))

    except Exception as exc:
        logger.error("[Blog] Failed to fetch '%s' (%s): %s", company, url, exc)

    return posts


def collect_all(
    feeds: Dict[str, str] | None = None,
    max_age_hours: int = DEFAULT_MAX_AGE_HOURS,
) -> List[Dict]:
    """
    Collect posts from all configured AI company blogs.

    Args:
        feeds:         Dict of {company_name: feed_url}.
                       Falls back to DEFAULT_BLOG_FEEDS.
        max_age_hours: Posts older than this are ignored.

    Returns:
        Combined list of blog post dicts.
    """
    feeds = feeds or DEFAULT_BLOG_FEEDS
    all_posts: List[Dict] = []

    for company, url in feeds.items():
        all_posts.extend(fetch_blog(company, url, max_age_hours))

    logger.info("[Blog]  Total collected: %d posts from %d blogs", len(all_posts), len(feeds))
    return all_posts
