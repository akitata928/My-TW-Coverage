import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("run_perch_compatibility", ROOT / "scripts/run_perch_compatibility.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class PerchCompatibilityHarnessTests(unittest.TestCase):
    def test_isolates_files_and_matches_json_csv(self):
        json_input = ROOT / "tests/fixtures/mops_xbrl/2330_2026Q2_C_canonical.sample.json"
        csv_input = ROOT / "tests/fixtures/mops_xbrl/2330_2026Q2_C_canonical.sample.csv"
        with tempfile.TemporaryDirectory() as directory:
            manifest = MODULE.stage_and_check(json_input, csv_input, Path(directory))
            self.assertEqual(manifest["contract_check"], "passed")
            self.assertEqual(manifest["deterministic_calculation"]["fact_count"], 1)
            self.assertTrue((Path(directory) / "manifest.json").exists())
            self.assertTrue((Path(directory) / json_input.name).exists())
            self.assertTrue((Path(directory) / csv_input.name).exists())

    def test_calculation_is_deterministic(self):
        facts = [{"value": "10", "unit": "TWD"}, {"value": "2.5", "unit": "TWD"}]
        self.assertEqual(MODULE.deterministic_summary(facts), MODULE.deterministic_summary(facts))


if __name__ == "__main__":
    unittest.main()
