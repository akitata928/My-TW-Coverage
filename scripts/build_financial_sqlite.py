"""
build_financial_sqlite.py — Build a local SQLite baseline from Markdown reports.

This script is read-only toward Pilot_Reports. It parses the current
## 財務概況 section in each ticker report and stores normalized rows in SQLite.

Usage:
  python scripts/build_financial_sqlite.py --from-markdown
  python scripts/build_financial_sqlite.py --from-markdown --db data/financial_snapshots.sqlite
  python scripts/build_financial_sqlite.py --from-markdown --ticker 2308
"""

import argparse
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import PROJECT_ROOT, REPORTS_DIR, setup_stdout


DEFAULT_DB = os.path.join(PROJECT_ROOT, "data", "financial_snapshots.sqlite")
FINANCIAL_METRIC_HEADINGS = {
    "annual": "### 年度關鍵財務數據",
    "quarterly": "### 季度關鍵財務數據",
}
VALUATION_FIELDS = {
    "P/E (TTM)": "trailing_pe",
    "Forward P/E": "forward_pe",
    "P/S (TTM)": "price_to_sales",
    "P/B": "price_to_book",
    "EV/EBITDA": "ev_to_ebitda",
}


def clean_wikilink(text):
    return re.sub(r"\[\[([^\]]+)\]\]", r"\1", text).strip()


def parse_number(value):
    value = value.strip()
    if not value or value in {"-", "N/A", "nan", "None"}:
        return None
    value = value.replace(",", "").replace("$", "")
    try:
        return float(value)
    except ValueError:
        return None


def parse_money_million(value):
    number = parse_number(value)
    return number


def parse_metadata(content, fallback_sector=None):
    title_match = re.search(r"^#\s+(\d{4})\s+-\s+(.+)$", content, re.MULTILINE)
    ticker = title_match.group(1) if title_match else None
    name = clean_wikilink(title_match.group(2)) if title_match else None

    sector_match = re.search(r"^\*\*板塊:\*\*\s*(.+)$", content, re.MULTILINE)
    industry_match = re.search(r"^\*\*產業:\*\*\s*(.+)$", content, re.MULTILINE)
    market_cap_match = re.search(r"^\*\*市值:\*\*\s*(.+?)\s*百萬台幣\s*$", content, re.MULTILINE)
    ev_match = re.search(r"^\*\*企業價值:\*\*\s*(.+?)(?:\s*百萬台幣)?\s*$", content, re.MULTILINE)

    return {
        "ticker": ticker,
        "name": name,
        "sector": sector_match.group(1).strip() if sector_match else None,
        "industry": industry_match.group(1).strip() if industry_match else fallback_sector,
        "market_cap_million_ntd": parse_money_million(market_cap_match.group(1)) if market_cap_match else None,
        "enterprise_value_million_ntd": parse_money_million(ev_match.group(1)) if ev_match else None,
    }


def split_markdown_row(line):
    line = line.strip()
    if not line.startswith("|") or not line.endswith("|"):
        return []
    return [cell.strip() for cell in line.strip("|").split("|")]


def is_separator_row(cells):
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells)


def extract_table_after_heading(content, heading):
    start = content.find(heading)
    if start < 0:
        return []

    table_lines = []
    in_table = False
    for line in content[start:].splitlines()[1:]:
        if line.startswith("### ") and in_table:
            break
        if line.strip().startswith("|"):
            table_lines.append(line)
            in_table = True
            continue
        if in_table and line.strip() == "":
            break

    rows = [split_markdown_row(line) for line in table_lines]
    return [row for row in rows if row and not is_separator_row(row)]


