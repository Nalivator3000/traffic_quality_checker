"""
Module 3: 8-day weighted buyout score.

Formula
-------
For each day cohort d (d=1 is yesterday, d=8 is 8 days ago):

    numerator   = Σ  approved_d × actual_buyout_rate_d
    denominator = Σ  approved_d × benchmark_buyout_rate_d

    score = numerator / denominator

Where:
    approved_d        — number of APPROVED leads in that day's cohort
    actual_buyout_rate_d  — bought_out / approved  (fraction that were redeemed)
    benchmark_buyout_rate_d — target redemption rate for leads of this age

A score of 1.0 means the webmaster is exactly on target.
A score > 1.0 means above-target buyout, < 1.0 means below-target.

Cohorts older than SCORING_WINDOW_DAYS use the benchmark for the last day in
the window (the highest target rate).
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

import pandas as pd

from app.config import APPROVE_STATUSES, BUYOUT_BENCHMARK, BUYOUT_STATUSES, SCORING_WINDOW_DAYS


@dataclass
class CohortRow:
    date: datetime.date
    age_days: int               # calendar days since creation
    leads: int                  # all leads on this day
    approved: int               # approved leads (base for rate calculation)
    bought_out: int
    actual_buyout_rate: float   # bought_out / approved  (0.0–1.0)
    benchmark_rate: float       # target buyout rate for this age (0.0–1.0)
    weighted_actual: float      # approved × actual_buyout_rate
    weighted_benchmark: float   # approved × benchmark_rate


@dataclass
class ScoringResult:
    webmaster: str
    analysis_date: datetime.date
    cohorts: list[CohortRow] = field(default_factory=list)
    numerator: float = 0.0
    denominator: float = 0.0
    score: float = 0.0          # numerator / denominator
    score_pct: float = 0.0      # score × 100


def _benchmark_for_age(age_days: int) -> float:
    """Return the benchmark buyout rate for a cohort of a given age."""
    clamped = max(1, min(age_days, SCORING_WINDOW_DAYS))
    return BUYOUT_BENCHMARK[clamped]


def calc_score(
    df: pd.DataFrame,
    webmaster: str,
    analysis_date: datetime.date | None = None,
) -> ScoringResult:
    """
    Calculate the 8-day weighted buyout score for one webmaster.

    Parameters
    ----------
    df : DataFrame from parser.load()
    webmaster : webmaster identifier string
    analysis_date : the "today" reference date. Defaults to the latest
                    date found in the DataFrame.
    """
    if analysis_date is None:
        analysis_date = max(df["date"])

    wdf = df[df["webmaster"] == webmaster].copy()

    # Keep only leads within the scoring window
    cutoff = analysis_date - datetime.timedelta(days=SCORING_WINDOW_DAYS)
    wdf = wdf[wdf["date"] >= cutoff]

    if wdf.empty:
        return ScoringResult(webmaster=webmaster, analysis_date=analysis_date)

    # Group by creation date
    grouped = wdf.groupby("date")

    cohorts: list[CohortRow] = []
    numerator = 0.0
    denominator = 0.0

    for day, group in grouped:
        age_days = (analysis_date - day).days
        if age_days < 1:
            age_days = 1  # leads from today count as age 1

        leads = len(group)
        approved = int(group["status"].isin(APPROVE_STATUSES).sum())
        bought_out = int(group["status"].isin(BUYOUT_STATUSES).sum())
        # Rate is relative to approved leads (not all leads)
        actual_rate = bought_out / approved if approved else 0.0
        benchmark_rate = _benchmark_for_age(age_days)

        w_actual = approved * actual_rate
        w_benchmark = approved * benchmark_rate

        numerator += w_actual
        denominator += w_benchmark

        cohorts.append(
            CohortRow(
                date=day,
                age_days=age_days,
                leads=leads,
                approved=approved,
                bought_out=bought_out,
                actual_buyout_rate=round(actual_rate, 4),
                benchmark_rate=round(benchmark_rate, 4),
                weighted_actual=round(w_actual, 2),
                weighted_benchmark=round(w_benchmark, 2),
            )
        )

    cohorts.sort(key=lambda c: c.date)

    score = round(numerator / denominator, 4) if denominator else 0.0
    return ScoringResult(
        webmaster=webmaster,
        analysis_date=analysis_date,
        cohorts=cohorts,
        numerator=round(numerator, 2),
        denominator=round(denominator, 2),
        score=score,
        score_pct=round(score * 100, 2),
    )


def calc_adjusted_buyout(
    df: pd.DataFrame,
    webmaster: str,
    analysis_date: datetime.date | None = None,
    period_days: int = 30,
) -> float:
    """
    Adjusted buyout rate: projects young cohorts to their expected mature rate.

    For each cohort of age_d days:
      - age_d >= 8  → use actual rate as-is   (coef = 1.0)
      - age_d <  8  → adjusted = min(actual × (0.65 / benchmark_d), 1.0)

    Returns weighted average adjusted rate across all approved leads, as %.
    """
    if analysis_date is None:
        analysis_date = datetime.date.today()

    since = analysis_date - datetime.timedelta(days=period_days)
    wdf = df[(df["webmaster"] == webmaster) & (df["date"] >= since)].copy()

    if wdf.empty:
        return 0.0

    total_approved = 0
    total_weighted = 0.0

    for day, group in wdf.groupby("date"):
        age_days = (analysis_date - day).days
        if age_days < 1:
            age_days = 1

        approved = int(group["status"].isin(APPROVE_STATUSES).sum())
        bought_out = int(group["status"].isin(BUYOUT_STATUSES).sum())
        if approved == 0:
            continue

        actual_rate = bought_out / approved

        if age_days >= SCORING_WINDOW_DAYS:
            adjusted_rate = actual_rate
        else:
            benchmark = BUYOUT_BENCHMARK[age_days]
            adjusted_rate = min(actual_rate * (0.65 / benchmark), 1.0)

        total_weighted += approved * adjusted_rate
        total_approved += approved

    if total_approved == 0:
        return 0.0

    return round(total_weighted / total_approved * 100, 2)


def cohorts_to_dataframe(result: ScoringResult) -> pd.DataFrame:
    """Convert a ScoringResult's cohorts to a DataFrame for reporting."""
    rows = [
        {
            "date": c.date,
            "age_days": c.age_days,
            "leads": c.leads,
            "approved": c.approved,
            "bought_out": c.bought_out,
            "actual_buyout_%": round(c.actual_buyout_rate * 100, 2),
            "benchmark_%": round(c.benchmark_rate * 100, 2),
            "weighted_actual": c.weighted_actual,
            "weighted_benchmark": c.weighted_benchmark,
        }
        for c in result.cohorts
    ]
    return pd.DataFrame(rows)
