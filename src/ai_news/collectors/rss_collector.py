"""
RSS Feed Collector
------------------
Fetches recent articles from a configurable set of RSS/Atom feeds.
Articles older than `max_age_hours` are filtered out automatically.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List

import feedparser

logger = logging.getLogger(__name__)

# ── Default feed list (overridable via sources.yaml) ──────────────────────────
DEFAULT_RSS_FEEDS: Dict[str, str] = {
    "TechCrunch AI":  "https://techcrunch.com/category/artificial-intelligence/feed/",
    "ArXiv CS.AI":    "https://rss.arxiv.org/rss/cs.AI",
    "ArXiv CS.LG":    "https://rss.arxiv.org/rss/cs.LG",
    "Wired":          "https://www.wired.com/feed/rss",
    "MIT Tech Review":"https://www.technologyreview.com/feed/",
    "The Verge":      "https://www.theverge.com/rss/index.xml",
    "VentureBeat AI": "https://venturebeat.com/category/ai/feed/",
}


def _parse_date(entry) -> datetime | None:
    """Safely extract a timezone-aware datetime from a feedparser entry."""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        except Exception:
            pass
    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        try:
            return datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
        except Exception:
            pass
    return None


def _clean_summary(summary: str, max_chars: int = 500) -> str:
    """Strip HTML tags and truncate a summary string."""
    import re
    text = re.sub(r"<[^>]+>", "", summary or "")
    return text[:max_chars].strip()


def fetch_feed(name: str, url: str, max_age_hours: int = 24) -> List[Dict]:
    """
    Fetch and parse a single RSS/Atom feed.

    Args:
        name:           Human-readable source label.
        url:            RSS/Atom feed URL.
        max_age_hours:  Discard articles published more than this many hours ago.

    Returns:
        List of article dicts following the collectors schema.
    """
    articles: List[Dict] = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)

    try:
        feed = feedparser.parse(url)

        if feed.bozo and not feed.entries:
            logger.warning("[RSS] %s — feed parse error: %s", name, feed.bozo_exception)
            return articles

        for entry in feed.entries:
            published = _parse_date(entry)

            # Skip articles that are too old (only when we have a date)
            if published and published < cutoff:
                continue

            title = (entry.get("title") or "").strip()
            link  = (entry.get("link")  or "").strip()

            if not title or not link:
                continue

            articles.append({
                "source":    name,
                "title":     title,
                "url":       link,
                "summary":   _clean_summary(entry.get("summary", "")),
                "published": published.isoformat() if published else None,
                "type":      "article",
            })

        logger.info("[RSS] %-20s → %d articles", name, len(articles))

    except Exception as exc:
        logger.error("[RSS] Failed to fetch '%s' (%s): %s", name, url, exc)

    return articles


def collect_all(
    feeds: Dict[str, str] | None = None,
    max_age_hours: int = 24,
) -> List[Dict]:
    """
    Collect articles from all RSS feeds.

    Args:
        feeds:          Dict of {name: url}. Falls back to DEFAULT_RSS_FEEDS.
        max_age_hours:  Articles older than this are ignored.

    Returns:
        Combined list of article dicts from all feeds.
    """
    feeds = feeds or DEFAULT_RSS_FEEDS
    all_articles: List[Dict] = []

    for name, url in feeds.items():
        all_articles.extend(fetch_feed(name, url, max_age_hours))

    logger.info("[RSS] Total collected: %d articles from %d feeds", len(all_articles), len(feeds))
    return all_articles
