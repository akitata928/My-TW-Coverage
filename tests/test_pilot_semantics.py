import importlib.util
import sys
import unittest
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("run_financial_pilot", ROOT / "scripts/run_financial_pilot.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class PilotSemanticTests(unittest.TestCase):
    def test_statement_classifier_only_uses_exact_local_name_anchors(self):
        @dataclass(frozen=True)
        class Fact:
            concept_qname: str
            statement_type: str = "unknown"

        facts = MODULE._classify_statements(
            [Fact("{urn:test}Assets"), Fact("{urn:test}AssetsAdjusted"), Fact("{urn:test}InterestExpense")],
            ROOT / "config/mops_financial_mapping.json",
        )
        self.assertEqual([fact.statement_type for fact in facts], ["balance_sheet", "unknown", "income_statement"])


if __name__ == "__main__":
    unittest.main()
