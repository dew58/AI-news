"""Render the validated Phase 2 digest payload as an HTML email."""

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATE_DIR = Path(__file__).parent / "templates"


def _safe_url(value: Any) -> str | None:
    """Return only absolute HTTP(S) links, preventing unsafe template hrefs."""
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    parsed = urlsplit(candidate)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return None
    return candidate


def _display_date(value: date | datetime | str | None) -> str:
    if value is None:
        value = datetime.now(timezone.utc)
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("digest_date must be a date, datetime, or ISO-8601 string") from exc
    if not isinstance(value, (date, datetime)):
        raise TypeError("digest_date must be a date, datetime, or ISO-8601 string")
    return f"{value.strftime('%B')} {value.day}, {value.year}"


def build_email(
    digest_payload: dict[str, Any],
    digest_date: date | datetime | str | None = None,
) -> str:
    """Build a complete HTML email from the analyzer's digest payload.

    Optional sections and statistics may be absent. Story text is autoescaped,
    and links are restricted to absolute HTTP(S) URLs.
    """
    if not isinstance(digest_payload, dict):
        raise TypeError("digest_payload must be a dictionary returned by the analyzer")

    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(enabled_extensions=("html", "xml"), default=True),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["safe_url"] = _safe_url
    template = env.get_template("digest.html")
    return template.render(
        digest_date=_display_date(digest_date),
        top_stories=digest_payload.get("top_stories") or [],
        blog_spotlight=digest_payload.get("blog_spotlight") or [],
        youtube_section=digest_payload.get("youtube_section") or [],
        stats=digest_payload.get("stats") or {},
    )


__all__ = ["build_email"]
