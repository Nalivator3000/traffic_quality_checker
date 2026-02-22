"""
Hourly background job: run full analysis for all webmasters and save reports to DB.

Uses APScheduler (AsyncIOScheduler) running inside the FastAPI process —
no separate Celery worker needed.
"""

import datetime
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app import metrics, scoring
from app.crud import detect_issues, fetch_leads_df, save_report
from app.db import _get_session_factory

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="UTC")

# How many days back to include in the periodic report
_REPORT_WINDOW_DAYS = 30


async def _run_reports() -> None:
    """Core logic: fetch all leads, analyse per webmaster, save reports."""
    logger.info("Scheduled report job started")
    since = datetime.date.today() - datetime.timedelta(days=_REPORT_WINDOW_DAYS)

    async with _get_session_factory()() as session:
        df = await fetch_leads_df(session, since=since)

        if df.empty:
            logger.info("No leads in the last %d days — skipping", _REPORT_WINDOW_DAYS)
            return

        webmasters = df["webmaster"].unique().tolist()
        logger.info("Running reports for %d webmaster(s): %s", len(webmasters), webmasters)

        for wm in webmasters:
            m = metrics.calc_webmaster_metrics(df, wm)

            score_pct: float | None = None
            since_score = datetime.date.today() - datetime.timedelta(days=8)
            df_score = df[(df["webmaster"] == wm) & (df["date"] >= since_score)]
            if not df_score.empty:
                result = scoring.calc_score(df_score, wm)
                score_pct = result.score_pct

            issues = detect_issues(m.approve_pct, m.buyout_pct, m.trash_pct, score_pct)

            await save_report(
                session,
                {
                    "webmaster": wm,
                    "period_days": _REPORT_WINDOW_DAYS,
                    "leads_total": m.total,
                    "approved": m.approved,
                    "bought_out": m.bought_out,
                    "trash": m.trash,
                    "approve_pct": m.approve_pct,
                    "buyout_pct": m.buyout_pct,
                    "trash_pct": m.trash_pct,
                    "score_pct": score_pct,
                    "issues": issues,
                },
            )
            status_str = "OK" if not issues else f"{len(issues)} issue(s): {issues}"
            logger.info("  %s — %s", wm, status_str)

    logger.info("Scheduled report job finished")


def setup_scheduler() -> AsyncIOScheduler:
    """Register jobs and return the scheduler (not yet started)."""
    scheduler.add_job(
        _run_reports,
        trigger="interval",
        hours=1,
        id="hourly_reports",
        replace_existing=True,
        next_run_time=datetime.datetime.now(datetime.timezone.utc),  # run immediately on startup
    )
    return scheduler
