"""
Traffic Quality Checker — CLI entry point.

Usage:
    python main.py <input_file> [--output <output.xlsx>] [--date YYYY-MM-DD]

Arguments:
    input_file      Path to .xlsx or .csv file with leads
    --output        Output report path (default: report_<timestamp>.xlsx)
    --date          Analysis reference date (default: latest date in file)

Example:
    python main.py "300 orders.xlsx"
    python main.py leads.csv --output my_report.xlsx --date 2025-03-21
"""

import argparse
import datetime
import sys
from pathlib import Path

from app import parser, metrics, scoring, reporter


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Traffic quality checker")
    p.add_argument("input", help="Path to .xlsx or .csv file with leads")
    p.add_argument("--output", default=None, help="Output .xlsx path")
    p.add_argument("--date", default=None, help="Analysis reference date YYYY-MM-DD")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: File not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    # Default output name
    if args.output is None:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path(f"report_{timestamp}.xlsx")
    else:
        output_path = Path(args.output)

    # Reference date
    analysis_date = None
    if args.date:
        try:
            analysis_date = datetime.date.fromisoformat(args.date)
        except ValueError:
            print(f"ERROR: Invalid date format: {args.date!r}. Use YYYY-MM-DD", file=sys.stderr)
            sys.exit(1)

    # -----------------------------------------------------------------------
    print(f"Loading {input_path} ...")
    df = parser.load(input_path)
    print(f"  Loaded {len(df):,} leads | "
          f"date range: {min(df['date'])} → {max(df['date'])}")

    webmasters = df["webmaster"].unique().tolist()
    print(f"  Webmasters: {len(webmasters)}")

    if analysis_date is None:
        analysis_date = max(df["date"])
    print(f"  Analysis date: {analysis_date}")

    # -----------------------------------------------------------------------
    # Module 1/2 – summary per webmaster (all leads)
    print("\nCalculating summary metrics ...")
    summary_df = metrics.summary_by_webmaster(df)

    # Module 2 – last 100 leads (print to console for quick check)
    print("\nLast-100 snapshot (per webmaster):")
    for wm in webmasters:
        m = metrics.summary_last_n(df, wm, n=100)
        print(f"  {wm}: total={m.total} approve={m.approve_pct}% "
              f"buyout={m.buyout_pct}% trash={m.trash_pct}%")

    # -----------------------------------------------------------------------
    # Module 3 – 8-day weighted score
    print("\nCalculating 8-day scores ...")
    scoring_results = []
    for wm in webmasters:
        result = scoring.calc_score(df, wm, analysis_date=analysis_date)
        scoring_results.append(result)
        print(f"  {wm}: score={result.score_pct:.1f}%  "
              f"(num={result.numerator:.1f} / den={result.denominator:.1f})")

    # -----------------------------------------------------------------------
    # Daily breakdown per webmaster
    daily_dfs: dict[str, object] = {}
    for wm in webmasters:
        daily_dfs[wm] = metrics.daily_breakdown(df, wm, analysis_date=analysis_date)

    # -----------------------------------------------------------------------
    # Write report
    print(f"\nWriting report → {output_path} ...")
    saved = reporter.save_report(output_path, summary_df, scoring_results, daily_dfs)
    print(f"Done. Report saved: {saved}")


if __name__ == "__main__":
    main()
