import importlib.util
import io
import sys
import unittest
from unittest import mock
from urllib.error import HTTPError
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "probe_mops_xbrl.py"
SPEC = importlib.util.spec_from_file_location("probe_mops_xbrl", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ProbeUnitTests(unittest.TestCase):
    def test_build_url_uses_western_year_and_explicit_report_id(self):
        url = MODULE.build_url("2330", 2026, 2, "C")
        self.assertIn("co_id=2330", url)
        self.assertIn("year=2026", url)
        self.assertIn("season=2", url)
        self.assertIn("report_id=C", url)

    def test_ixbrl_payload_is_download_candidate_but_not_parsed(self):
        status = MODULE.classify_payload(
            b'<?xml version="1.0"?><html xmlns:tifrs-bsta="urn:test">'
        )
        self.assertEqual(("success_ixbrl_candidate", "not_run"), status)

    def test_html_error_page_is_not_success(self):
        self.assertEqual(
            ("invalid_html_response", "not_run"),
            MODULE.classify_payload(b"<html><body>d!!</body></html>"),
        )

    def test_empty_and_unknown_payloads_are_classified(self):
        self.assertEqual(("empty_content", "not_run"), MODULE.classify_payload(b""))
        self.assertEqual(("success_zip_candidate", "not_run"), MODULE.classify_payload(b"PK" + b"x"))
        self.assertEqual(("invalid_content", "not_run"), MODULE.classify_payload(b"not xbrl"))

    def test_probe_retries_transient_http_status_without_disabling_tls(self):
        class Response:
            status = 200
            headers = {
                "Content-Type": "; charset=iso-8859-1",
                "Content-Disposition": 'attachment; filename="fixture.html"',
            }

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return b'<html xmlns:tifrs-bsta="urn:test">'

        transient = HTTPError(
            "https://example.invalid", 503, "busy", {}, io.BytesIO(b"retry")
        )
        with mock.patch.object(MODULE, "urlopen", side_effect=[transient, Response()]) as opened:
            result = MODULE.probe("2330", 2026, 2, retries=1)

        self.assertEqual(2, result.attempt_count)
        self.assertEqual("success_ixbrl_candidate", result.download_status)
        self.assertEqual(2, opened.call_count)


if __name__ == "__main__":
    unittest.main()
