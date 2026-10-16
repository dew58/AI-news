"""
Phase 1 Collector Tests
------------------------
Run with:  python -m pytest tests/ -v
"""

import pytest
from unittest.mock import patch, MagicMock


# ─────────────────────────────────────────────────────────────────────────────
#  RSS Collector Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestRSSCollector:
    def test_collect_returns_list(self):
        """collect_all should always return a list."""
        from ai_news.collectors import rss_collector
        result = rss_collector.collect_all(
            feeds={"Test Feed": "https://techcrunch.com/category/artificial-intelligence/feed/"},
            max_age_hours=48,
        )
        assert isinstance(result, list)

    def test_article_schema(self):
        """Each item must have the required schema keys."""
        from ai_news.collectors import rss_collector
        result = rss_collector.collect_all(
            feeds={"Test Feed": "https://techcrunch.com/category/artificial-intelligence/feed/"},
            max_age_hours=48,
        )
        required_keys = {"source", "title", "url", "summary", "published", "type"}
        for item in result:
            assert required_keys.issubset(item.keys()), f"Missing keys in: {item}"
            assert item["type"] == "article"

    def test_bad_url_returns_empty(self):
        """A broken feed URL should return [] without raising."""
        from ai_news.collectors import rss_collector
        result = rss_collector.collect_all(
            feeds={"Bad Feed": "https://this-url-does-not-exist-xyz.com/rss"},
            max_age_hours=24,
        )
        assert result == []


# ─────────────────────────────────────────────────────────────────────────────
#  Hacker News Collector Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestHackerNewsCollector:
    def test_collect_returns_list(self):
        """collect_all should return a list."""
        from ai_news.collectors import hackernews_collector
        result = hackernews_collector.collect_all(limit=5)
        assert isinstance(result, list)

    def test_story_schema(self):
        """Each HN item must have the required schema keys."""
        from ai_news.collectors import hackernews_collector
        result = hackernews_collector.collect_all(limit=5)
        required_keys = {"source", "title", "url", "summary", "type"}
        for item in result:
            assert required_keys.issubset(item.keys())
            assert item["source"] == "Hacker News"
            assert item["type"] == "article"
            assert item["url"].startswith("http")


# ─────────────────────────────────────────────────────────────────────────────
#  Blog Collector Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestBlogCollector:
    def test_collect_returns_list(self):
        from ai_news.collectors import blog_collector
        result = blog_collector.collect_all(
            feeds={"OpenAI": "https://openai.com/news/rss.xml"},
            max_age_hours=168,  # 1 week — give it a wide window for tests
        )
        assert isinstance(result, list)

    def test_blog_type_tag(self):
        from ai_news.collectors import blog_collector
        result = blog_collector.collect_all(
            feeds={"OpenAI": "https://openai.com/news/rss.xml"},
            max_age_hours=168,
        )
        for item in result:
            assert item["type"] == "blog"
            assert "Blog" in item["source"]


# ─────────────────────────────────────────────────────────────────────────────
#  LinkedIn Collector Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestLinkedInCollector:
    def test_no_feeds_returns_empty(self):
        """With no feeds configured, collector must return [] silently."""
        from ai_news.collectors import linkedin_collector
        result = linkedin_collector.collect_all(feeds={})
        assert result == []

    def test_bad_url_returns_empty(self):
        """A broken feed URL must return [] without raising."""
        from ai_news.collectors import linkedin_collector
        result = linkedin_collector.collect_all(
            feeds={"Test": "https://this-url-does-not-exist-xyz.com/feed"}
        )
        assert result == []


# ─────────────────────────────────────────────────────────────────────────────
#  YouTube Collector Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestYouTubeCollector:
    def test_no_api_key_returns_empty(self, monkeypatch):
        """Without an API key, the collector must return [] gracefully."""
        monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
        from ai_news.collectors import youtube_collector
        result = youtube_collector.collect_all()
        assert result == []
