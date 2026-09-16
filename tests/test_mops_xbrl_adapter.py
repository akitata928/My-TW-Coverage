import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("mops_xbrl_adapter", ROOT / "scripts/mops_xbrl_adapter.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class AdapterTests(unittest.TestCase):
    def result(self, job, raw_out):
        content = b"<?xml tifrs-fixture?>"
        raw_out.write_bytes(content)
        return SimpleNamespace(
            source_url="https://example.invalid/mops",
            retrieved_at="2026-09-15T00:00:00+00:00",
            ticker=job.ticker,
            year=job.year,
            quarter=job.quarter,
            report_id=job.report_id,
            function_name=job.function_name,
            attempt_count=1,
            http_status=200,
            response_content_type="text/html",
            content_disposition=None,
            content_length=len(content),
            sha256=__import__("hashlib").sha256(content).hexdigest(),
            index_status="not_applicable",
            download_status="success_ixbrl_candidate",
            parse_status="not_run",
            error_class=None,
            error_message=None,
        )

    def test_fetch_is_idempotent_and_logs_cache_hit(self):
        calls = []

        def probe(*args, **kwargs):
            calls.append(args)
            job = SimpleNamespace(ticker=args[0], year=args[1], quarter=args[2], report_id=args[3], function_name=args[4])
            return self.result(job, kwargs["raw_out"])

        with tempfile.TemporaryDirectory() as directory:
            adapter = MODULE.MopsXbrlAdapter(Path(directory), probe_fn=probe)
            job = MODULE.MopsJob("2330", 2026, 2)
            adapter.fetch(job)
            adapter.fetch(job)
            self.assertEqual(len(calls), 1)
            events = (Path(directory) / "adapter-events.jsonl").read_text()
            self.assertIn('"event": "cache_hit"', events)

    def test_pilot_isolates_fetch_and_parser_failures(self):
        def probe(ticker, year, quarter, report_id, function_name, raw_out=None):
            if ticker == "9999":
                return SimpleNamespace(**{
                    "source_url": "x", "retrieved_at": "x", "ticker": ticker, "year": year, "quarter": quarter,
                    "report_id": report_id, "function_name": function_name, "attempt_count": 1, "http_status": 403,
                    "response_content_type": None, "content_disposition": None, "content_length": 0, "sha256": None,
                    "index_status": "not_applicable", "download_status": "request_failed", "parse_status": "not_run",
                    "error_class": "http_403", "error_message": "blocked",
                })
            return self.result(SimpleNamespace(ticker=ticker, year=year, quarter=quarter, report_id=report_id, function_name=function_name), raw_out)

        with tempfile.TemporaryDirectory() as directory:
            adapter = MODULE.MopsXbrlAdapter(Path(directory) / "cache", probe_fn=probe)
            jobs = [MODULE.MopsJob("2330", 2026, 2), MODULE.MopsJob("9999", 2026, 2)]
            results = MODULE.run_pilot(jobs, adapter, lambda path: {"raw": path.read_text()}, Path(directory) / "out")
            self.assertEqual([item.status for item in results], ["ok", "fetch_error"])
            self.assertTrue((Path(directory) / "out" / "2330_2026Q2_C_t164sb01.json").exists())
            self.assertFalse((Path(directory) / "out" / "9999_2026Q2_C_t164sb01.json").exists())
            payload = json.loads((Path(directory) / "out" / "pilot-results.json").read_text())
            self.assertEqual(payload[1]["error_class"], "http_403")


if __name__ == "__main__":
    unittest.main()
