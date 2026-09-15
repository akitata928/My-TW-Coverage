import importlib.util
import sys
import unittest
import json
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("parse_mops_xbrl", ROOT / "scripts/parse_mops_xbrl.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ParseHelpersTests(unittest.TestCase):
    def test_negative_decimals_are_explicitly_scaled(self):
        self.assertEqual(MODULE.normalize_decimal("12.5", "-3"), Decimal("12500"))
        self.assertEqual(MODULE.normalize_decimal("12.5", "INF"), Decimal("12.5"))

    def test_qname_keeps_namespace(self):
        self.assertEqual(
            MODULE.qualified_name("http://example.test/tifrs", "Revenue"),
            ("{http://example.test/tifrs}Revenue", "http://example.test/tifrs", "Revenue"),
        )

    def test_decimal_string_is_stable(self):
        self.assertEqual(MODULE.decimal_string(Decimal("100.5000")), "100.5")

    def test_sanitized_golden_sample_preserves_qualified_names_and_units(self):
        path = ROOT / "tests/fixtures/mops_xbrl/2330_2026Q2_C_normalized.sample.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["metadata"]["parser_version"], "2.45.1")
        self.assertTrue(all(f["concept_qname"].startswith("{") for f in payload["facts"]))
        self.assertTrue(any(f["dimensions"] for f in payload["facts"]))
        self.assertTrue(any(f["raw_unit"].endswith("shares") for f in payload["facts"]))
        self.assertTrue(all(f["label_zh_tw"] is None for f in payload["facts"]))


if __name__ == "__main__":
    unittest.main()
