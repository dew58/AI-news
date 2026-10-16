"""
Gmail SMTP Sender — Phase 4
-----------------------------
[NOT YET IMPLEMENTED]

This module will send the rendered HTML digest via Gmail SMTP
using an App Password (not your regular Gmail password).

Planned interface:
    send_digest(html: str, subject: str) -> None

Setup:
    1. Enable 2-Factor Authentication on your Google account
    2. Go to: Google Account → Security → App passwords
    3. Generate an app password for "Mail"
    4. Set GMAIL_APP_PASSWORD in your .env file
"""
