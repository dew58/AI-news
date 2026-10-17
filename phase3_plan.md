# Phase 3 — HTML Email Digest

## Goal
Turn the validated Phase 2 `digest_payload` into a polished, responsive, email-client-friendly HTML digest. This phase owns rendering only: Phase 4 remains responsible for SMTP delivery and scheduling.

## Current integration contract
`ai_news.analyzer.news_analyzer.run(items)` returns a dictionary with `top_stories`, `blog_spotlight`, `youtube_section`, and `stats`. Phase 3 must consume those keys directly, tolerate absent/empty optional sections, and never trust model/source text as HTML.

## Work plan

### 1. Define and implement the rendering boundary
- Implement `build_email(digest_payload, digest_date=None) -> str` in `src/ai_news/digest/email_builder.py`.
- Use Jinja2 with autoescaping, a package-relative template path, and a deterministic timezone-aware date default.
- Validate that the payload is a mapping and normalize optional collection sections to empty lists; fail clearly for invalid top-level input.
- Keep rendering independent from collection, Gemini, credentials, and SMTP.

### 2. Build the email template
- Replace the placeholder `src/ai_news/digest/templates/digest.html` with a self-contained, responsive HTML email.
- Include a header/date, ranked top stories, official blog highlights, YouTube highlights, and compact run statistics.
- Render each optional section only when it has content; show a useful empty-state when there are no stories.
- Use conservative inline styles and semantic structure suitable for common email clients; no external assets or scripts.
- Escape titles, summaries, source labels, and URLs through Jinja autoescaping; only allow HTTP(S) links.

### 3. Wire Phase 3 into the pipeline
- Replace `pipeline.build_digest` stub with a call to `email_builder.build_email` and update phase labels/docstrings.
- Preserve the existing phase-1 `--test` behavior and the Phase 2 payload contract.
- Do not implement SMTP sending or scheduling in this phase; keep Phase 4 boundaries intact.

### 4. Test in isolation and end-to-end across phases
- Replace `tests/test_email.py` placeholder with tests for all sections, empty/missing optional sections, malformed input, unsafe HTML escaping, unsafe URL handling, and date formatting.
- Add a pipeline integration test that feeds a representative Phase 2 payload through `build_digest` and asserts rendered content.
- Mock external collection/LLM/network behavior; no API keys, network access, or email sending in tests.
- Run the complete project test suite and static diagnostics, fix regressions caused by this phase, and document any pre-existing failures separately.

## Acceptance criteria
- Valid Phase 2 payload renders to non-empty, complete HTML with all available sections and useful links.
- Untrusted text cannot inject markup or unsafe link schemes.
- Missing/empty sections render without exceptions, and invalid top-level input fails with an actionable error.
- The pipeline's normal path passes Phase 2 output to the renderer; collection-only `--test` is unchanged.
- Existing Phase 1/2 tests and new Phase 3 tests pass together without credentials or network dependency.

## Out of scope
- Gmail SMTP implementation, delivery configuration, schedule execution, deployment changes, and custom user ranking prompts (later phases).
