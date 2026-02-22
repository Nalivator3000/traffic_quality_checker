"""
Core metric calculations for a set of leads (DataFrame).

All functions accept a pandas DataFrame (output of parser.load) and
return plain Python dicts or DataFrames ready for reporting.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

import pandas as pd

from app.config import APPROVE_STATUSES, BUYOUT_STATUSES, TRASH_STATUSES


@dataclass
class WebmasterMetrics:
    webmaster: str
    total: int
    approved: int
    bought_out: int
    trash: int
    approve_pct: float   # %
    buyout_pct: float    # % от всех лидов
    trash_pct: float     # %


def _pct(numerator: int, denominator: int) -> float:
    """Safe percentage (0–100)."""
    return round(numerator / denominator * 100, 2) if denominator else 0.0


def calc_webmaster_metrics(df: pd.DataFrame, webmaster: str) -> WebmasterMetrics:
    """Calculate approve/buyout/trash for a single webmaster's leads."""
    wdf = df[df["webmaster"] == webmaster]
    total = len(wdf)
    approved = int(wdf["status"].isin(APPROVE_STATUSES).sum())
    bought_out = int(wdf["status"].isin(BUYOUT_STATUSES).sum())
    trash = int(wdf["status"].isin(TRASH_STATUSES).sum())

    return WebmasterMetrics(
        webmaster=webmaster,
        total=total,
        approved=approved,
        bought_out=bought_out,
        trash=trash,
        approve_pct=_pct(approved, total),
        buyout_pct=_pct(bought_out, approved),  # выкуп от апрувов
        trash_pct=_pct(trash, total),
    )


def summary_by_webmaster(df: pd.DataFrame) -> pd.DataFrame:
    """
    Module 1 / Module 2 helper.

    Returns a DataFrame with one row per webmaster containing:
        webmaster, total, approved, bought_out, trash,
        approve_pct, buyout_pct, trash_pct
    """
    rows = []
    for wm in df["webmaster"].unique():
        m = calc_webmaster_metrics(df, wm)
        rows.append(
            {
                "webmaster": m.webmaster,
                "total": m.total,
                "approved": m.approved,
                "bought_out": m.bought_out,
                "trash": m.trash,
                "approve_%": m.approve_pct,
                "buyout_%": m.buyout_pct,
                "trash_%": m.trash_pct,
            }
        )
    result = pd.DataFrame(rows)
    result = result.sort_values("buyout_%", ascending=False).reset_index(drop=True)
    return result


def last_n_leads(df: pd.DataFrame, webmaster: str, n: int = 100) -> pd.DataFrame:
    """Return the last n leads (by date) for a webmaster."""
    wdf = df[df["webmaster"] == webmaster].copy()
    wdf = wdf.sort_values("date", ascending=False).head(n)
    return wdf.reset_index(drop=True)


def summary_last_n(df: pd.DataFrame, webmaster: str, n: int = 100) -> WebmasterMetrics:
    """Module 2: metrics on the last n leads of a webmaster."""
    subset = last_n_leads(df, webmaster, n)
    # Reuse calc_webmaster_metrics logic directly on subset
    total = len(subset)
    approved = int(subset["status"].isin(APPROVE_STATUSES).sum())
    bought_out = int(subset["status"].isin(BUYOUT_STATUSES).sum())
    trash = int(subset["status"].isin(TRASH_STATUSES).sum())
    return WebmasterMetrics(
        webmaster=webmaster,
        total=total,
        approved=approved,
        bought_out=bought_out,
        trash=trash,
        approve_pct=_pct(approved, total),
        buyout_pct=_pct(bought_out, approved),  # выкуп от апрувов
        trash_pct=_pct(trash, total),
    )


def daily_breakdown(
    df: pd.DataFrame,
    webmaster: str,
    analysis_date: datetime.date | None = None,
) -> pd.DataFrame:
    """
    Return per-day metrics for a webmaster.

    Columns: date, leads, approved, bought_out, trash,
             approve_%, buyout_%, trash_%
    """
    if analysis_date is None:
        analysis_date = max(df["date"])

    wdf = df[df["webmaster"] == webmaster].copy()
    grouped = wdf.groupby("date")

    rows = []
    for day, group in grouped:
        total = len(group)
        approved = int(group["status"].isin(APPROVE_STATUSES).sum())
        bought_out = int(group["status"].isin(BUYOUT_STATUSES).sum())
        trash = int(group["status"].isin(TRASH_STATUSES).sum())
        rows.append(
            {
                "date": day,
                "leads": total,
                "approved": approved,
                "bought_out": bought_out,
                "trash": trash,
                "approve_%": _pct(approved, total),
                "buyout_%": _pct(bought_out, approved),  # выкуп от апрувов
                "trash_%": _pct(trash, total),
            }
        )

    result = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    return result
