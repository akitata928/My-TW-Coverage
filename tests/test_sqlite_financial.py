import csv
import importlib.util
import json
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("sqlite_financial", ROOT / "scripts/sqlite_financial.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


FIXTURE = ROOT / "tests/fixtures/mops_xbrl/phase3a_multi_industry.sample.json"


def _write_single(tmp_path: Path, ticker: str) -> Path:
    rows = [row for row in json.loads(FIXTURE.read_text(encoding="utf-8")) if row["ticker"] == ticker]
    path = tmp_path / f"{ticker}.json"
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return path


def _write_csv(tmp_path: Path, json_path: Path) -> Path:
    rows = json.loads(json_path.read_text(encoding="utf-8"))
    path = tmp_path / f"{rows[0]['ticker']}.csv"
    fields = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            encoded = {
                key: json.dumps(value, ensure_ascii=False, separators=(",", ":"))
                if isinstance(value, (dict, list))
                else "" if value is None else value
                for key, value in row.items()
            }
            writer.writerow(encoded)
    return path


def test_migration_is_idempotent_and_has_required_views(tmp_path):
    db_path = tmp_path / "financial.sqlite"
    MODULE.migrate(db_path)
    MODULE.migrate(db_path)
    with sqlite3.connect(db_path) as db:
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        views = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='view'")}
        assert {"issuers", "raw_documents", "xbrl_facts", "statement_facts", "concept_mappings", "data_quality_issues"} <= tables
        assert {"v_general_industrial_financials", "v_financial_holding_financials", "v_bank_financials"} <= views
        assert db.execute("SELECT count(*) FROM schema_migrations").fetchone()[0] == 1


def test_three_industry_facts_coexist_and_are_idempotent(tmp_path):
    db_path = tmp_path / "financial.sqlite"
    specs = (("2330", "general_industrial", "industrial"), ("2882", "financial_holding", "holding"), ("2801", "bank", "bank"))
    for ticker, industry, institution in specs:
        path = _write_single(tmp_path, ticker)
        assert MODULE.import_canonical(db_path, path, industry_family=industry, institution_type=institution) == 1
        assert MODULE.import_canonical(db_path, path, industry_family=industry, institution_type=institution) == 1
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT count(*) FROM xbrl_facts").fetchone()[0] == 3
        assert db.execute("SELECT count(*) FROM v_general_industrial_financials").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM v_financial_holding_financials").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM v_bank_financials").fetchone()[0] == 1
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert db.execute("SELECT count(*) FROM pragma_foreign_key_check").fetchone()[0] == 0


def test_unknown_mapping_is_quality_issue_not_zero(tmp_path):
    db_path = tmp_path / "financial.sqlite"
    path = _write_single(tmp_path, "2882")
    MODULE.import_canonical(db_path, path, industry_family="financial_holding", institution_type="holding")
    with sqlite3.connect(db_path) as db:
        row = db.execute("SELECT mapping_status, normalized_value FROM v_financial_holding_financials").fetchone()
        assert row == ("unknown", "200")
        assert db.execute("SELECT count(*) FROM data_quality_issues WHERE issue_type='mapping_pending'").fetchone()[0] == 1


def test_json_csv_pair_is_required_to_match(tmp_path):
    db_path = tmp_path / "financial.sqlite"
    json_path = _write_single(tmp_path, "2330")
    csv_path = _write_csv(tmp_path, json_path)
    assert MODULE.import_canonical(db_path, json_path, csv_path=csv_path, industry_family="general_industrial") == 1
    csv_path.write_text(csv_path.read_text(encoding="utf-8").replace(",100,100,", ",999,999,"), encoding="utf-8")
    try:
        MODULE.import_canonical(db_path, json_path, csv_path=csv_path, industry_family="general_industrial")
    except ValueError as exc:
        assert "JSON and CSV differ" in str(exc)
    else:
        raise AssertionError("mismatched JSON/CSV pair was accepted")


def test_query_filters_decimal_and_quality_report(tmp_path):
    db_path = tmp_path / "financial.sqlite"
    for ticker, industry, institution in (("2330", "general_industrial", "industrial"), ("2882", "financial_holding", "holding")):
        json_path = _write_single(tmp_path, ticker)
        csv_path = _write_csv(tmp_path, json_path)
        MODULE.import_canonical(db_path, json_path, csv_path=csv_path, industry_family=industry, institution_type=institution)
    rows = MODULE.query_financial_facts(db_path, industry_family="general_industrial", report_period="2026Q2", unit="TWD")
    assert len(rows) == 1
    assert rows[0]["ticker"] == "2330"
    assert MODULE.analyze_database(db_path, industry_family="financial_holding")["sum_by_unit"] == {"TWD": "200"}
    report = MODULE.quality_report(db_path)
    assert report["issues_by_type"] == {"mapping_pending": 2}
    assert report["mapping_status"] == {"unknown": 2}