def parse_metric_table(content, period_type):
    heading = FINANCIAL_METRIC_HEADINGS[period_type]
    rows = extract_table_after_heading(content, heading)
    if len(rows) < 2:
        return []

    header = rows[0]
    periods = header[1:]
    metrics = []
    for row in rows[1:]:
        if len(row) < 2:
            continue
        metric = row[0].strip()
        unit = "percent" if "%" in metric else "million_ntd"
        for period_end, raw_value in zip(periods, row[1:]):
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", period_end):
                continue
            metrics.append(
                {
                    "period_type": period_type,
                    "period_end": period_end,
                    "metric": metric,
                    "value": parse_number(raw_value),
                    "unit": unit,
                }
            )
    return metrics


def parse_valuation(content, metadata):
    heading_match = re.search(r"### 估值指標\s*\((.*?)\)", content)
    rows = extract_table_after_heading(content, "### 估值指標")
    if len(rows) < 2:
        return None

    result = {
        "price": None,
        "valuation_as_of": None,
        "ttm_period_end": None,
        "forward_period_end": None,
        "trailing_pe": None,
        "forward_pe": None,
        "price_to_sales": None,
        "price_to_book": None,
        "ev_to_ebitda": None,
        "market_cap_million_ntd": metadata.get("market_cap_million_ntd"),
        "enterprise_value_million_ntd": metadata.get("enterprise_value_million_ntd"),
    }

    if heading_match:
        heading = heading_match.group(1)
        price_match = re.search(r"股價\s*\$?([\d,]+(?:\.\d+)?)", heading)
        as_of_match = re.search(r"as of\s*(\d{4}-\d{2}-\d{2})", heading)
        ttm_match = re.search(r"TTM 截至\s*(\d{4}-\d{2}-\d{2})", heading)
        forward_match = re.search(r"Forward 預估至\s*(\d{4}-\d{2}-\d{2})", heading)

        result["price"] = parse_number(price_match.group(1)) if price_match else None
        result["valuation_as_of"] = as_of_match.group(1) if as_of_match else None
        result["ttm_period_end"] = ttm_match.group(1) if ttm_match else None
        result["forward_period_end"] = forward_match.group(1) if forward_match else None

    headers = rows[0]
    values = rows[1]
    for header, value in zip(headers, values):
        field = VALUATION_FIELDS.get(header.strip())
        if field:
            result[field] = parse_number(value)

    return result


def parse_ticker_from_filename(filename):
    normal = re.match(r"^(\d{4})_", filename)
    if normal:
        return normal.group(1)

    reversed_name = re.match(r"^.+_(\d{4})\.md$", filename)
    if reversed_name:
        return reversed_name.group(1)

    return None


def iter_report_files(ticker_filter=None):
    for sector_name in sorted(os.listdir(REPORTS_DIR)):
        sector_path = os.path.join(REPORTS_DIR, sector_name)
        if not os.path.isdir(sector_path):
            continue

        for filename in sorted(os.listdir(sector_path)):
            if not filename.endswith(".md"):
                continue
            ticker = parse_ticker_from_filename(filename)
            if not ticker:
                continue
            if ticker_filter and ticker not in ticker_filter:
                continue
            yield ticker, sector_name, os.path.join(sector_path, filename)


