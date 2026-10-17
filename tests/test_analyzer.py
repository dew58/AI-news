import json
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

import pytest

from ai_news.analyzer import news_analyzer
from ai_news.analyzer.gemini_client import GeminiError, PermanentGeminiError, TransientGeminiError
from ai_news.analyzer.cache import AnalysisCache


def _make_item(title="AI breakthrough", url="https://example.com/ai",
               source="TechCrunch AI", summary="New AI model released",
               published="2026-10-16T10:00:00+00:00", item_type="article"):
    canonical_url = news_analyzer._canonicalize_url(url)
    return {
        "source": source,
        "title": title,
        "url": canonical_url,
        "summary": summary,
        "published": published,
        "type": item_type,
        "_id": news_analyzer._item_id(canonical_url),
        "_published_dt": news_analyzer._parse_published(published),
    }


def _make_raw_item(title="AI breakthrough", url="https://example.com/ai",
                   source="TechCrunch AI", summary="New AI model released",
                   published="2026-10-16T10:00:00+00:00", item_type="article"):
    return {
        "source": source,
        "title": title,
        "url": url,
        "summary": summary,
        "published": published,
        "type": item_type,
    }


class TestNormalizeAndValidate:
    def test_empty_input_returns_empty(self):
        assert news_analyzer._normalize_and_validate([]) == []

    def test_item_missing_title_is_dropped(self):
        item = _make_raw_item()
        del item["title"]
        assert news_analyzer._normalize_and_validate([item]) == []

    def test_item_missing_url_is_dropped(self):
        item = _make_raw_item()
        del item["url"]
        assert news_analyzer._normalize_and_validate([item]) == []

    def test_url_canonicalization_removes_tracking_params(self):
        item = _make_raw_item(url="https://example.com/ai?utm_source=newsletter&id=123")
        result = news_analyzer._normalize_and_validate([item])
        assert result[0]["url"] == "https://example.com/ai?id=123"

    def test_url_canonicalization_removes_fragment(self):
        item = _make_raw_item(url="https://example.com/ai#section")
        result = news_analyzer._normalize_and_validate([item])
        assert result[0]["url"] == "https://example.com/ai"

    def test_url_canonicalization_lowercases_scheme_and_host(self):
        item = _make_raw_item(url="HTTPS://EXAMPLE.COM/ai")
        result = news_analyzer._normalize_and_validate([item])
        assert result[0]["url"] == "https://example.com/ai"

    def test_different_articles_not_merged(self):
        item1 = _make_raw_item(url="https://example.com/ai?page=1")
        item2 = _make_raw_item(url="https://example.com/ai?page=2")
        result = news_analyzer._normalize_and_validate([item1, item2])
        assert len(result) == 2

    def test_published_date_parsed_to_datetime(self):
        item = _make_raw_item(published="2026-10-16T10:00:00+00:00")
        result = news_analyzer._normalize_and_validate([item])
        assert result[0]["_published_dt"] == datetime(2026, 10, 16, 10, 0, tzinfo=timezone.utc)

    def test_missing_published_date_is_none(self):
        item = _make_raw_item(published=None)
        result = news_analyzer._normalize_and_validate([item])
        assert result[0]["_published_dt"] is None

    def test_invalid_published_date_is_none(self):
        item = _make_raw_item(published="not-a-date")
        result = news_analyzer._normalize_and_validate([item])
        assert result[0]["_published_dt"] is None

    def test_whitespace_stripped_from_fields(self):
        item = _make_raw_item(title="  AI News  ", source="  TechCrunch  ")
        result = news_analyzer._normalize_and_validate([item])
        assert result[0]["title"] == "AI News"
        assert result[0]["source"] == "TechCrunch"


