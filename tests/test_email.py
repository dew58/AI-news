from datetime import date
from unittest.mock import MagicMock

import pytest

from ai_news.digest.email_builder import build_email
from ai_news.pipeline import build_digest
from ai_news.delivery import gmail_sender
from ai_news import pipeline
from ai_news.scheduler import cron_runner


@pytest.fixture
def payload():
	return {
		"top_stories": [{
			"rank": 1, "title": "New AI model", "url": "https://example.com/story?a=1&b=2",
			"source": "Example News", "category": "Research", "summary": "Useful summary",
			"score": 9, "breaking": True, "related_sources": [
				{"title": "Mirror", "url": "https://other.example/story", "source": "Other"}
			],
		}],
		"blog_spotlight": [{"title": "Company update", "url": "https://example.com/blog", "source": "OpenAI Blog", "summary": "Blog summary"}],
		"youtube_section": [{"title": "Video update", "url": "https://youtube.com/watch?v=abc", "channel": "AI Channel", "summary": "Video summary"}],
		"stats": {"total_collected": 42, "gemini_model": "test-model", "duration_ms": 1200, "warnings": []},
	}


def test_renders_all_phase_two_sections(payload):
	html = build_email(payload, date(2026, 10, 18))
	for expected in ("October 18, 2026", "New AI model", "Useful summary", "BREAKING",
					 "Official blog highlights", "Company update", "YouTube highlights",
					 "Video update", "42 items collected", "test-model"):
		assert expected in html


def test_optional_sections_can_be_absent_or_empty():
	html = build_email({})
	assert "No top stories were available" in html
	assert "Official blog highlights" not in html
	assert "YouTube highlights" not in html


def test_untrusted_text_is_html_escaped_and_unsafe_url_not_linked():
	html = build_email({"top_stories": [{
		"rank": 1, "title": '<img src=x onerror="alert(1)">', "url": "javascript:alert(1)",
		"source": "<b>Injected</b>", "summary": "<script>bad()</script>",
		"related_sources": [],
	}]})
	assert "&lt;img" in html
	assert "&lt;script&gt;bad()&lt;/script&gt;" in html
	assert '<a href="javascript:' not in html
	assert 'onerror="alert(1)"' not in html


def test_pipeline_build_digest_integrates_phase_two_payload(payload):
	html = build_digest(payload)
	assert "New AI model" in html
	assert "Video update" in html


def test_invalid_top_level_payload_is_rejected():
	with pytest.raises(TypeError, match="digest_payload"):
		build_email([])


def test_invalid_date_is_rejected():
	with pytest.raises(ValueError, match="digest_date"):
		build_email({}, "not-a-date")


def test_smtp_delivery_sends_html_using_ssl(monkeypatch):
	monkeypatch.setenv("GMAIL_ADDRESS", "sender@example.com")
	monkeypatch.setenv("GMAIL_APP_PASSWORD", "app password")
	monkeypatch.setenv("RECIPIENT_EMAIL", "reader@example.com")
	smtp = MagicMock()
	context = MagicMock()
	context.__enter__.return_value = smtp
	monkeypatch.setattr(gmail_sender.smtplib, "SMTP_SSL", lambda *args, **kwargs: context)

	gmail_sender.send_digest("<h1>News</h1>", subject="Test digest")

	context.__enter__.assert_called_once()
	smtp.login.assert_called_once_with("sender@example.com", "apppassword")
	message = smtp.send_message.call_args.args[0]
	assert message["Subject"] == "Test digest"
	assert message["To"] == "reader@example.com"
	assert message.get_body(preferencelist=("html",)).get_content().strip() == "<h1>News</h1>"


def test_smtp_delivery_requires_all_credentials(monkeypatch):
	for name in ("GMAIL_ADDRESS", "GMAIL_APP_PASSWORD", "RECIPIENT_EMAIL"):
		monkeypatch.delenv(name, raising=False)
	with pytest.raises(gmail_sender.EmailDeliveryError, match="GMAIL_ADDRESS"):
		gmail_sender.send_digest("<p>Hi</p>")


def test_smtp_delivery_rejects_invalid_address(monkeypatch):
	monkeypatch.setenv("GMAIL_ADDRESS", "not-an-email")
	monkeypatch.setenv("GMAIL_APP_PASSWORD", "secret")
	monkeypatch.setenv("RECIPIENT_EMAIL", "reader@example.com")
	with pytest.raises(gmail_sender.EmailDeliveryError, match="GMAIL_ADDRESS"):
		gmail_sender.send_digest("<p>Hi</p>")


def test_preview_orchestration_saves_without_sending(monkeypatch, tmp_path):
	monkeypatch.setattr(pipeline, "_load_sources", lambda: {})
	monkeypatch.setattr(pipeline, "collect", lambda sources: [{"title": "story"}])
	monkeypatch.setattr(pipeline, "analyze", lambda items: {"top_stories": []})
	monkeypatch.setattr(pipeline, "build_digest", lambda payload: "<html>preview</html>")
	monkeypatch.setattr(pipeline, "send", lambda html: pytest.fail("preview must not send"))
	output = tmp_path / "preview.html"

	assert pipeline.run_pipeline(send_email=False, preview_path=str(output)) == "<html>preview</html>"
	assert output.read_text(encoding="utf-8") == "<html>preview</html>"


def test_full_orchestration_sends_rendered_digest(monkeypatch):
	monkeypatch.setattr(pipeline, "_load_sources", lambda: {})
	monkeypatch.setattr(pipeline, "collect", lambda sources: [])
	monkeypatch.setattr(pipeline, "analyze", lambda items: {"top_stories": []})
	monkeypatch.setattr(pipeline, "build_digest", lambda payload: "<html>ready</html>")
	sent = []
	monkeypatch.setattr(pipeline, "send", sent.append)

	pipeline.run_pipeline()
	assert sent == ["<html>ready</html>"]


def test_scheduler_uses_configured_time_and_timezone(monkeypatch):
	monkeypatch.setenv("DIGEST_TIME", "08:35")
	monkeypatch.setenv("DIGEST_TIMEZONE", "Asia/Jerusalem")
	scheduler = MagicMock()
	monkeypatch.setattr(cron_runner, "BlockingScheduler", lambda timezone: scheduler)
	job = lambda: None

	cron_runner.run_daily(job)

	scheduler.add_job.assert_called_once_with(job, "cron", hour=8, minute=35, id="daily_digest", max_instances=1)
	scheduler.start.assert_called_once()


def test_scheduler_rejects_invalid_time(monkeypatch):
	monkeypatch.setenv("DIGEST_TIME", "29:70")
	monkeypatch.setenv("DIGEST_TIMEZONE", "UTC")
	with pytest.raises(ValueError, match="DIGEST_TIME"):
		cron_runner.run_daily(lambda: None)
