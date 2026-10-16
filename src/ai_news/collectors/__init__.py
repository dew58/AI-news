"""
AI News Collectors Package
--------------------------
Each module in this package is responsible for fetching raw news items
from a specific type of source. All collectors return a uniform list of
article dicts with these guaranteed keys:

    {
        "source":    str,   # Human-readable source name
        "title":     str,   # Article / video title
        "url":       str,   # Canonical link
        "summary":   str,   # Short text description or excerpt
        "published": str | None,  # ISO-8601 datetime string or None
        "type":      str,   # "article" | "youtube" | "blog" | "linkedin"
    }

Additional source-specific keys may be present (e.g. "score" for HN,
"transcript_snippet" for YouTube) but are not guaranteed.
"""