class TestExactDeduplicate:
    def test_same_url_deduplicated(self):
        item1 = _make_item(url="https://example.com/ai")
        item2 = _make_item(url="https://example.com/ai")
        result = news_analyzer._exact_deduplicate([item1, item2])
        assert len(result) == 1

    def test_same_title_and_summary_deduplicated(self):
        item1 = _make_item(url="https://a.com/1", title="AI News", summary="Summary text")
        item2 = _make_item(url="https://b.com/2", title="AI News", summary="Summary text")
        result = news_analyzer._exact_deduplicate([item1, item2])
        assert len(result) == 1

    def test_different_titles_not_deduplicated(self):
        item1 = _make_item(url="https://a.com/1", title="AI News One")
        item2 = _make_item(url="https://b.com/2", title="AI News Two")
        result = news_analyzer._exact_deduplicate([item1, item2])
        assert len(result) == 2

    def test_empty_input(self):
        assert news_analyzer._exact_deduplicate([]) == []


class TestKeywordFilter:
    def test_empty_input(self):
        assert news_analyzer._keyword_filter([]) == []

    def test_ai_keyword_match_keeps_item(self):
        item = _make_item(title="New AI model released")
        result = news_analyzer._keyword_filter([item])
        assert len(result) == 1

    def test_no_topic_match_but_no_exclusion_keeps_item(self):
        item = _make_item(title="Something completely unrelated")
        result = news_analyzer._keyword_filter([item])
        assert len(result) == 1

    def test_strong_exclusion_drops_item(self):
        item = _make_item(
            title="NFL football basketball soccer baseball",
            summary="NFL football basketball soccer baseball game sports"
        )
        result = news_analyzer._keyword_filter([item])
        assert len(result) == 0

    def test_configurable_topic_keywords(self):
        item = _make_item(title="Quantum computing breakthrough")
        config = {"topic_keywords": {"quantum": ["quantum computing"]}}
        result = news_analyzer._keyword_filter([item], config)
        assert len(result) == 1


class TestScoreCandidates:
    def test_items_receive_score(self):
        items = [_make_item()]
        result = news_analyzer._score_candidates(items)
        assert "_score" in result[0]
        assert 0 <= result[0]["_score"] <= 10

    def test_official_blog_scores_higher_than_unknown(self):
        blog_item = _make_item(source="OpenAI Blog")
        unknown_item = _make_item(url="https://x.com/2", source="Unknown Blog")
        result = news_analyzer._score_candidates([blog_item, unknown_item])
        blog_score = next(i["_score"] for i in result if i["source"] == "OpenAI Blog")
        unknown_score = next(i["_score"] for i in result if i["source"] == "Unknown Blog")
        assert blog_score > unknown_score

    def test_recent_items_score_higher_than_old(self):
        recent = _make_item(published=datetime.now(timezone.utc).isoformat())
        old = _make_item(url="https://old.com/2", published="2020-01-01T00:00:00+00:00")
        result = news_analyzer._score_candidates([recent, old])
        assert result[0]["_score"] > result[1]["_score"]


class TestNearDuplicateGrouping:
    def test_similar_titles_grouped(self):
        item1 = _make_item(url="https://a.com/1", title="OpenAI announces GPT-5")
        item2 = _make_item(url="https://b.com/2", title="OpenAI announces GPT-5!")
        result = news_analyzer._group_near_duplicates([item1, item2])
        assert len(result) == 1
        assert len(result[0]["related"]) == 1

    def test_different_titles_not_grouped(self):
        item1 = _make_item(url="https://a.com/1", title="AI model released")
        item2 = _make_item(url="https://b.com/2", title="New startup raises funding")
        result = news_analyzer._group_near_duplicates([item1, item2])
        assert len(result) == 2

    def test_threshold_configurable(self):
        item1 = _make_item(url="https://a.com/1", title="OpenAI announces GPT-5")
        item2 = _make_item(url="https://b.com/2", title="OpenAI announces GPT-5 with new features")
        result = news_analyzer._group_near_duplicates([item1, item2], threshold=0.95)
        assert len(result) == 2

    def test_empty_input(self):
        assert news_analyzer._group_near_duplicates([]) == []

    def test_group_has_group_id(self):
        items = [_make_item()]
        result = news_analyzer._group_near_duplicates(items)
        assert "group_id" in result[0]
        assert len(result[0]["group_id"]) == 12


