"""
YouTube Collector
-----------------
Fetches the latest videos from a configured set of YouTube channels
using the YouTube Data API v3.

Optionally retrieves a short transcript snippet via youtube-transcript-api
to give the LLM richer context for summarization.

Requirements:
    - YOUTUBE_API_KEY must be set in the environment (.env file).
    - Free quota: 10,000 units/day. Each search request costs ~100 units,
      so tracking up to ~100 channels/day is well within the free tier.
"""

import logging
import os
from typing import Dict, List

import requests
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound

logger = logging.getLogger(__name__)

YOUTUBE_API_BASE  = "https://www.googleapis.com/youtube/v3"
DEFAULT_MAX_RESULTS = 5
TRANSCRIPT_MAX_CHARS = 600  # How much of the transcript to include

# ── Default channels (overridable via sources.yaml) ───────────────────────────
DEFAULT_CHANNELS: Dict[str, str] = {
    "Two Minute Papers": "UCbfYPyITQ-7l4upoX8nvctg",
    "Google DeepMind":   "UCP4bf6IHJJQehibu6ai__cg",
    "OpenAI":            "UCXZCJLdBC09xxGZ6gcdrc6A",
    "Yannic Kilcher":    "UCZHmQk67mSJgfCCTn7xBfew",
    "Lex Fridman":       "UCSHZKyawb77ixDdsGog4iWA",
    "AI Explained":      "UCNJ1Ymd5yFuUPtn21xtRbbw",
}


def _get_api_key() -> str | None:
    """Return the YouTube API key from the environment."""
    key = os.getenv("YOUTUBE_API_KEY", "").strip()
    return key if key else None


def _fetch_transcript(video_id: str) -> str:
    """
    Try to fetch a short transcript snippet for a given video.

    Returns an empty string if transcripts are unavailable or disabled.
    """
    try:
        segments = YouTubeTranscriptApi.get_transcript(video_id, languages=["en"])
        full_text = " ".join(seg["text"] for seg in segments)
        return full_text[:TRANSCRIPT_MAX_CHARS].strip()
    except (TranscriptsDisabled, NoTranscriptFound):
        return ""
    except Exception as exc:
        logger.debug("[YouTube] Transcript unavailable for %s: %s", video_id, exc)
        return ""


def fetch_channel_videos(
    channel_id: str,
    channel_name: str,
    api_key: str,
    max_results: int = DEFAULT_MAX_RESULTS,
) -> List[Dict]:
    """
    Fetch the latest `max_results` videos from a YouTube channel.

    Args:
        channel_id:   YouTube channel ID (not the handle/@name).
        channel_name: Human-readable label used in the digest.
        api_key:      YouTube Data API v3 key.
        max_results:  Max videos to return per channel.

    Returns:
        List of video dicts following the collectors schema.
    """
    videos: List[Dict] = []

    try:
        params = {
            "part":      "snippet",
            "channelId": channel_id,
            "maxResults": max_results,
            "order":     "date",
            "type":      "video",
            "key":       api_key,
        }
        resp = requests.get(f"{YOUTUBE_API_BASE}/search", params=params, timeout=10)
        resp.raise_for_status()
        items = resp.json().get("items", [])

    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 403:
            logger.error(
                "[YouTube] 403 Forbidden for channel '%s'. "
                "Check your YOUTUBE_API_KEY and quota.",
                channel_name,
            )
        else:
            logger.error("[YouTube] HTTP error for '%s': %s", channel_name, exc)
        return videos
    except Exception as exc:
        logger.error("[YouTube] Failed to fetch channel '%s': %s", channel_name, exc)
        return videos

    for item in items:
        video_id = item.get("id", {}).get("videoId")
        if not video_id:
            continue

        snippet = item.get("snippet", {})
        title   = (snippet.get("title") or "").strip()
        if not title:
            continue

        description       = (snippet.get("description") or "")[:300].strip()
        published_at      = snippet.get("publishedAt")           # ISO-8601
        thumbnail_url     = (
            snippet.get("thumbnails", {})
            .get("medium", {})
            .get("url", "")
        )
        transcript_snippet = _fetch_transcript(video_id)

        videos.append({
            "source":             f"YouTube — {channel_name}",
            "title":              title,
            "url":                f"https://www.youtube.com/watch?v={video_id}",
            "summary":            description,
            "published":          published_at,
            "type":               "youtube",
            # YouTube-specific extras
            "transcript_snippet": transcript_snippet,
            "thumbnail_url":      thumbnail_url,
            "video_id":           video_id,
        })

    logger.info("[YouTube] %-25s → %d videos", channel_name, len(videos))
    return videos


def collect_all(
    channels: Dict[str, str] | None = None,
    max_results: int = DEFAULT_MAX_RESULTS,
) -> List[Dict]:
    """
    Collect latest videos from all configured YouTube channels.

    Args:
        channels:    Dict of {channel_name: channel_id}.
                     Falls back to DEFAULT_CHANNELS if not provided.
        max_results: Max videos to fetch per channel.

    Returns:
        Combined list of video dicts from all channels.
    """
    api_key = _get_api_key()
    if not api_key:
        logger.warning(
            "[YouTube] YOUTUBE_API_KEY is not set. Skipping YouTube collection. "
            "Get a free key at https://console.cloud.google.com"
        )
        return []

    channels = channels or DEFAULT_CHANNELS
    all_videos: List[Dict] = []

    for name, channel_id in channels.items():
        all_videos.extend(fetch_channel_videos(channel_id, name, api_key, max_results))

    logger.info(
        "[YouTube] Total collected: %d videos from %d channels",
        len(all_videos),
        len(channels),
    )
    return all_videos
