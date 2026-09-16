#!/usr/bin/env python3
"""Stage canonical files and run a deterministic, Perch-independent contract check.

This is deliberately not a Perch implementation.  It proves that the JSON and
CSV exports carry the same machine-readable facts and records hashes for a
later Perch Desktop/CLI/Web upload test.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from decimal import Decimal
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = {"concept_qname", "value", "unit", "context_ref", "source_url", "source_input_sha256"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_signature(fact: dict[str, Any]) -> tuple[str, str, str, str]:
    return (str(fact.get("concept_qname", "")), str(fact.get("value", "")), str(fact.get("unit", "")), str(fact.get("context_ref", "")))


def _csv_signature(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (row.get("concept_qname", ""), row.get("value", ""), row.get("unit", ""), row.get("context_ref", ""))


def deterministic_summary(facts: list[dict[str, Any]]) -> dict[str, Any]:
    sums: dict[str, Decimal] = {}
    for fact in facts:
        value = fact.get("value")
        unit = str(fact.get("unit") or "")
        if value in (None, ""):
            continue
        sums[unit] = sums.get(unit, Decimal("0")) + Decimal(str(value))
    return {
        "fact_count": len(facts),
        "numeric_value_count": sum(1 for fact in facts if fact.get("value") not in (None, "")),
        "sum_by_unit": {unit: format(value, "f") for unit, value in sorted(sums.items())},
    }


def stage_and_check(json_input: Path, csv_input: Path, output_dir: Path) -> dict[str, Any]:
    payload = json.loads(json_input.read_text(encoding="utf-8"))
    facts = payload if isinstance(payload, list) else payload.get("facts", [])
    if not facts:
        raise ValueError("JSON input contains no facts")
    missing = REQUIRED_FIELDS - set(facts[0])
    if missing:
        raise ValueError(f"JSON input missing required fields: {sorted(missing)}")
    with csv_input.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError("CSV input contains no rows")
    missing_csv = REQUIRED_FIELDS - set(rows[0])
    if missing_csv:
        raise ValueError(f"CSV input missing required fields: {sorted(missing_csv)}")
    if [_json_signature(fact) for fact in facts] != [_csv_signature(row) for row in rows]:
        raise ValueError("JSON and CSV facts differ in concept/value/unit/context order")
    output_dir.mkdir(parents=True, exist_ok=True)
    staged_json = output_dir / json_input.name
    staged_csv = output_dir / csv_input.name
    shutil.copyfile(json_input, staged_json)
    shutil.copyfile(csv_input, staged_csv)
    summary = deterministic_summary(facts)
    manifest = {
        "runtime": "perch_runtime_not_available",
        "json_filename": staged_json.name,
        "csv_filename": staged_csv.name,
        "json_sha256": sha256(staged_json),
        "csv_sha256": sha256(staged_csv),
        "input_sha256": str(payload.get("metadata", {}).get("input_sha256", "")) if isinstance(payload, dict) else "",
        "contract_check": "passed",
        "deterministic_calculation": summary,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-input", type=Path, required=True)
    parser.add_argument("--csv-input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(stage_and_check(args.json_input, args.csv_input, args.output_dir), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