def init_db(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS companies (
          ticker TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          sector TEXT,
          industry TEXT,
          report_path TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS financial_metrics (
          ticker TEXT NOT NULL,
          period_type TEXT NOT NULL,
          period_end TEXT NOT NULL,
          metric TEXT NOT NULL,
          value REAL,
          unit TEXT NOT NULL,
          source TEXT NOT NULL,
          fetched_at TEXT NOT NULL,
          run_id TEXT NOT NULL,
          PRIMARY KEY (ticker, period_type, period_end, metric, fetched_at)
        );

        CREATE TABLE IF NOT EXISTS valuation_snapshots (
          ticker TEXT NOT NULL,
          fetched_at TEXT NOT NULL,
          valuation_as_of TEXT,
          ttm_period_end TEXT,
          forward_period_end TEXT,
          price REAL,
          trailing_pe REAL,
          forward_pe REAL,
          price_to_sales REAL,
          price_to_book REAL,
          ev_to_ebitda REAL,
          market_cap_million_ntd REAL,
          enterprise_value_million_ntd REAL,
          source TEXT NOT NULL,
          run_id TEXT NOT NULL,
          PRIMARY KEY (ticker, fetched_at)
        );

        CREATE TABLE IF NOT EXISTS ingest_runs (
          run_id TEXT PRIMARY KEY,
          started_at TEXT NOT NULL,
          finished_at TEXT,
          mode TEXT NOT NULL,
          scope TEXT NOT NULL,
          status TEXT NOT NULL,
          notes TEXT
        );

        CREATE VIEW IF NOT EXISTS latest_financial_metrics AS
        SELECT fm.*
        FROM financial_metrics fm
        JOIN (
          SELECT ticker, period_type, period_end, metric, MAX(fetched_at) AS fetched_at
          FROM financial_metrics
          GROUP BY ticker, period_type, period_end, metric
        ) latest
        ON fm.ticker = latest.ticker
        AND fm.period_type = latest.period_type
        AND fm.period_end = latest.period_end
        AND fm.metric = latest.metric
        AND fm.fetched_at = latest.fetched_at;

        CREATE INDEX IF NOT EXISTS idx_financial_metrics_lookup
          ON financial_metrics (ticker, period_type, metric, period_end);

        CREATE INDEX IF NOT EXISTS idx_financial_metrics_screen
          ON financial_metrics (metric, period_type, period_end);

        CREATE INDEX IF NOT EXISTS idx_valuation_snapshots_ticker
          ON valuation_snapshots (ticker, fetched_at);
        """
    )


def import_markdown_reports(db_path, ticker_filter=None, fetched_at=None):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    started_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    fetched_at = fetched_at or started_at
    run_id = str(uuid4())
    scope = ",".join(sorted(ticker_filter)) if ticker_filter else "all"

    report_count = failed = 0
    seen_tickers = set()
    duplicate_tickers = set()
    conn = sqlite3.connect(db_path)
    try:
        init_db(conn)
        conn.execute(
            """
            INSERT INTO ingest_runs (run_id, started_at, mode, scope, status, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (run_id, started_at, "markdown", scope, "running", None),
        )

        for expected_ticker, folder_sector, filepath in iter_report_files(ticker_filter):
            report_count += 1
            relpath = os.path.relpath(filepath, PROJECT_ROOT)
            try:
                with open(filepath, "r", encoding="utf-8") as fh:
                    content = fh.read()

                metadata = parse_metadata(content, fallback_sector=folder_sector)
                ticker = metadata["ticker"] or expected_ticker
                name = metadata["name"] or os.path.basename(filepath).split("_", 1)[-1].removesuffix(".md")
                if ticker in seen_tickers:
                    duplicate_tickers.add(ticker)
                seen_tickers.add(ticker)

                conn.execute(
                    """
                    INSERT INTO companies
                      (ticker, name, sector, industry, report_path, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(ticker) DO UPDATE SET
                      name=excluded.name,
                      sector=excluded.sector,
                      industry=excluded.industry,
                      report_path=excluded.report_path,
                      updated_at=excluded.updated_at
                    """,
                    (
                        ticker,
                        name,
                        metadata.get("sector"),
                        metadata.get("industry"),
                        relpath,
                        fetched_at,
                    ),
                )

                for period_type in ("annual", "quarterly"):
                    for row in parse_metric_table(content, period_type):
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO financial_metrics
                              (ticker, period_type, period_end, metric, value, unit, source, fetched_at, run_id)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                ticker,
                                row["period_type"],
                                row["period_end"],
                                row["metric"],
                                row["value"],
                                row["unit"],
                                "markdown",
                                fetched_at,
                                run_id,
                            ),
                        )

                valuation = parse_valuation(content, metadata)
                if valuation:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO valuation_snapshots
                          (ticker, fetched_at, valuation_as_of, ttm_period_end, forward_period_end,
                           price, trailing_pe, forward_pe, price_to_sales, price_to_book,
                           ev_to_ebitda, market_cap_million_ntd, enterprise_value_million_ntd,
                           source, run_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            ticker,
                            fetched_at,
                            valuation.get("valuation_as_of"),
                            valuation.get("ttm_period_end"),
                            valuation.get("forward_period_end"),
                            valuation.get("price"),
                            valuation.get("trailing_pe"),
                            valuation.get("forward_pe"),
                            valuation.get("price_to_sales"),
                            valuation.get("price_to_book"),
                            valuation.get("ev_to_ebitda"),
                            valuation.get("market_cap_million_ntd"),
                            valuation.get("enterprise_value_million_ntd"),
                            "markdown",
                            run_id,
                        ),
                    )
            except Exception as exc:
                failed += 1
                print(f"WARN: failed to import {relpath}: {exc}")

        company_count = conn.execute(
            "SELECT COUNT(*) FROM companies"
        ).fetchone()[0]
        metric_count = conn.execute(
            "SELECT COUNT(*) FROM financial_metrics WHERE run_id = ?",
            (run_id,),
        ).fetchone()[0]
        valuation_count = conn.execute(
            "SELECT COUNT(*) FROM valuation_snapshots WHERE run_id = ?",
            (run_id,),
        ).fetchone()[0]
        status = "success" if failed == 0 else "partial"
        notes = (
            f"reports={report_count}, companies={company_count}, "
            f"metrics={metric_count}, valuations={valuation_count}, failed={failed}, "
            f"duplicate_tickers={','.join(sorted(duplicate_tickers)) if duplicate_tickers else 'none'}"
        )
        finished_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        conn.execute(
            """
            UPDATE ingest_runs
            SET finished_at = ?, status = ?, notes = ?
            WHERE run_id = ?
            """,
            (finished_at, status, notes, run_id),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "db_path": db_path,
        "run_id": run_id,
        "status": "success" if failed == 0 else "partial",
        "reports": report_count,
        "companies": company_count,
        "metrics": metric_count,
        "valuations": valuation_count,
        "failed": failed,
        "duplicate_tickers": sorted(duplicate_tickers),
        "fetched_at": fetched_at,
    }


