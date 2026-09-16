import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("sqlite_financial", ROOT / "scripts/sqlite_financial.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class FinancialMappingTests(unittest.TestCase):
    def test_registry_is_versioned_and_exact_name_only(self):
        path = ROOT / "config/mops_financial_mapping.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["registry_version"], "mops-tifrs-2026-09-pilot-2")
        registry = MODULE.load_mapping_registry(path)
        self.assertEqual(registry[("bank", "DepositsFromCustomers")]["mapping_status"], "provisional")
        self.assertEqual(registry[("__default__", "__default__")]["mapping_status"], "unknown")

    def test_braced_qname_keeps_namespace_and_local_name(self):
        self.assertEqual(MODULE._namespace("{urn:test}Assets"), ("urn:test", "Assets"))

    def test_second_round_fixture_keeps_specialized_semantics_unknown(self):
        path = ROOT / "tests/fixtures/mops_xbrl/second_round_industry_contract.sample.json"
        rows = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual({row["ticker"] for row in rows}, {"INS001", "SEC001"})
        self.assertTrue(all(row["statement_type"] == "unknown" for row in rows))


if __name__ == "__main__":
    unittest.main()
