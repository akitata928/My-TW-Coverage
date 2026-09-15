import csv
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("emit_mops_canonical", ROOT / "scripts/emit_mops_canonical.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class CanonicalSchemaTests(unittest.TestCase):
    def setUp(self):
        self.payload = json.loads((ROOT / "tests/fixtures/mops_xbrl/2330_2026Q2_C_normalized.sample.json").read_text())

    def kwargs(self):
        return dict(ticker="2330", company_name="台積電", report_period="2026Q2", statement_type="balance_sheet", consolidation_scope="consolidated", period_role="current", accumulation="instant", restatement_status="as_filed", source_url="https://example.invalid/mops", retrieved_at="2026-09-15T00:00:00+00:00")

    def test_required_fields_and_explicit_provenance(self):
        facts = MODULE.canonicalize(self.payload, **self.kwargs())
        self.assertEqual(len(facts), 3)
        self.assertEqual(facts[0].ticker, "2330")
        self.assertEqual(facts[0].statement_type, "balance_sheet")
        self.assertEqual(facts[0].source_input_sha256, self.payload["metadata"]["input_sha256"])
        self.assertEqual(facts[0].value_status, "present")

    def test_json_and_csv_are_both_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            facts = MODULE.canonicalize(self.payload, **self.kwargs())
            digest_a = MODULE.write_outputs(facts, root / "a.json", root / "a.csv")
            digest_b = MODULE.write_outputs(facts, root / "b.json", root / "b.csv")
            self.assertEqual(digest_a, digest_b)
            self.assertEqual((root / "a.json").read_bytes(), (root / "b.json").read_bytes())
            with (root / "a.csv").open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 3)
            self.assertIn("source_url", rows[0])
            self.assertIn("dimensions", rows[0])

    def test_unknown_policy_does_not_invent_semantics(self):
        kwargs = self.kwargs()
        kwargs.update(period_role="unknown", accumulation="unknown", restatement_status="unknown")
        facts = MODULE.canonicalize(self.payload, **kwargs)
        self.assertTrue(all(fact.period_role == "unknown" for fact in facts))

    def test_invalid_statement_type_rejected(self):
        kwargs = self.kwargs()
        kwargs["statement_type"] = "other"
        with self.assertRaises(ValueError):
            MODULE.canonicalize(self.payload, **kwargs)


if __name__ == "__main__":
    unittest.main()
