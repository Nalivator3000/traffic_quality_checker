import datetime

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Lead


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


async def fetch_leads_df(
    session: AsyncSession,
    webmaster: str | None = None,
    since: datetime.date | None = None,
) -> pd.DataFrame:
    """
    Fetch leads from DB and return a DataFrame with the same shape
    as parser.load() output: [id_custom, status, date, webmaster, sum].

    Parameters
    ----------
    webmaster : filter to a single webmaster
    since     : filter to leads where date >= since
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

    # Mirror parser.load() normalization so metrics.py / scoring.py work unchanged
    df["id_custom"] = pd.to_numeric(df["id_custom"], errors="coerce")
    df["status"] = pd.to_numeric(df["status"], errors="coerce").astype("Int64")
    df["sum"] = pd.to_numeric(df["sum"], errors="coerce").fillna(0)
    df["webmaster"] = df["webmaster"].astype(str).str.strip()
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date

    return df.reset_index(drop=True)
