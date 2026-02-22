import datetime
import json

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Lead, WebmasterReport


async def upsert_leads(session: AsyncSession, df: pd.DataFrame) -> int:
    """
    Insert or update leads from a DataFrame.
    ON CONFLICT (id_custom) DO UPDATE all mutable columns.
    Returns the number of rows processed.
    """
    records = df[["id_custom", "status", "date", "webmaster", "sum"]].to_dict(orient="records")
    if not records:
        return 0

    stmt = pg_insert(Lead).values(records)
    stmt = stmt.on_conflict_do_update(
        index_elements=["id_custom"],
        set_={
            "status": stmt.excluded.status,
            "date": stmt.excluded.date,
            "webmaster": stmt.excluded.webmaster,
            "sum": stmt.excluded.sum,
            "imported_at": func.now(),
        },
    )
    await session.execute(stmt)
    await session.commit()
    return len(records)


async def upsert_leads_json(session: AsyncSession, records: list[dict]) -> int:
    """
    Insert or update leads from a list of dicts (JSON API input).
    Each dict must have: id_custom, status, date (str or date), webmaster, sum.
    comment is optional.
    Returns the number of rows processed.
    """
    if not records:
        return 0

    # Normalise date field
    normalised = []
    for r in records:
        row = dict(r)
        if isinstance(row.get("date"), str):
            row["date"] = datetime.date.fromisoformat(row["date"])
        normalised.append(row)

    allowed = {"id_custom", "status", "date", "webmaster", "sum", "comment"}
    clean = [{k: v for k, v in r.items() if k in allowed} for r in normalised]

    stmt = pg_insert(Lead).values(clean)
    update_set = {
        "status": stmt.excluded.status,
        "date": stmt.excluded.date,
        "webmaster": stmt.excluded.webmaster,
        "sum": stmt.excluded.sum,
        "imported_at": func.now(),
    }
    # Update comment only if provided in the incoming record
    update_set["comment"] = stmt.excluded.comment
    stmt = stmt.on_conflict_do_update(
        index_elements=["id_custom"],
        set_=update_set,
    )
    await session.execute(stmt)
    await session.commit()
    return len(clean)


async def patch_lead(
    session: AsyncSession,
    id_custom: int,
    status: int | None = None,
    comment: str | None = None,
) -> bool:
    """
    Update status and/or comment for a single lead.
    Returns True if the lead was found and updated, False otherwise.
    """
    result = await session.get(Lead, id_custom)
    if result is None:
        return False
    if status is not None:
        result.status = status
    if comment is not None:
        result.comment = comment
    await session.commit()
    return True


async def delete_lead(session: AsyncSession, id_custom: int) -> bool:
    """Delete a single lead. Returns True if found and deleted."""
    row = await session.get(Lead, id_custom)
    if row is None:
        return False
    await session.delete(row)
    await session.commit()
    return True


async def fetch_leads_df(
    session: AsyncSession,
    webmaster: str | None = None,
    since: datetime.date | None = None,
) -> pd.DataFrame:
    """
    Fetch leads from DB and return a DataFrame with the same shape
    as parser.load() output: [id_custom, status, date, webmaster, sum].
    """
    q = select(
        Lead.id_custom,
        Lead.status,
        Lead.date,
        Lead.webmaster,
        Lead.sum,
    )
    if webmaster is not None:
        q = q.where(Lead.webmaster == webmaster)
    if since is not None:
        q = q.where(Lead.date >= since)

    result = await session.execute(q)
    rows = result.fetchall()

    df = pd.DataFrame(rows, columns=["id_custom", "status", "date", "webmaster", "sum"])

    if df.empty:
        return df

    df["id_custom"] = pd.to_numeric(df["id_custom"], errors="coerce")
    df["status"] = pd.to_numeric(df["status"], errors="coerce").astype("Int64")
    df["sum"] = pd.to_numeric(df["sum"], errors="coerce").fillna(0)
    df["webmaster"] = df["webmaster"].astype(str).str.strip()
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date

    return df.reset_index(drop=True)


def detect_issues(
    approve_pct: float,
    buyout_pct: float,
    trash_pct: float,
    score_pct: float | None,
) -> list[str]:
    """Return a list of human-readable problem descriptions."""
    issues = []
    if trash_pct > 20:
        issues.append(f"Высокий треш: {trash_pct:.1f}% (норма ≤ 20%)")
    if approve_pct < 30:
        issues.append(f"Низкий апрув: {approve_pct:.1f}% (норма ≥ 30%)")
    if buyout_pct < 65:
        issues.append(f"Низкий выкуп: {buyout_pct:.1f}% (норма ≥ 65%)")
    if score_pct is not None and score_pct < 70:
        issues.append(f"Слабый 8-дневный скор: {score_pct:.1f}% (норма ≥ 70%)")
    return issues


async def save_report(session: AsyncSession, data: dict) -> WebmasterReport:
    """Persist a WebmasterReport row and return the ORM object."""
    report = WebmasterReport(
        webmaster=data["webmaster"],
        period_days=data["period_days"],
        leads_total=data["leads_total"],
        approved=data["approved"],
        bought_out=data["bought_out"],
        trash=data["trash"],
        approve_pct=data["approve_pct"],
        buyout_pct=data["buyout_pct"],
        trash_pct=data["trash_pct"],
        score_pct=data.get("score_pct"),
        issues=json.dumps(data.get("issues", []), ensure_ascii=False),
    )
    session.add(report)
    await session.commit()
    await session.refresh(report)
    return report


async def get_reports(
    session: AsyncSession,
    webmaster: str | None = None,
    limit: int = 50,
) -> list[WebmasterReport]:
    """Fetch recent reports, optionally filtered by webmaster."""
    q = select(WebmasterReport).order_by(WebmasterReport.created_at.desc()).limit(limit)
    if webmaster is not None:
        q = q.where(WebmasterReport.webmaster == webmaster)
    result = await session.execute(q)
    return list(result.scalars().all())
