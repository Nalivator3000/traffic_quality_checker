"""
Analysis reports: run analysis and store results in DB.

POST /reports/run?days=30[&webmaster=...]  — run & save
GET  /reports?webmaster=...&limit=20       — list saved reports
GET  /reports/{webmaster}                  — latest report for one webmaster
"""

import datetime
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import metrics, scoring
from app.api.deps import require_api_key
from app.crud import detect_issues, fetch_leads_df, get_reports, save_report
from app.db import get_db

router = APIRouter(prefix="/reports", tags=["reports"])


def _report_to_dict(report) -> dict[str, Any]:
    return {
        "id": report.id,
        "webmaster": report.webmaster,
        "created_at": report.created_at.isoformat(),
        "period_days": report.period_days,
        "leads_total": report.leads_total,
        "approved": report.approved,
        "bought_out": report.bought_out,
        "trash": report.trash,
        "approve_pct": report.approve_pct,
        "buyout_pct": report.buyout_pct,
        "trash_pct": report.trash_pct,
        "score_pct": report.score_pct,
        "issues": json.loads(report.issues),
        "ok": len(json.loads(report.issues)) == 0,
    }


@router.post("/run", status_code=status.HTTP_200_OK)
async def run_reports(
    days: int = Query(default=30, ge=1, le=365, description="Look-back window in days"),
    webmaster: str | None = Query(default=None, description="Limit to one webmaster"),
    session: AsyncSession = Depends(get_db),
    _key: str = Depends(require_api_key),
) -> list[dict[str, Any]]:
    """
    Run analysis for all webmasters (or one) and save results to DB.
    Returns the list of saved reports with highlighted issues.
    """
    since = datetime.date.today() - datetime.timedelta(days=days)
    df = await fetch_leads_df(session, webmaster=webmaster, since=since)

    if df.empty:
        return []

    webmasters = df["webmaster"].unique().tolist()
    saved = []

    for wm in webmasters:
        m = metrics.calc_webmaster_metrics(df, wm)

        # Try to get 8-day score
        score_pct: float | None = None
        since_score = datetime.date.today() - datetime.timedelta(days=8)
        df_score = df[(df["webmaster"] == wm) & (df["date"] >= since_score)]
        if not df_score.empty:
            result = scoring.calc_score(df_score, wm)
            score_pct = result.score_pct

        issues = detect_issues(m.approve_pct, m.buyout_pct, m.trash_pct, score_pct)

        report = await save_report(
            session,
            {
                "webmaster": wm,
                "period_days": days,
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
        saved.append(_report_to_dict(report))

    return saved


@router.get("", status_code=status.HTTP_200_OK)
async def list_reports(
    webmaster: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    _key: str = Depends(require_api_key),
) -> list[dict[str, Any]]:
    """List saved reports (most recent first)."""
    reports = await get_reports(session, webmaster=webmaster, limit=limit)
    return [_report_to_dict(r) for r in reports]


@router.get("/{webmaster}", status_code=status.HTTP_200_OK)
async def get_webmaster_report(
    webmaster: str,
    session: AsyncSession = Depends(get_db),
    _key: str = Depends(require_api_key),
) -> dict[str, Any]:
    """Latest saved report for one webmaster."""
    reports = await get_reports(session, webmaster=webmaster, limit=1)
    if not reports:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No reports found for webmaster {webmaster!r}. Run POST /reports/run first.",
        )
    return _report_to_dict(reports[0])
