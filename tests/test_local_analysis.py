import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("local_analysis", ROOT / "scripts/local_analysis.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


JSON = ROOT / "tests/fixtures/mops_xbrl/2330_2026Q2_C_canonical.sample.json"
CSV = ROOT / "tests/fixtures/mops_xbrl/2330_2026Q2_C_canonical.sample.csv"


def test_local_import_query_calculation_and_provenance():
    result = MODULE.analyze(JSON, CSV)
    assert result["runtime"] == "local_python"
    assert result["fact_count"] == 1
    assert result["sum_by_unit"]
    assert result["provenance"][0]["source_input_sha256"]


def test_query_can_select_one_concept():
    facts = MODULE.load_facts(JSON, CSV)
    result = MODULE.analyze(JSON, CSV, facts[0]["concept_qname"])
    assert result["fact_count"] == 1


def test_query_unknown_concept_is_empty():
    result = MODULE.analyze(JSON, CSV, "unknown:concept")
    assert result["fact_count"] == 0
    assert result["sum_by_unit"] == {}


def test_json_csv_mismatch_is_rejected(tmp_path):
    bad_csv = tmp_path / "bad.csv"
    bad_csv.write_text(CSV.read_text(encoding="utf-8").replace("5160539000000", "1"), encoding="utf-8")
    with pytest.raises(ValueError, match="differ"):
        MODULE.load_facts(JSON, bad_csv)