class TestSelectCandidates:
    def test_limit_respected(self):
        groups = [{"group_id": f"g{i}", "score": i, "type": "article", "primary": _make_item(), "related": []}
                  for i in range(10)]
        result = news_analyzer._select_candidates(groups, limit=5)
        assert len(result) == 5

    def test_empty_input(self):
        assert news_analyzer._select_candidates([]) == []


class TestParseJsonResponse:
    def test_valid_json(self):
        result = news_analyzer._parse_json_response('{"key": "value"}')
        assert result == {"key": "value"}

    def test_markdown_fenced_json(self):
        text = '```json\n{"top_stories": []}\n```'
        result = news_analyzer._parse_json_response(text)
        assert result == {"top_stories": []}

    def test_invalid_json_returns_none(self):
        assert news_analyzer._parse_json_response("not json at all") is None

    def test_non_dict_json_returns_none(self):
        assert news_analyzer._parse_json_response("[1, 2, 3]") is None


class TestValidateAnalysis:
    def test_unknown_group_ids_filtered(self):
        candidates = [{"group_id": "abc", "primary": _make_item(), "related": []}]
        analysis = {"top_stories": [
            {"group_id": "abc", "rank": 1, "score": 8, "category": "Research", "summary": "Good"},
            {"group_id": "unknown", "rank": 2, "score": 9, "category": "Opinion", "summary": "Bad"},
        ]}
        result = news_analyzer._validate_analysis(analysis, candidates)
        assert len(result["top_stories"]) == 1
        assert result["top_stories"][0]["group_id"] == "abc"

    def test_scores_clamped(self):
        candidates = [{"group_id": "abc", "primary": _make_item(), "related": []}]
        analysis = {"top_stories": [
            {"group_id": "abc", "rank": 1, "score": 15, "category": "Research", "summary": "Test"},
        ]}
        result = news_analyzer._validate_analysis(analysis, candidates)
        assert result["top_stories"][0]["score"] == 10

    def test_invalid_category_defaults(self):
        candidates = [{"group_id": "abc", "primary": _make_item(), "related": []}]
        analysis = {"top_stories": [
            {"group_id": "abc", "rank": 1, "score": 5, "category": "Invalid", "summary": "Test"},
        ]}
        result = news_analyzer._validate_analysis(analysis, candidates)
        assert result["top_stories"][0]["category"] == "Industry News"

    def test_ranks_reordered(self):
        candidates = [{"group_id": "abc", "primary": _make_item(), "related": []}]
        analysis = {"top_stories": [
            {"group_id": "abc", "rank": 5, "score": 5, "category": "Research", "summary": "Test"},
        ]}
        result = news_analyzer._validate_analysis(analysis, candidates)
        assert result["top_stories"][0]["rank"] == 1

    def test_empty_analysis(self):
        assert news_analyzer._validate_analysis({"top_stories": []}, []) == {"top_stories": []}


class TestBreakingNews:
    def test_recent_item_is_breaking(self):
        now = datetime.now(timezone.utc)
        recent = now - timedelta(hours=2)
        assert news_analyzer._is_breaking(recent, breaking_hours=6, now=now) is True

    def test_old_item_not_breaking(self):
        now = datetime.now(timezone.utc)
        old = now - timedelta(hours=12)
        assert news_analyzer._is_breaking(old, breaking_hours=6, now=now) is False

    def test_missing_timestamp_not_breaking(self):
        now = datetime.now(timezone.utc)
        assert news_analyzer._is_breaking(None, breaking_hours=6, now=now) is False

    def test_exactly_at_threshold(self):
        now = datetime.now(timezone.utc)
        at_threshold = now - timedelta(hours=6)
        assert news_analyzer._is_breaking(at_threshold, breaking_hours=6, now=now) is False


