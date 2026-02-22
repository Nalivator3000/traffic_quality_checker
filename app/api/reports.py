"""
Analysis reports: run analysis and store results in DB.

POST /reports/run?days=30[&webmaster=...]  — run & save
GET  /reports?webmaster=...&limit=20       — history of saved reports
GET  /reports/{webmaster}                  — latest report for one webmaster
GET  /status                               — current status snapshot (for TG bot / Superset)
GET  /status/{webmaster}                   — current status for one webmaster
"""

import datetime
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis import run_and_save
from app.api.deps import require_api_key
from app.crud import fetch_leads_df, get_reports, get_webmaster_status
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
        "adj_buyout_pct": report.buyout_pct,
        "trash_pct": report.trash_pct,
        "score_pct": report.score_pct,
        "issues": json.loads(report.issues),
        "ok": len(json.loads(report.issues)) == 0,
    }


def _status_to_dict(s) -> dict[str, Any]:
    return {
        "webmaster": s.webmaster,
        "updated_at": s.updated_at.isoformat(),
        "period_days": s.period_days,
        "leads_total": s.leads_total,
        "approved": s.approved,
        "bought_out": s.bought_out,
        "trash": s.trash,
        "approve_pct": s.approve_pct,
        "avg_approve_pct": s.avg_approve_pct,
        "adj_buyout_pct": s.adj_buyout_pct,
        "trash_pct": s.trash_pct,
        "avg_trash_pct": s.avg_trash_pct,
        "score_pct": s.score_pct,
        "issues": json.loads(s.issues),
        "ok": s.ok,
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
    Also updates webmaster_status table (used by TG bot / Superset).
    """
    since = datetime.date.today() - datetime.timedelta(days=days)
    df = await fetch_leads_df(session, webmaster=webmaster, since=since)

    if df.empty:
        return []

    return await run_and_save(df, session, period_days=days)


@router.get("/status", status_code=status.HTTP_200_OK)
async def get_status(
    only_issues: bool = Query(default=False, description="Return only webmasters with problems"),
    session: AsyncSession = Depends(get_db),
    _key: str = Depends(require_api_key),
) -> list[dict[str, Any]]:
    """
    Current status snapshot — one row per webmaster, updated each cron run.
    Sorted: problematic webmasters first, then by name.
    Use ?only_issues=true to get only problematic webmasters.
    """
    rows = await get_webmaster_status(session)
    result = [_status_to_dict(r) for r in rows]
    if only_issues:
        result = [r for r in result if not r["ok"]]
    return result


@router.get("/status/{webmaster}", status_code=status.HTTP_200_OK)
async def get_one_status(
    webmaster: str,
    session: AsyncSession = Depends(get_db),
    _key: str = Depends(require_api_key),
) -> dict[str, Any]:
    """Current status for one webmaster."""
    rows = await get_webmaster_status(session, webmaster=webmaster)
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No status for {webmaster!r}. Run POST /reports/run first.",
        )
    return _status_to_dict(rows[0])


@router.get("", status_code=status.HTTP_200_OK)
async def list_reports(
    webmaster: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    _key: str = Depends(require_api_key),
) -> list[dict[str, Any]]:
    """History of saved reports (most recent first)."""
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