def main():
    setup_stdout()
    parser = argparse.ArgumentParser(
        description="Build SQLite financial snapshots from Markdown reports."
    )
    parser.add_argument(
        "--from-markdown",
        action="store_true",
        help="Import current Pilot_Reports Markdown financial sections.",
    )
    parser.add_argument(
        "--db",
        default=DEFAULT_DB,
        help="SQLite output path. Default: data/financial_snapshots.sqlite",
    )
    parser.add_argument(
        "--ticker",
        nargs="*",
        help="Optional ticker filter, e.g. --ticker 2308 2330",
    )
    parser.add_argument(
        "--fetched-at",
        help="Override snapshot timestamp, ISO format. Default: current UTC time.",
    )
    args = parser.parse_args()

    if not args.from_markdown:
        parser.error("This MVP only supports --from-markdown.")

    ticker_filter = set(args.ticker) if args.ticker else None
    result = import_markdown_reports(
        os.path.abspath(args.db),
        ticker_filter=ticker_filter,
        fetched_at=args.fetched_at,
    )

    print("Financial SQLite baseline created.")
    print(f"DB: {result['db_path']}")
    print(f"Run: {result['run_id']}")
    print(f"Fetched at: {result['fetched_at']}")
    print(
        "Imported: "
        f"{result['reports']} reports, "
        f"{result['companies']} companies, "
        f"{result['metrics']} metric rows, "
        f"{result['valuations']} valuation rows"
    )
    if result["duplicate_tickers"]:
        print("Duplicate tickers collapsed: " + ", ".join(result["duplicate_tickers"]))
    print(f"Status: {result['status']} | Failed: {result['failed']}")


if __name__ == "__main__":
    main()