class TestRuleBasedFallback:
    def test_fallback_returns_top_n(self):
        groups = [{"group_id": f"g{i}", "score": 10 - i, "type": "article",
                   "primary": _make_item(), "related": []} for i in range(10)]
        result = news_analyzer._rule_based_fallback(groups, top_n=3)
        assert len(result["top_stories"]) == 3

    def test_fallback_ranks_sequential(self):
        groups = [{"group_id": f"g{i}", "score": 10 - i, "type": "article",
                   "primary": _make_item(), "related": []} for i in range(5)]
        result = news_analyzer._rule_based_fallback(groups, top_n=3)
        ranks = [s["rank"] for s in result["top_stories"]]
        assert ranks == [1, 2, 3]

    def test_fallback_includes_primary_data(self):
        primary = _make_item(title="Test Story")
        groups = [{"group_id": "g1", "score": 8, "type": "article",
                   "primary": primary, "related": []}]
        result = news_analyzer._rule_based_fallback(groups, top_n=1)
        assert result["top_stories"][0]["_primary"]["title"] == "Test Story"


class TestCache:
    def test_cache_miss_returns_none(self, tmp_path):
        cache = AnalysisCache(db_path=str(tmp_path / "test.db"))
        result = cache.get("fingerprint", "v1", "model", "profile")
        assert result is None

    def test_cache_hit_returns_stored_value(self, tmp_path):
        cache = AnalysisCache(db_path=str(tmp_path / "test.db"))
        cache.set("fp", "v1", "model", "prof", {"result": "data"})
        result = cache.get("fp", "v1", "model", "prof")
        assert result == {"result": "data"}

    def test_cache_invalidation_on_model_change(self, tmp_path):
        cache = AnalysisCache(db_path=str(tmp_path / "test.db"))
        cache.set("fp", "v1", "model_a", "prof", {"result": "data"})
        result = cache.get("fp", "v1", "model_b", "prof")
        assert result is None

    def test_cache_clear(self, tmp_path):
        cache = AnalysisCache(db_path=str(tmp_path / "test.db"))
        cache.set("fp", "v1", "model", "prof", {"result": "data"})
        cache.clear()
        result = cache.get("fp", "v1", "model", "prof")
        assert result is None


class TestGeminiClientRetries:
    def test_transient_error_retries_then_succeeds(self):
        client = news_analyzer.GeminiClient(api_key="test_key", max_retries=3)
        client._genai = MagicMock()
        mock_model = MagicMock()
        client._model = mock_model

        mock_response = MagicMock()
        mock_response.text = '{"result": "ok"}'
        mock_response.usage_metadata = None

        mock_model.generate_content.side_effect = [
            Exception("429 Too Many Requests"),
            mock_response,
        ]

        with patch("time.sleep"):
            result = client.generate("test prompt")
        assert result == '{"result": "ok"}'
        assert mock_model.generate_content.call_count == 2

    def test_permanent_error_no_retry(self):
        client = news_analyzer.GeminiClient(api_key="test_key", max_retries=3)
        client._genai = MagicMock()
        mock_model = MagicMock()
        client._model = mock_model

        permanent_exc = Exception("401 Unauthorized")
        permanent_exc.status_code = 401
        mock_model.generate_content.side_effect = permanent_exc

        with pytest.raises(PermanentGeminiError):
            client.generate("test prompt")
        assert mock_model.generate_content.call_count == 1

    def test_transient_error_exhausts_retries(self):
        client = news_analyzer.GeminiClient(api_key="test_key", max_retries=2)
        client._genai = MagicMock()
        mock_model = MagicMock()
        client._model = mock_model

        transient_exc = Exception("503 Service Unavailable")
        transient_exc.status_code = 503
        mock_model.generate_content.side_effect = transient_exc

        with patch("time.sleep"):
            with pytest.raises(TransientGeminiError):
                client.generate("test prompt")
        assert mock_model.generate_content.call_count == 2


