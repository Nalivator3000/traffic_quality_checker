"""
Load and normalize leads from Excel (.xlsx) or CSV files.

Keeps only columns needed for analysis; everything else is dropped.
"""

from pathlib import Path

import pandas as pd


# Subset of columns we actually use
_USED_COLS = [
    "id_custom",
    "status",
    "date",
    "webmaster",
    "sum",
]


def load(path: str | Path) -> pd.DataFrame:
    """
    Load leads from an Excel or CSV file and return a clean DataFrame.

    Columns returned:
        id_custom  – order ID (int)
        status     – CRM status code (int)
        date       – creation date (date, no time)
        webmaster  – webmaster identifier (str)
        sum        – order amount (float, 0 if empty)
    """
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix in (".xlsx", ".xls"):
        raw = pd.read_excel(path, usecols=_USED_COLS)
    elif suffix == ".csv":
        raw = pd.read_csv(path, usecols=_USED_COLS)
    else:
        raise ValueError(f"Unsupported file format: {suffix!r}. Use .xlsx or .csv")

    df = raw.copy()

    # Normalize types
    df["id_custom"] = pd.to_numeric(df["id_custom"], errors="coerce")
    df["status"] = pd.to_numeric(df["status"], errors="coerce").astype("Int64")
    df["sum"] = pd.to_numeric(df["sum"], errors="coerce").fillna(0)
    df["webmaster"] = df["webmaster"].astype(str).str.strip()

    # Convert datetime → date only
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date

    # Drop rows without a date or status (unusable)
    df = df.dropna(subset=["date", "status"])

    return df.reset_index(drop=True)
