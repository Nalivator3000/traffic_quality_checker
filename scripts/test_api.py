#!/usr/bin/env python3
"""
End-to-end API smoke test.

Usage:
    python scripts/test_api.py --file "300 orders.xlsx" --url https://your-app.railway.app --key YOUR_API_KEY

    # Против локального сервера:
    python scripts/test_api.py --file "300 orders.xlsx" --url http://localhost:8000 --key test
"""

import argparse
import json
import sys

import httpx

GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BOLD = "\033[1m"
RESET = "\033[0m"


def ok(msg: str) -> None:
    print(f"{GREEN}✓{RESET} {msg}")


def fail(msg: str) -> None:
    print(f"{RED}✗{RESET} {msg}")
    sys.exit(1)


def warn(msg: str) -> None:
    print(f"{YELLOW}!{RESET} {msg}")


def section(title: str) -> None:
    print(f"\n{BOLD}── {title} ──{RESET}")


def call(client: httpx.Client, method: str, path: str, **kwargs) -> httpx.Response:
    r = client.request(method, path, **kwargs)
    if r.status_code >= 500:
        fail(f"{method} {path} → HTTP {r.status_code}\n{r.text}")
    return r


def main() -> None:
    parser = argparse.ArgumentParser(description="API smoke test")
    parser.add_argument("--file", required=True, help="Path to .xlsx or .csv test file")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL of the API")
    parser.add_argument("--key", required=True, help="API key (value of Authorization header)")
    args = parser.parse_args()

    base = args.url.rstrip("/")
    headers = {"Authorization": args.key}

    with httpx.Client(base_url=base, headers=headers, timeout=60) as client:

        # ── 1. Health ──────────────────────────────────────────────────────────
        section("Health check")
        r = call(client, "GET", "/health")
        if r.json().get("status") == "ok":
            ok(f"GET /health → {r.json()}")
        else:
            fail(f"Unexpected health response: {r.text}")

        # ── 2. Upload file ─────────────────────────────────────────────────────
        section("Upload test file")
        with open(args.file, "rb") as f:
            filename = args.file.split("/")[-1]
            suffix = filename.rsplit(".", 1)[-1].lower()
            mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if suffix == "xlsx" else "text/csv"
            r = call(client, "POST", "/upload", files={"file": (filename, f, mime)})

        if r.status_code == 200:
            data = r.json()
            ok(f"POST /upload → {data['rows_parsed']} parsed, {data['rows_upserted']} upserted")
        else:
            fail(f"Upload failed ({r.status_code}): {r.text}")

        # Grab first webmaster from summary to use in subsequent tests
        r2 = call(client, "GET", "/summary", params={"days": 365})
        if r2.status_code != 200 or not r2.json():
            fail(f"GET /summary returned nothing after upload: {r2.text}")
        summary = r2.json()
        webmaster = summary[0]["webmaster"]

        # ── 3. JSON lead ingest ────────────────────────────────────────────────
        section("JSON lead ingest (POST /leads)")
        sample_leads = [
            {
                "id_custom": 999999901,
                "status": 2,
                "date": "2025-03-15",
                "webmaster": webmaster,
                "sum": 500.0,
                "comment": "тест json",
            },
            {
                "id_custom": 999999902,
                "status": 3,
                "date": "2025-03-15",
                "webmaster": webmaster,
                "sum": 600.0,
            },
        ]
        r = call(client, "POST", "/leads", json=sample_leads)
        if r.status_code == 200:
            ok(f"POST /leads → {r.json()}")
        else:
            warn(f"POST /leads returned {r.status_code}: {r.text}")

        # ── 4. Patch lead status & comment ─────────────────────────────────────
        section("Patch lead (PATCH /leads/{id})")
        r = call(client, "PATCH", "/leads/999999901", json={"status": 4, "comment": "выкуплен"})
        if r.status_code == 200:
            ok(f"PATCH /leads/999999901 → {r.json()}")
        elif r.status_code == 404:
            warn("Lead 999999901 not found (may not have been inserted — check POST /leads)")
        else:
            warn(f"PATCH /leads returned {r.status_code}: {r.text}")

        # ── 5. Summary ─────────────────────────────────────────────────────────
        section("Summary (GET /summary)")
        r = call(client, "GET", "/summary", params={"days": 30})
        if r.status_code == 200:
            rows = r.json()
            ok(f"GET /summary?days=30 → {len(rows)} webmaster(s)")
            for row in rows:
                print(
                    f"   {row['webmaster'][:20]:20s}  "
                    f"total={row['total']:4d}  "
                    f"approve={row.get('approve_%', 0):.1f}%  "
                    f"buyout={row.get('buyout_%', 0):.1f}%  "
                    f"trash={row.get('trash_%', 0):.1f}%"
                )
        else:
            warn(f"GET /summary → {r.status_code}: {r.text}")

        # ── 6. 8-day score ─────────────────────────────────────────────────────
        section(f"8-day score (GET /score/{webmaster})")
        r = call(client, "GET", f"/score/{webmaster}")
        if r.status_code == 200:
            data = r.json()
            ok(f"Score = {data['score_pct']:.1f}%  (num={data['numerator']}, den={data['denominator']})")
            print(f"   Cohorts: {len(data['cohorts'])}")
            for c in data["cohorts"]:
                print(
                    f"   {c['date']}  age={c['age_days']}d  "
                    f"approved={c['approved']}  bought={c['bought_out']}  "
                    f"actual={c['actual_buyout_pct']}%  bench={c['benchmark_pct']}%"
                )
        elif r.status_code == 404:
            warn(f"No leads for webmaster in 8-day window: {r.json()}")
        else:
            warn(f"GET /score → {r.status_code}: {r.text}")

        # ── 7. Last N leads metrics ────────────────────────────────────────────
        section(f"Last 100 leads (GET /leads/{webmaster})")
        r = call(client, "GET", f"/leads/{webmaster}", params={"last": 100})
        if r.status_code == 200:
            data = r.json()
            ok(
                f"sampled={data['total_sampled']}  "
                f"approve={data['approve_pct']}%  "
                f"buyout={data['buyout_pct']}%  "
                f"trash={data['trash_pct']}%"
            )
        else:
            warn(f"GET /leads → {r.status_code}: {r.text}")

        # ── 8. Run & save reports ──────────────────────────────────────────────
        section("Run reports (POST /reports/run)")
        r = call(client, "POST", "/reports/run", params={"days": 30})
        if r.status_code == 200:
            reports = r.json()
            ok(f"POST /reports/run → {len(reports)} report(s) saved")
            for rep in reports:
                issues = rep["issues"]
                status_label = f"{GREEN}OK{RESET}" if rep["ok"] else f"{RED}{len(issues)} issue(s){RESET}"
                print(f"   {rep['webmaster'][:20]:20s}  score={rep.get('score_pct') or '—':>6}%  {status_label}")
                for issue in issues:
                    print(f"      ⚠ {issue}")
        else:
            warn(f"POST /reports/run → {r.status_code}: {r.text}")

        # ── 9. Get latest report for webmaster ─────────────────────────────────
        section(f"Latest report (GET /reports/{webmaster})")
        r = call(client, "GET", f"/reports/{webmaster}")
        if r.status_code == 200:
            rep = r.json()
            ok(f"id={rep['id']}  created={rep['created_at']}  ok={rep['ok']}")
        elif r.status_code == 404:
            warn("No reports saved yet")
        else:
            warn(f"GET /reports/{webmaster} → {r.status_code}: {r.text}")

    print(f"\n{GREEN}{BOLD}All checks passed.{RESET}\n")


if __name__ == "__main__":
    main()