class TestFullPipeline:
    @patch("ai_news.analyzer.news_analyzer.GeminiClient")
    def test_full_run_with_mocked_gemini(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.model_name = "test-model"
        mock_client.last_input_tokens = 100
        mock_client.last_output_tokens = 50

        def mock_generate(prompt, system_instruction=None):
            if "Rank the following" in prompt:
                return '{"top_stories": [{"group_id": "g0", "rank": 1, "category": "Research", "score": 9, "summary": "AI story", "reason": "Big deal"}]}'
            return '{"summaries": []}'

        mock_client.generate.side_effect = mock_generate
        mock_client_class.return_value = mock_client

        with patch("ai_news.analyzer.news_analyzer.AnalysisCache") as mock_cache_class:
            mock_cache = MagicMock()
            mock_cache.get.return_value = None
            mock_cache_class.return_value = mock_cache

            items = [
                _make_raw_item(title="AI model breakthrough", url="https://a.com/1"),
                _make_raw_item(title="New GPT release", url="https://a.com/2"),
            ]

            env = {
                "NEWS_ANALYZER_CANDIDATE_LIMIT": "60",
                "NEWS_ANALYZER_TOP_STORIES": "5",
                "NEWS_ANALYZER_BREAKING_HOURS": "6",
                "NEWS_ANALYZER_RETRY_LIMIT": "3",
            }
            with patch.dict("os.environ", env):
                result = news_analyzer.run(items)

        assert "top_stories" in result
        assert "blog_spotlight" in result
        assert "youtube_section" in result
        assert "stats" in result
        assert result["stats"]["total_collected"] == 2
        assert result["stats"]["after_validation"] == 2
        assert result["stats"]["gemini_model"] == "test-model"

    @patch("ai_news.analyzer.news_analyzer.GeminiClient")
    def test_fallback_when_gemini_fails(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.generate.side_effect = GeminiError("API key not set")
        mock_client_class.return_value = mock_client

        with patch("ai_news.analyzer.news_analyzer.AnalysisCache"):
            items = [_make_raw_item(title="AI news", url="https://a.com/1")]
            env = {"NEWS_ANALYZER_RETRY_LIMIT": "1"}
            with patch.dict("os.environ", env):
                result = news_analyzer.run(items)

        assert "top_stories" in result
        assert len(result["top_stories"]) > 0
        assert any("Gemini" in w for w in result["stats"]["warnings"])

    @patch("ai_news.analyzer.news_analyzer.GeminiClient")
    def test_cache_hit_skips_gemini_call(self, mock_client_class):
        import hashlib

        mock_client = MagicMock()
        mock_client.model_name = "test-model"
        mock_client_class.return_value = mock_client

        raw_item = _make_raw_item(title="AI news", url="https://a.com/1")
        normalized = news_analyzer._normalize_and_validate([raw_item])[0]
        expected_group_id = hashlib.sha256(normalized["_id"].encode()).hexdigest()[:12]

        with patch("ai_news.analyzer.news_analyzer.AnalysisCache") as mock_cache_class:
            mock_cache = MagicMock()
            mock_cache.get.return_value = {"top_stories": [
                {"group_id": expected_group_id, "rank": 1, "category": "Research", "score": 8,
                 "summary": "Cached story", "reason": "Important"}
            ]}
            mock_cache_class.return_value = mock_cache

            env = {"NEWS_ANALYZER_RETRY_LIMIT": "1"}
            with patch.dict("os.environ", env):
                result = news_analyzer.run([raw_item])

        mock_client.generate.assert_not_called()
        assert result["top_stories"][0]["summary"] == "Cached story"

    @patch("ai_news.analyzer.news_analyzer.GeminiClient")
    def test_youtube_items_go_to_youtube_section(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.model_name = "test-model"
        mock_client.last_input_tokens = 10
        mock_client.last_output_tokens = 5

        def mock_generate(prompt, system_instruction=None):
            if "YouTube videos" in prompt:
                return '{"summaries": []}'
            if "blog posts" in prompt:
                return '{"summaries": []}'
            return '{"top_stories": []}'

        mock_client.generate.side_effect = mock_generate
        mock_client_class.return_value = mock_client

        with patch("ai_news.analyzer.news_analyzer.AnalysisCache"):
            items = [_make_raw_item(
                title="AI Video",
                url="https://youtube.com/watch?v=123",
                source="YouTube — Two Minute Papers",
                item_type="youtube",
            )]
            env = {"NEWS_ANALYZER_RETRY_LIMIT": "1"}
            with patch.dict("os.environ", env):
                result = news_analyzer.run(items)

        assert len(result["youtube_section"]) == 1
        assert result["youtube_section"][0]["title"] == "AI Video"

    @patch("ai_news.analyzer.news_analyzer.GeminiClient")
    def test_blog_items_go_to_blog_spotlight(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.model_name = "test-model"
        mock_client.last_input_tokens = 10
        mock_client.last_output_tokens = 5

        def mock_generate(prompt, system_instruction=None):
            if "blog posts" in prompt:
                return '{"summaries": [{"id": "test", "summary": "Blog summary"}]}'
            if "YouTube videos" in prompt:
                return '{"summaries": []}'
            return '{"top_stories": []}'

        mock_client.generate.side_effect = mock_generate
        mock_client_class.return_value = mock_client

        with patch("ai_news.analyzer.news_analyzer.AnalysisCache"):
            items = [_make_raw_item(
                title="OpenAI Announces New Model",
                url="https://openai.com/news/new-model",
                source="OpenAI Blog",
                item_type="blog",
            )]
            env = {"NEWS_ANALYZER_RETRY_LIMIT": "1"}
            with patch.dict("os.environ", env):
                result = news_analyzer.run(items)

        assert len(result["blog_spotlight"]) == 1
        assert result["blog_spotlight"][0]["title"] == "OpenAI Announces New Model"

    @patch("ai_news.analyzer.news_analyzer.GeminiClient")
    def test_cache_hits_incremented_in_stats(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.model_name = "test-model"
        mock_client_class.return_value = mock_client

        raw_item = _make_raw_item(title="AI news", url="https://a.com/1")
        normalized = news_analyzer._normalize_and_validate([raw_item])[0]
        expected_group_id = news_analyzer.hashlib.sha256(normalized["_id"].encode()).hexdigest()[:12]

        with patch("ai_news.analyzer.news_analyzer.AnalysisCache") as mock_cache_class:
            mock_cache = MagicMock()
            mock_cache.get.return_value = {"top_stories": [
                {"group_id": expected_group_id, "rank": 1, "category": "Research", "score": 8,
                 "summary": "Cached story", "reason": "Important"}
            ]}
            mock_cache_class.return_value = mock_cache

            env = {"NEWS_ANALYZER_RETRY_LIMIT": "1"}
            with patch.dict("os.environ", env):
                result = news_analyzer.run([raw_item])

        assert result["stats"]["cache_hits"] >= 1


class TestPhase2DesignCompliance:
    def test_public_interface_aliases(self):
        expected_exports = [
            "run",
            "normalize_and_validate",
            "exact_deduplicate",
            "keyword_filter",
            "score_candidates",
            "group_near_duplicates",
            "select_candidates",
            "analyze_with_gemini",
            "validate_analysis",
            "build_digest_payload",
        ]
        for name in expected_exports:
            assert hasattr(news_analyzer, name), f"Missing public function: {name}"
            assert name in news_analyzer.__all__, f"Missing from __all__: {name}"

    def test_gemini_client_system_instruction_applied(self):
        client = news_analyzer.GeminiClient(api_key="test_key")
        mock_genai = MagicMock()
        mock_model_class = MagicMock()
        mock_genai.GenerativeModel = mock_model_class
        client._genai = mock_genai
        client._model = MagicMock()

        mock_active_model = MagicMock()
        mock_active_model.generate_content.return_value = MagicMock(text='{"ok": true}', usage_metadata=None)
        mock_model_class.return_value = mock_active_model

        client.generate("hello", system_instruction="You are an AI analyst.")
        mock_model_class.assert_called_with(
            client.model_name,
            system_instruction="You are an AI analyst.",
        )

    def test_gemini_client_retry_delay_from_rate_limit(self):
        client = news_analyzer.GeminiClient(api_key="test_key", max_retries=2)
        client._genai = MagicMock()
        mock_model = MagicMock()
        client._model = mock_model

        exc = Exception("429 Quota exceeded. Please retry in 15s.")
        exc.status_code = 429
        mock_response = MagicMock(text='{"status": "ok"}', usage_metadata=None)
        mock_model.generate_content.side_effect = [exc, mock_response]

        sleep_times = []
        with patch("time.sleep", side_effect=lambda s: sleep_times.append(s)):
            res = client.generate("test prompt")

        assert res == '{"status": "ok"}'
        assert len(sleep_times) == 1
        assert sleep_times[0] >= 15.0

