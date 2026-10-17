"""Run the news pipeline on a daily schedule."""

import logging
import os
from collections.abc import Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apscheduler.schedulers.blocking import BlockingScheduler

logger = logging.getLogger(__name__)


def run_daily(job: Callable[[], object]) -> None:
    """Run ``job`` daily at configured ``DIGEST_TIME`` in ``DIGEST_TIMEZONE``."""
    digest_time = os.getenv("DIGEST_TIME", "07:00").strip()
    timezone_name = os.getenv("DIGEST_TIMEZONE", "UTC").strip()
    try:
        hour_text, minute_text = digest_time.split(":", maxsplit=1)
        hour, minute = int(hour_text), int(minute_text)
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
        tz = ZoneInfo(timezone_name)
    except (ValueError, ZoneInfoNotFoundError) as exc:
        raise ValueError("DIGEST_TIME must be HH:MM and DIGEST_TIMEZONE a valid IANA timezone") from exc

    scheduler = BlockingScheduler(timezone=tz)
    scheduler.add_job(job, "cron", hour=hour, minute=minute, id="daily_digest", max_instances=1)
    logger.info("Daily digest scheduled for %02d:%02d (%s); waiting for next run.", hour, minute, timezone_name)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")
