#!/usr/bin/env python3
"""Emit the Phase 3 canonical JSON/CSV contract from normalized facts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


STATEMENT_TYPES = ("balance_sheet", "income_statement", "cash_flow_statement", "unknown")
SCOPE_TYPES = ("consolidated", "individual")
PERIOD_ROLES = ("current", "comparative", "unknown")
RESTATEMENT_STATUSES = ("as_filed", "restated", "unknown")
ACCUMULATION_TYPES = ("instant", "single_period", "year_to_date", "unknown")


@dataclass(frozen=True)
class CanonicalFact:
    ticker: str
    company_name: str
    report_period: str
    statement_type: str
    consolidation_scope: str
    period_role: str
    accumulation: str
    restatement_status: str
    concept_qname: str
    label_zh_tw: str | None
    label_en: str | None
    value: str | None
    raw_value: str | None
    unit: str | None
    raw_unit: str | None
    decimals: str | None
    context_ref: str
    entity_scheme: str | None
    entity_identifier: str | None
    period_start: str | None
    period_end: str | None
    period_instant: str | None
    dimensions: tuple[tuple[str, str], ...] | list[list[str]]
    value_status: str
    missing_value_reason: str | None
    source_url: str
    retrieved_at: str
    source_input_sha256: str


CSV_FIELDS = tuple(CanonicalFact.__dataclass_fields__.keys())


def _require_choice(name: str, value: str, choices: tuple[str, ...]) -> str:
    if value not in choices:
        raise ValueError(f"{name} must be one of: {', '.join(choices)}")
    return value


def _json_dimensions(value: Any) -> list[list[str]]:
    return [[str(pair[0]), str(pair[1])] for pair in (value or [])]


def canonicalize(
    payload: dict[str, Any],
    *,
    ticker: str,
    company_name: str,
    report_period: str,
    statement_type: str,
    consolidation_scope: str,
    period_role: str,
    accumulation: str,
    restatement_status: str,
    source_url: str,
    retrieved_at: str,
) -> list[CanonicalFact]:
    statement_type = _require_choice("statement_type", statement_type, STATEMENT_TYPES)
    consolidation_scope = _require_choice("consolidation_scope", consolidation_scope, SCOPE_TYPES)
    period_role = _require_choice("period_role", period_role, PERIOD_ROLES)
    accumulation = _require_choice("accumulation", accumulation, ACCUMULATION_TYPES)
    restatement_status = _require_choice("restatement_status", restatement_status, RESTATEMENT_STATUSES)
    source_hash = str(payload.get("metadata", {}).get("input_sha256", ""))
    if not source_hash:
        raise ValueError("normalized input metadata.input_sha256 is required")
    result: list[CanonicalFact] = []
    for fact in payload.get("facts", []):
        raw_value = fact.get("raw_value")
        normalized_value = fact.get("normalized_value")
        present = normalized_value is not None and raw_value is not None
        result.append(
            CanonicalFact(
                ticker=ticker,
                company_name=company_name,
                report_period=report_period,
                statement_type=statement_type,
                consolidation_scope=consolidation_scope,
                period_role=period_role,
                accumulation=accumulation,
                restatement_status=restatement_status,
                concept_qname=str(fact["concept_qname"]),
                label_zh_tw=fact.get("label_zh_tw"),
                label_en=fact.get("label_en"),
                value=str(normalized_value) if present else None,
                raw_value=str(raw_value) if present else None,
                unit=fact.get("normalized_unit"),
                raw_unit=fact.get("raw_unit"),
                decimals=fact.get("raw_decimals"),
                context_ref=str(fact["context_ref"]),
                entity_scheme=fact.get("entity_scheme"),
                entity_identifier=fact.get("entity_identifier"),
                period_start=fact.get("period_start"),
                period_end=fact.get("period_end"),
                period_instant=fact.get("period_instant"),
                dimensions=_json_dimensions(fact.get("dimensions")),
                value_status="present" if present else "missing",
                missing_value_reason=None if present else "source_value_unavailable",
                source_url=source_url,
                retrieved_at=retrieved_at,
                source_input_sha256=source_hash,
            )
        )
    return sorted(result, key=lambda fact: (fact.concept_qname, fact.context_ref, fact.unit or "", fact.raw_value or ""))


def _row(fact: CanonicalFact) -> dict[str, str]:
    data = asdict(fact)
    data["dimensions"] = json.dumps(data["dimensions"], ensure_ascii=False, separators=(",", ":"))
    return {key: "" if value is None else str(value) for key, value in data.items()}


def write_outputs(facts: list[CanonicalFact], json_path: Path, csv_path: Path) -> str:
    rows = [_row(fact) for fact in facts]
    json_text = json.dumps([asdict(fact) for fact in facts], ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json_text, encoding="utf-8")
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return hashlib.sha256(json_text.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--csv-output", type=Path, required=True)
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--company-name", required=True)
    parser.add_argument("--report-period", required=True)
    parser.add_argument("--statement-type", choices=STATEMENT_TYPES, required=True)
    parser.add_argument("--consolidation-scope", choices=SCOPE_TYPES, required=True)
    parser.add_argument("--period-role", choices=PERIOD_ROLES, default="unknown")
    parser.add_argument("--accumulation", choices=ACCUMULATION_TYPES, default="unknown")
    parser.add_argument("--restatement-status", choices=RESTATEMENT_STATUSES, default="unknown")
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--retrieved-at", required=True)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    facts = canonicalize(payload, ticker=args.ticker, company_name=args.company_name, report_period=args.report_period, statement_type=args.statement_type, consolidation_scope=args.consolidation_scope, period_role=args.period_role, accumulation=args.accumulation, restatement_status=args.restatement_status, source_url=args.source_url, retrieved_at=args.retrieved_at)
    digest = write_outputs(facts, args.json_output, args.csv_output)
    print(json.dumps({"facts": len(facts), "json_sha256": digest}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
