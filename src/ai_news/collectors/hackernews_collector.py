"""
Hacker News Collector
---------------------
Fetches the current Top Stories from the Hacker News Firebase API.
Returns only story-type items that have an external URL.
"""

import logging
from typing import Dict, List

import requests

logger = logging.getLogger(__name__)

HN_TOP_STORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL        = "https://hacker-news.firebaseio.com/v0/item/{id}.json"
DEFAULT_LIMIT      = 30
REQUEST_TIMEOUT    = 8  # seconds


def _fetch_item(story_id: int) -> Dict | None:
    """Fetch a single HN item by ID. Returns None on failure."""
    try:
        resp = requests.get(
            HN_ITEM_URL.format(id=story_id),
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning("[HN] Could not fetch item %d: %s", story_id, exc)
        return None


def collect_all(limit: int = DEFAULT_LIMIT) -> List[Dict]:
    """
    Fetch the top `limit` stories from Hacker News.

    Only stories with an external URL are returned (Ask HN / jobs are skipped).

    Args:
        limit:  Maximum number of story IDs to process.

    Returns:
        List of article dicts following the collectors schema.
    """
    stories: List[Dict] = []

    # ── 1. Get the ranked list of story IDs ──────────────────────────────────
    try:
        resp = requests.get(HN_TOP_STORIES_URL, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        story_ids: List[int] = resp.json()[:limit]
    except Exception as exc:
        logger.error("[HN] Failed to fetch top stories list: %s", exc)
        return stories

    # ── 2. Fetch each story ───────────────────────────────────────────────────
    for story_id in story_ids:
        item = _fetch_item(story_id)
        if not item:
            continue

        # Skip non-story types (Ask HN, polls, jobs without URL)
        if item.get("type") != "story":
            continue

        url = item.get("url", "").strip()
        if not url:
            # Ask HN / self-posts: build an HN link instead
            url = f"https://news.ycombinator.com/item?id={story_id}"

        title = (item.get("title") or "").strip()
        if not title:
            continue

        score    = item.get("score", 0)
        comments = item.get("descendants", 0)

        stories.append({
            "source":    "Hacker News",
            "title":     title,
            "url":       url,
            "summary":   f"⬆️ {score} points · 💬 {comments} comments",
            "published": None,   # HN doesn't expose RFC-822 dates via API
            "type":      "article",
            # HN-specific extras
            "hn_score":    score,
            "hn_comments": comments,
            "hn_id":       story_id,
        })

    logger.info("[HN] Collected %d stories (limit=%d)", len(stories), limit)
    return stories
