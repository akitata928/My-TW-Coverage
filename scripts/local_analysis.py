#!/usr/bin/env python3
"""Perch-independent local import, query, calculation, and provenance checks."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_facts(json_path: Path, csv_path: Path) -> list[dict[str, Any]]:
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    json_facts = payload if isinstance(payload, list) else payload.get("facts", [])
    with csv_path.open(encoding="utf-8", newline="") as handle:
        csv_facts = list(csv.DictReader(handle))
    if not json_facts or not csv_facts:
        raise ValueError("JSON and CSV must both contain facts")
    if len(json_facts) != len(csv_facts):
        raise ValueError("JSON and CSV fact counts differ")
    for index, (json_fact, csv_fact) in enumerate(zip(json_facts, csv_facts, strict=True)):
        for field in ("concept_qname", "value", "unit", "context_ref"):
            if str(json_fact.get(field, "")) != csv_fact.get(field, ""):
                raise ValueError(f"JSON and CSV differ at row {index}, field {field}")
    return json_facts


def analyze(json_path: Path, csv_path: Path, concept_qname: str | None = None) -> dict[str, Any]:
    facts = load_facts(json_path, csv_path)
    selected = [fact for fact in facts if concept_qname is None or fact.get("concept_qname") == concept_qname]
    sums: dict[str, Decimal] = {}
    for fact in selected:
        if fact.get("value") not in (None, ""):
            unit = str(fact.get("unit") or "")
            sums[unit] = sums.get(unit, Decimal("0")) + Decimal(str(fact["value"]))
    provenance = sorted({(str(f.get("source_url", "")), str(f.get("source_input_sha256", ""))) for f in selected})
    return {
        "json_sha256": _sha256(json_path),
        "csv_sha256": _sha256(csv_path),
        "fact_count": len(selected),
        "sum_by_unit": {unit: format(total, "f") for unit, total in sorted(sums.items())},
        "provenance": [{"source_url": url, "source_input_sha256": digest} for url, digest in provenance],
        "runtime": "local_python",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-input", type=Path, required=True)
    parser.add_argument("--csv-input", type=Path, required=True)
    parser.add_argument("--concept-qname")
    args = parser.parse_args()
    print(json.dumps(analyze(args.json_input, args.csv_input, args.concept_qname), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
