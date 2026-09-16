#!/usr/bin/env python3
"""SQLite migration and local semantic importer for Phase 3A."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "migrations/001_financial_schema.sql"
INDUSTRIES = {"general_industrial", "financial_holding", "bank", "insurance", "securities", "unknown"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def migrate(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript(MIGRATION.read_text(encoding="utf-8"))
        db.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (1, utc_now()),
        )
        db.commit()


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _load_json(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload if isinstance(payload, list) else payload.get("facts", [])
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{path} contains no canonical facts")
    return rows


def _namespace(qname: str) -> tuple[str, str]:
    if "#" in qname:
        namespace, local = qname.rsplit("#", 1)
    elif ":" in qname:
        namespace, local = qname.rsplit(":", 1)
    else:
        namespace, local = "unknown", qname
    return namespace, local


def _json(value: Any) -> str:
    return json.dumps(value if value is not None else [], ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _get_or_insert(db: sqlite3.Connection, sql: str, params: tuple[Any, ...], select_sql: str, select_params: tuple[Any, ...]) -> int:
    db.execute(sql, params)
    row = db.execute(select_sql, select_params).fetchone()
    assert row is not None
    return int(row[0])


def import_canonical(
    db_path: Path,
    json_path: Path,
    *,
    industry_family: str,
    institution_type: str | None = None,
    parent_ticker: str | None = None,
    mapping_version: str = "mvp-2026-09",
) -> int:
    if industry_family not in INDUSTRIES:
        raise ValueError(f"industry_family must be one of: {', '.join(sorted(INDUSTRIES))}")
    rows = _load_json(json_path)
    ticker = str(rows[0]["ticker"])
    company_name = str(rows[0]["company_name"])
    if any(str(row.get("ticker")) != ticker for row in rows):
        raise ValueError("one import job must contain one ticker")
    digest = str(rows[0].get("source_input_sha256") or _sha256(json_path.read_text(encoding="utf-8")))
    report_period = str(rows[0].get("report_period") or "unknown")
    scope = str(rows[0].get("consolidation_scope") or "unknown")
    retrieved_at = str(rows[0].get("retrieved_at") or utc_now())
    statement_types = {str(row.get("statement_type") or "unknown") for row in rows}

    migrate(db_path)
    inserted = 0
    with sqlite3.connect(db_path) as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute(
            """INSERT INTO issuers(ticker, company_name, industry_family, institution_type, parent_ticker,
               classification_source, effective_from) VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(ticker) DO UPDATE SET company_name=excluded.company_name,
               industry_family=excluded.industry_family, institution_type=excluded.institution_type,
               parent_ticker=excluded.parent_ticker""",
            (ticker, company_name, industry_family, institution_type, parent_ticker, "pilot_fixture", "2026-01-01"),
        )
        db.execute(
            """INSERT OR IGNORE INTO raw_documents
               (ticker, report_period, report_year, report_quarter, consolidation_scope, source_url,
                retrieved_at, raw_sha256, taxonomy_version, parser_version, metadata_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (ticker, report_period, None, None, scope, str(rows[0].get("source_url") or "fixture://canonical"),
             retrieved_at, digest, "unknown", "arelle-2.45.1", json.dumps({"statements": sorted(statement_types)})),
        )
        raw_id = db.execute(
            "SELECT raw_document_id FROM raw_documents WHERE ticker=? AND report_period=? AND consolidation_scope=? AND raw_sha256=?",
            (ticker, report_period, scope, digest),
        ).fetchone()[0]
        for row in rows:
            qname = str(row["concept_qname"])
            namespace, local_name = _namespace(qname)
            taxonomy_version = "unknown"
            db.execute(
                """INSERT OR IGNORE INTO taxonomy_concepts
                   (namespace, concept_qname, local_name, label_zh_tw, label_en, taxonomy_version)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (namespace, qname, local_name, row.get("label_zh_tw"), row.get("label_en"), taxonomy_version),
            )
            concept_id = db.execute(
                "SELECT concept_id FROM taxonomy_concepts WHERE concept_qname=? AND taxonomy_version=?",
                (qname, taxonomy_version),
            ).fetchone()[0]
            context_ref = str(row.get("context_ref") or "unknown")
            period_kind = "instant" if row.get("period_instant") else "duration"
            db.execute(
                """INSERT OR IGNORE INTO xbrl_contexts
                   (raw_document_id, context_ref, entity_scheme, entity_identifier, period_kind,
                    period_start, period_end, period_instant, period_role, dimensions_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (raw_id, context_ref, row.get("entity_scheme"), row.get("entity_identifier"), period_kind,
                 row.get("period_start"), row.get("period_end"), row.get("period_instant"),
                 str(row.get("period_role") or "unknown"), _json(row.get("dimensions"))),
            )
            context_id = db.execute(
                "SELECT context_id FROM xbrl_contexts WHERE raw_document_id=? AND context_ref=?",
                (raw_id, context_ref),
            ).fetchone()[0]
            unit = row.get("unit")
            unit_id = None
            if unit:
                unit_ref = str(unit)
                db.execute(
                    "INSERT OR IGNORE INTO xbrl_units(raw_document_id, unit_ref, measure, unit_json) VALUES (?, ?, ?, ?)",
                    (raw_id, unit_ref, unit_ref, json.dumps({"unit": unit_ref})),
                )
                unit_id = db.execute(
                    "SELECT unit_id FROM xbrl_units WHERE raw_document_id=? AND unit_ref=?", (raw_id, unit_ref)
                ).fetchone()[0]
            fact_key = _sha256(json.dumps({"qname": qname, "context": context_ref, "value": row.get("value"), "unit": unit}, sort_keys=True))
            db.execute(
                """INSERT OR IGNORE INTO xbrl_facts
                   (raw_document_id, concept_id, context_id, unit_id, raw_value, normalized_value, raw_unit,
                    normalized_unit, decimals, value_status, missing_value_reason, dimensions_json, fact_sha256)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (raw_id, concept_id, context_id, unit_id, row.get("raw_value"), row.get("value"), row.get("raw_unit"),
                 row.get("unit"), row.get("decimals"), str(row.get("value_status") or "missing"),
                 row.get("missing_value_reason"), _json(row.get("dimensions")), fact_key),
            )
            fact_id = db.execute(
                "SELECT fact_id FROM xbrl_facts WHERE raw_document_id=? AND fact_sha256=?", (raw_id, fact_key)
            ).fetchone()[0]
            canonical = str(row.get("label_en") or local_name)
            db.execute(
                """INSERT OR IGNORE INTO concept_mappings
                   (source_qname, canonical_concept, industry_family, taxonomy_version, mapping_version,
                    confidence, mapping_status, notes) VALUES (?, ?, ?, ?, ?, 'unknown', 'unknown', ?)""",
                (qname, canonical, industry_family, taxonomy_version, mapping_version, "fixture mapping pending verification"),
            )
            mapping_id = db.execute(
                """SELECT concept_mapping_id FROM concept_mappings
                   WHERE source_qname=? AND industry_family=? AND taxonomy_version=? AND mapping_version=?""",
                (qname, industry_family, taxonomy_version, mapping_version),
            ).fetchone()[0]
            db.execute(
                """INSERT OR IGNORE INTO statement_facts
                   (fact_id, ticker, statement_type, industry_family, institution_type, consolidation_scope,
                    period_role, accumulation, restatement_status, concept_mapping_id, canonical_concept, mapping_status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (fact_id, ticker, str(row.get("statement_type") or "unknown"), industry_family, institution_type,
                 scope, str(row.get("period_role") or "unknown"), str(row.get("accumulation") or "unknown"),
                 str(row.get("restatement_status") or "unknown"), mapping_id, canonical, "unknown"),
            )
            sf_id = db.execute("SELECT statement_fact_id FROM statement_facts WHERE fact_id=?", (fact_id,)).fetchone()[0]
            if str(row.get("value_status") or "missing") == "missing":
                db.execute(
                    """INSERT OR IGNORE INTO data_quality_issues
                       (fact_id, statement_fact_id, issue_type, severity, message, detected_at)
                       VALUES (?, ?, 'missing_value', 'warning', ?, ?)""",
                    (fact_id, sf_id, str(row.get("missing_value_reason") or "source_value_unavailable"), utc_now()),
                )
            db.execute(
                """INSERT OR IGNORE INTO data_quality_issues
                   (fact_id, statement_fact_id, issue_type, severity, message, detected_at)
                   VALUES (?, ?, 'mapping_pending', 'warning', 'concept mapping requires industry review', ?)""",
                (fact_id, sf_id, utc_now()),
            )
            inserted += 1
        db.commit()
    return inserted


def integrity_report(db_path: Path) -> dict[str, Any]:
    with sqlite3.connect(db_path) as db:
        return {
            "integrity": db.execute("PRAGMA integrity_check").fetchone()[0],
            "foreign_keys": db.execute("PRAGMA foreign_key_check").fetchall(),
            "schema_version": db.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0],
            "tables": db.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchone()[0],
            "view_counts": {
                name: db.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
                for name in ("v_general_industrial_financials", "v_financial_holding_financials", "v_bank_financials")
            },
        }


def query_financial_facts(
    db_path: Path,
    *,
    industry_family: str | None = None,
    ticker: str | None = None,
    statement_type: str | None = None,
    canonical_concept: str | None = None,
) -> list[dict[str, Any]]:
    """Return deterministic, provenance-preserving rows from the semantic views."""
    if industry_family is not None and industry_family not in INDUSTRIES:
        raise ValueError(f"unknown industry_family: {industry_family}")
    view = {
        None: "v_financial_facts",
        "general_industrial": "v_general_industrial_financials",
        "financial_holding": "v_financial_holding_financials",
        "bank": "v_bank_financials",
        "insurance": "v_insurance_financials",
        "securities": "v_securities_financials",
        "unknown": "v_financial_facts",
    }[industry_family]
    clauses: list[str] = []
    values: list[str] = []
    for column, value in (("ticker", ticker), ("statement_type", statement_type), ("canonical_concept", canonical_concept)):
        if value is not None:
            clauses.append(f"{column} = ?")
            values.append(value)
    sql = f"SELECT * FROM {view}" + (" WHERE " + " AND ".join(clauses) if clauses else "") + " ORDER BY ticker, statement_type, concept_qname, fact_sha256"
    with sqlite3.connect(db_path) as db:
        db.row_factory = sqlite3.Row
        return [dict(row) for row in db.execute(sql, values).fetchall()]


def analyze_database(db_path: Path, **filters: str | None) -> dict[str, Any]:
    """Perform a Decimal sum over SQLite semantic facts with provenance."""
    from decimal import Decimal

    rows = query_financial_facts(db_path, **filters)
    totals: dict[str, Decimal] = {}
    for row in rows:
        if row["normalized_value"] not in (None, ""):
            unit = str(row["normalized_unit"] or "")
            totals[unit] = totals.get(unit, Decimal("0")) + Decimal(str(row["normalized_value"]))
    return {
        "fact_count": len(rows),
        "sum_by_unit": {unit: format(value, "f") for unit, value in sorted(totals.items())},
        "provenance": sorted({(row["source_url"], row["raw_sha256"]) for row in rows}),
        "runtime": "local_python_sqlite",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    migrate_parser = sub.add_parser("migrate")
    migrate_parser.add_argument("db", type=Path)
    import_parser = sub.add_parser("import-canonical")
    import_parser.add_argument("db", type=Path)
    import_parser.add_argument("json_input", type=Path)
    import_parser.add_argument("--industry-family", required=True, choices=sorted(INDUSTRIES))
    import_parser.add_argument("--institution-type")
    import_parser.add_argument("--parent-ticker")
    import_parser.add_argument("--mapping-version", default="mvp-2026-09")
    report_parser = sub.add_parser("integrity")
    report_parser.add_argument("db", type=Path)
    query_parser = sub.add_parser("query")
    query_parser.add_argument("db", type=Path)
    query_parser.add_argument("--industry-family", choices=sorted(INDUSTRIES))
    query_parser.add_argument("--ticker")
    query_parser.add_argument("--statement-type")
    query_parser.add_argument("--canonical-concept")
    args = parser.parse_args()
    if args.command == "migrate":
        migrate(args.db)
        return 0
    if args.command == "import-canonical":
        print(json.dumps({"inserted": import_canonical(args.db, args.json_input, industry_family=args.industry_family, institution_type=args.institution_type, parent_ticker=args.parent_ticker, mapping_version=args.mapping_version)}, ensure_ascii=False))
        return 0
    if args.command == "integrity":
        print(json.dumps(integrity_report(args.db), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(analyze_database(args.db, industry_family=args.industry_family, ticker=args.ticker, statement_type=args.statement_type, canonical_concept=args.canonical_concept), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
