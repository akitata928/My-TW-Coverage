#!/usr/bin/env python3
"""Run the bounded 2026 Q2, three-industry MOPS pilot from an external cache.

This runner never downloads or copies raw filings into the repository.  It
consumes parser output from the repo-external cache, emits canonical files to
an external output directory, imports them into an external SQLite database,
and writes a deterministic manifest/quality summary.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE = Path.home() / ".openclaw/data/my-tw-coverage/mops_xbrl/live-2026Q2"
DEFAULT_OUTPUT = Path.home() / ".openclaw/data/my-tw-coverage/live-2026Q2"


def _module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


PARSE = _module("parse_mops_xbrl", ROOT / "scripts/parse_mops_xbrl.py")
EMIT = _module("emit_mops_canonical", ROOT / "scripts/emit_mops_canonical.py")
SQLITE = _module("sqlite_financial", ROOT / "scripts/sqlite_financial.py")
PROBE = _module("probe_mops_xbrl", ROOT / "scripts/probe_mops_xbrl.py")


JOBS = (
    {"ticker": "2330", "company_name": "台灣積體電路製造股份有限公司", "industry_family": "general_industrial", "institution_type": "industrial"},
    {"ticker": "2882", "company_name": "國泰金融控股股份有限公司", "industry_family": "financial_holding", "institution_type": "financial_holding"},
    {"ticker": "2801", "company_name": "彰化商業銀行股份有限公司", "industry_family": "bank", "institution_type": "bank"},
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _coverage(payload: dict[str, Any], industry: str, registry: dict[tuple[str, str], dict[str, str]]) -> dict[str, Any]:
    default = registry[("__default__", "__default__")]
    counts: Counter[str] = Counter()
    qnames: Counter[str] = Counter()
    for fact in payload.get("facts", []):
        local = str(fact.get("local_name") or fact["concept_qname"].rsplit("}", 1)[-1])
        entry = registry.get((industry, local), default)
        counts[entry["mapping_status"]] += 1
        if entry["mapping_status"] == "unknown":
            qnames[str(fact["concept_qname"])] += 1
    return {
        "facts_total": len(payload.get("facts", [])),
        "mapping_status": dict(sorted(counts.items())),
        "unknown_qnames": dict(sorted(qnames.items())),
    }


def run(cache_root: Path, output_root: Path, db_path: Path, registry_path: Path) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    registry = SQLITE.load_mapping_registry(registry_path)
    manifest: dict[str, Any] = {
        "pilot": "mops-2026Q2-C-t164sb01",
        "generated_at": _now(),
        "parser": "arelle-2.45.1",
        "mapping_registry": str(registry_path),
        "jobs": [],
    }
    for job in JOBS:
        ticker = job["ticker"]
        normalized_path = cache_root / f"{ticker}.normalized.json"
        if not normalized_path.exists():
            raise FileNotFoundError(normalized_path)
        payload = json.loads(normalized_path.read_text(encoding="utf-8"))
        raw_path = cache_root / f"{ticker}_2026Q2_C_t164sb01.bin"
        source_url = PROBE.build_url(ticker, 2026, 2, "C", "t164sb01")
        facts = EMIT.canonicalize(
            payload,
            ticker=ticker,
            company_name=job["company_name"],
            report_period="2026Q2",
            statement_type="unknown",
            consolidation_scope="consolidated",
            period_role="unknown",
            accumulation="unknown",
            restatement_status="unknown",
            source_url=source_url,
            retrieved_at=_now(),
        )
        json_path = output_root / "canonical" / f"{ticker}.json"
        csv_path = output_root / "canonical" / f"{ticker}.csv"
        digest = EMIT.write_outputs(facts, json_path, csv_path)
        rows = SQLITE.validate_json_csv(json_path, csv_path)
        imported = SQLITE.import_canonical(
            db_path, json_path, csv_path=csv_path,
            industry_family=job["industry_family"],
            institution_type=job["institution_type"],
            mapping_version="mops-tifrs-2026-09-pilot-1",
            mapping_registry=registry_path,
        )
        manifest["jobs"].append({
            **job,
            "report_period": "2026Q2",
            "report_id": "C",
            "function_name": "t164sb01",
            "raw_sha256": _sha(raw_path) if raw_path.exists() else None,
            "normalized_sha256": _sha(normalized_path),
            "canonical_json": str(json_path),
            "canonical_csv": str(csv_path),
            "facts": len(rows),
            "inserted": imported,
            "canonical_json_sha256": digest,
            "diagnostic_count": payload.get("metadata", {}).get("diagnostic_count"),
            "mapping_coverage": _coverage(payload, job["industry_family"], registry),
        })
    manifest["integrity"] = SQLITE.integrity_report(db_path)
    manifest["quality"] = SQLITE.quality_report(db_path)
    manifest_path = output_root / "pilot-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--db", type=Path)
    parser.add_argument("--mapping-registry", type=Path, default=ROOT / "config/mops_financial_mapping.json")
    args = parser.parse_args()
    db = args.db or args.output_root / "financial.sqlite"
    print(json.dumps(run(args.cache_root, args.output_root, db, args.mapping_registry), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
