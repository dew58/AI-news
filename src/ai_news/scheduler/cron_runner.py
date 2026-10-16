"""
Cron Runner / Scheduler — Phase 4
-----------------------------------
[NOT YET IMPLEMENTED]

This module will use APScheduler to trigger the full pipeline
at the configured DIGEST_TIME (from .env) every day.

Planned:
    - Read DIGEST_TIME and DIGEST_TIMEZONE from environment
    - Schedule pipeline.main() as a cron job
    - Keep the process alive (for Render Background Worker deployment)
"""
