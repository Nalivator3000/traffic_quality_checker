"""
Full webmaster analysis: combines metrics, adjusted buyout, 8-day score,
and issue detection. Used by both the API (reports.py) and the cron scheduler.
"""

from __future__ import annotations

import datetime

import pandas as pd

from app import metrics, scoring
from app.crud import detect_issues, save_report
from app.scoring import calc_adjusted_buyout
from sqlalchemy.ext.asyncio import AsyncSession


def _compute_averages(df: pd.DataFrame, webmasters: list[str]) -> tuple[float, float]:
    """Return (avg_approve_pct, avg_trash_pct) across all webmasters."""
    approves, trashes = [], []
    for wm in webmasters:
        m = metrics.calc_webmaster_metrics(df, wm)
        approves.append(m.approve_pct)
        trashes.append(m.trash_pct)
    avg_approve = sum(approves) / len(approves) if approves else 0.0
    avg_trash = sum(trashes) / len(trashes) if trashes else 0.0
    return round(avg_approve, 2), round(avg_trash, 2)


def analyse_all(
    df: pd.DataFrame,
    period_days: int = 30,
    analysis_date: datetime.date | None = None,
) -> list[dict]:
    """
    Run full analysis for every webmaster in df.

    Returns a list of dicts (one per webmaster) with all metrics and issues.
    """
    if df.empty:
        return []

    today = analysis_date or datetime.date.today()
    webmasters = df["webmaster"].unique().tolist()

    avg_approve, avg_trash = _compute_averages(df, webmasters)

    results = []
    for wm in webmasters:
        m = metrics.calc_webmaster_metrics(df, wm)

        adj_buyout_pct = calc_adjusted_buyout(df, wm, today, period_days)

        # 8-day score
        score_pct: float | None = None
        since_score = today - datetime.timedelta(days=8)
        df_score = df[(df["webmaster"] == wm) & (df["date"] >= since_score)]
        if not df_score.empty:
            sr = scoring.calc_score(df_score, wm, analysis_date=today)
            score_pct = sr.score_pct

        issues = detect_issues(
            approve_pct=m.approve_pct,
            adj_buyout_pct=adj_buyout_pct,
            trash_pct=m.trash_pct,
            score_pct=score_pct,
            avg_approve_pct=avg_approve,
            avg_trash_pct=avg_trash,
        )

        results.append(
            {
                "webmaster": wm,
                "period_days": period_days,
                "leads_total": m.total,
                "approved": m.approved,
                "bought_out": m.bought_out,
                "trash": m.trash,
                "approve_pct": m.approve_pct,
                "buyout_pct": m.buyout_pct,       # raw: bought_out / approved
                "adj_buyout_pct": adj_buyout_pct, # adjusted for cohort age
                "trash_pct": m.trash_pct,
                "score_pct": score_pct,
                "avg_approve_pct": avg_approve,
                "avg_trash_pct": avg_trash,
                "issues": issues,
                "ok": len(issues) == 0,
            }
        )

    return results


async def run_and_save(
    df: pd.DataFrame,
    session: AsyncSession,
    period_days: int = 30,
    analysis_date: datetime.date | None = None,
) -> list[dict]:
    """Analyse all webmasters, persist each report, return list of result dicts."""
    results = analyse_all(df, period_days=period_days, analysis_date=analysis_date)
    for r in results:
        saved = await save_report(
            session,
            {
                "webmaster": r["webmaster"],
                "period_days": r["period_days"],
                "leads_total": r["leads_total"],
                "approved": r["approved"],
                "bought_out": r["bought_out"],
                "trash": r["trash"],
                "approve_pct": r["approve_pct"],
                "buyout_pct": r["adj_buyout_pct"],  # store adjusted in buyout_pct field
                "trash_pct": r["trash_pct"],
                "score_pct": r["score_pct"],
                "issues": r["issues"],
            },
        )
        r["id"] = saved.id
        r["created_at"] = saved.created_at.isoformat()
    return results
