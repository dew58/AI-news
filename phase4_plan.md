# Phase 4 — Email Delivery, Scheduling, and End-to-End Run

## Goal
Complete the project so a configured local run collects technology news, analyzes it, renders the Phase 3 email, and sends it to the configured recipient. Add an explicit preview mode so the HTML can be inspected without sending, and provide an optional daily scheduler.

## Existing contracts and boundaries
- Phase 1 returns normalized raw story dictionaries.
- Phase 2 returns `top_stories`, `blog_spotlight`, `youtube_section`, and `stats`.
- Phase 3 renders that payload into HTML.
- Phase 4 handles SMTP only; it must not alter analyzer ranking or digest rendering contracts.
- Credentials are supplied through environment variables / `.env`, never committed or logged.

## Work plan

### 1. Implement Gmail SMTP delivery
- Implement `send_digest(html, subject=None)` using `EmailMessage` and Gmail SMTP over TLS (`SMTP_SSL`).
- Require and validate `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, and `RECIPIENT_EMAIL`; fail early with actionable configuration errors.
- Set HTML content type, UTF-8 headers, a date-based default subject, and clear transport errors without leaking credentials.
- Permit tests to inject/mock SMTP; never contact real SMTP in automated tests.

### 2. Complete the application entry points
- Add an orchestration function that runs collection → analysis → rendering → optional delivery.
- Keep `--test` as collection-only JSON output for backwards compatibility.
- Add `--preview [path]` to run all non-delivery phases and save an inspectable HTML file without SMTP credentials.
- Default invocation performs a real send, and reports missing setup instead of silently succeeding.
- Add `--schedule` as an opt-in long-running daily schedule using `DIGEST_TIME` and `DIGEST_TIMEZONE`; validate time and IANA timezone and log run failures.
- Ensure a scheduled run does not accidentally send at process startup unless explicitly intended; schedule the next configured daily occurrence.

### 3. Tests and safety checks
- Test SMTP message headers, HTML body, required configuration, invalid email settings, and send failures with mocks.
- Test CLI/orchestration behavior: preview does not send, normal run does, collection-only mode stays unchanged, and scheduler configuration is validated.
- Exercise the complete Phase 1→2→3→4 handoff with deterministic mocked collectors/analyzer/SMTP; no API keys, network access, or real email.
- Run all tests and diagnostics; fix any regressions across existing phases.

### 4. Documentation as the final implementation step
- Replace the empty `README.md` with an accurate setup guide, environment/key setup, source configuration, commands, workflow/data contract, test instructions, preview instructions, email sending, scheduler/deployment notes, troubleshooting, and security notes.
- Document that the first actual run requires internet access and valid Gemini/Gmail credentials; do not claim tests send email or that a digest can be received without setup.

## Acceptance criteria
- With valid `.env` credentials and network/API availability, `uv run ai-news` collects, analyzes, renders, and sends an HTML email.
- `uv run ai-news --preview` produces a local HTML file and never attempts SMTP.
- `uv run ai-news --test` remains collection-only.
- `uv run ai-news --schedule` schedules daily execution at configured local time and timezone.
- Full tests pass without network calls, API credentials, or actual email delivery.
- README matches actual behavior and lets a developer run a preview and configure a real send.

## Out of scope
- Guaranteeing third-party feeds/APIs, Gemini quota, or Gmail account availability; deployment credentials and production monitoring; changing Phase 2 editorial logic.
