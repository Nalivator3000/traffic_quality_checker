"""
Hourly background job: run full analysis for all webmasters and save reports to DB.

Uses APScheduler (AsyncIOScheduler) running inside the FastAPI process —
no separate Celery worker needed.
"""

import datetime
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.analysis import run_and_save
from app.crud import fetch_leads_df
from app.db import _get_session_factory

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="UTC")

_REPORT_WINDOW_DAYS = 30


async def _run_reports() -> None:
    """Fetch all leads for the last N days, analyse per webmaster, save reports."""
    logger.info("Scheduled report job started")
    since = datetime.date.today() - datetime.timedelta(days=_REPORT_WINDOW_DAYS)

    async with _get_session_factory()() as session:
        df = await fetch_leads_df(session, since=since)

        if df.empty:
            logger.info("No leads in the last %d days — skipping", _REPORT_WINDOW_DAYS)
            return

        results = await run_and_save(df, session, period_days=_REPORT_WINDOW_DAYS)

        for r in results:
            status_str = "OK" if r["ok"] else f"{len(r['issues'])} issue(s): {r['issues']}"
            logger.info("  %s — %s | adj_buyout=%.1f%%", r["webmaster"], status_str, r["adj_buyout_pct"])

    logger.info("Scheduled report job finished")


def setup_scheduler() -> AsyncIOScheduler:
    """Register jobs and return the scheduler (not yet started)."""
    scheduler.add_job(
        _run_reports,
        trigger="interval",
        hours=1,
        id="hourly_reports",
        replace_existing=True,
        next_run_time=datetime.datetime.now(datetime.timezone.utc),
    )
    return scheduler
