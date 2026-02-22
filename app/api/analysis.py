import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import metrics, scoring
from app.api.deps import require_api_key
from app.crud import fetch_leads_df
from app.db import get_db

router = APIRouter(tags=["analysis"])


@router.get("/summary")
async def get_summary(
    days: int = Query(default=30, ge=1, le=365, description="Look-back window in days"),
    session: AsyncSession = Depends(get_db),
    _key: str = Depends(require_api_key),
):
    """
    Summary metrics (approve%, buyout%, trash%) per webmaster over the last N days.
    """
    since = datetime.date.today() - datetime.timedelta(days=days)
    df = await fetch_leads_df(session, since=since)
    if df.empty:
        return []
    summary = metrics.summary_by_webmaster(df)
    return summary.to_dict(orient="records")


@router.get("/score/{webmaster}")
async def get_score(
    webmaster: str,
    session: AsyncSession = Depends(get_db),
    _key: str = Depends(require_api_key),
):
    """
    8-day weighted buyout score for one webmaster.
    """
    since = datetime.date.today() - datetime.timedelta(days=8)
    df = await fetch_leads_df(session, webmaster=webmaster, since=since)
    if df.empty:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"No leads found for webmaster {webmaster!r}")
    result = scoring.calc_score(df, webmaster)
    return {
        "webmaster": result.webmaster,
        "analysis_date": result.analysis_date.isoformat(),
        "score": result.score,
        "score_pct": result.score_pct,
        "numerator": result.numerator,
        "denominator": result.denominator,
        "cohorts": [
            {
                "date": c.date.isoformat(),
                "age_days": c.age_days,
                "leads": c.leads,
                "approved": c.approved,
                "bought_out": c.bought_out,
                "actual_buyout_pct": round(c.actual_buyout_rate * 100, 2),
                "benchmark_pct": round(c.benchmark_rate * 100, 2),
            }
            for c in result.cohorts
        ],
    }


@router.get("/leads/{webmaster}")
async def get_leads_metrics(
    webmaster: str,
    last: int = Query(default=100, ge=1, le=10_000, description="Number of most recent leads"),
    session: AsyncSession = Depends(get_db),
    _key: str = Depends(require_api_key),
):
    """
    Metrics on the last N leads for one webmaster (approve%, buyout%, trash%).
    """
    df = await fetch_leads_df(session, webmaster=webmaster)
    if df.empty:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"No leads found for webmaster {webmaster!r}")
    m = metrics.summary_last_n(df, webmaster, n=last)
    return {
        "webmaster": m.webmaster,
        "total_sampled": m.total,
        "approved": m.approved,
        "bought_out": m.bought_out,
        "trash": m.trash,
        "approve_pct": m.approve_pct,
        "buyout_pct": m.buyout_pct,
        "trash_pct": m.trash_pct,
    }
