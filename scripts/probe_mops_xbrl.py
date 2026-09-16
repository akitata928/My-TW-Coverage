#!/usr/bin/env python3
"""Probe the official MOPS XBRL download endpoint without storing credentials.

The probe deliberately keeps TLS certificate verification enabled and never
falls back to ``verify=False``.  By default it emits metadata only; raw
responses are written only when ``--raw-out`` is explicitly supplied.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import ssl
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_URL = "https://mopsov.twse.com.tw"
DOWNLOAD_PATH = "/server-java/FileDownLoad"
DEFAULT_REFERER = f"{BASE_URL}/mops/web/t203sb01"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
    "AppleWebKit/537.36 Chrome/140 Safari/537.36"
)
RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}
FILENAME_RE = re.compile(r'filename="?([^";]+)')


@dataclass
class ProbeResult:
    source_url: str
    retrieved_at: str
    ticker: str
    year: int
    quarter: int
    report_id: str
    function_name: str
    attempt_count: int
    http_status: Optional[int]
    response_content_type: Optional[str]
    content_disposition: Optional[str]
    content_length: int
    sha256: Optional[str]
    index_status: str
    download_status: str
    parse_status: str
    error_class: Optional[str] = None
    error_message: Optional[str] = None


def build_url(
    ticker: str,
    year: int,
    quarter: int,
    report_id: str = "C",
    function_name: str = "t164sb01",
) -> str:
    return (
        f"{BASE_URL}{DOWNLOAD_PATH}?functionName={function_name}"
        f"&step=9&co_id={ticker}&year={year}&season={quarter}"
        f"&report_id={report_id}"
    )


def classify_payload(content: bytes) -> tuple[str, str]:
    """Return (download_status, parse_status) without invoking an XBRL parser."""
    if not content:
        return "empty_content", "not_run"
    sample = content[:2_000_000].lower()
    if content[:2] == b"PK":
        return "success_zip_candidate", "not_run"
    if b"tifrs-" in sample or b"ifrs-full" in sample:
        return "success_ixbrl_candidate", "not_run"
    if b"<html" in sample or b"<!doctype" in sample:
        return "invalid_html_response", "not_run"
    return "invalid_content", "not_run"


def _header(headers, name: str) -> Optional[str]:
    value = headers.get(name)
    return str(value) if value is not None else None


def probe(
    ticker: str,
    year: int,
    quarter: int,
    report_id: str = "C",
    function_name: str = "t164sb01",
    timeout: float = 30.0,
    retries: int = 2,
    raw_out: Optional[Path] = None,
) -> ProbeResult:
    if not 1 <= quarter <= 4:
        raise ValueError("quarter must be 1..4")
    if retries < 0:
        raise ValueError("retries must be >= 0")

    url = build_url(ticker, year, quarter, report_id, function_name)
    retrieved_at = datetime.now(timezone.utc).isoformat()
    last_error: Optional[tuple[str, str]] = None
    attempts = 0

    for attempt in range(retries + 1):
        attempts = attempt + 1
        request = Request(
            url,
            headers={"User-Agent": DEFAULT_USER_AGENT, "Referer": DEFAULT_REFERER},
            method="GET",
        )
        try:
            # urlopen uses the platform CA bundle and validates TLS by default.
            with urlopen(request, timeout=timeout, context=ssl.create_default_context()) as response:
                content = response.read()
                status = int(response.status)
                download_status, parse_status = classify_payload(content)
                if raw_out is not None and download_status.startswith("success_"):
                    raw_out.parent.mkdir(parents=True, exist_ok=True)
                    raw_out.write_bytes(content)
                return ProbeResult(
                    source_url=url,
                    retrieved_at=retrieved_at,
                    ticker=ticker,
                    year=year,
                    quarter=quarter,
                    report_id=report_id,
                    function_name=function_name,
                    attempt_count=attempts,
                    http_status=status,
                    response_content_type=_header(response.headers, "Content-Type"),
                    content_disposition=_header(response.headers, "Content-Disposition"),
                    content_length=len(content),
                    sha256=hashlib.sha256(content).hexdigest(),
                    index_status="not_applicable",
                    download_status=download_status,
                    parse_status=parse_status,
                )
        except HTTPError as exc:
            body = exc.read(512)
            last_error = (f"http_{exc.code}", body.decode("utf-8", "replace")[:200])
            if exc.code not in RETRYABLE_STATUS or attempt >= retries:
                break
        except TimeoutError as exc:
            last_error = ("timeout", str(exc))
        except URLError as exc:
            last_error = ("network_error", str(exc.reason))
        except OSError as exc:
            last_error = ("io_error", str(exc))

        if attempt < retries:
            time.sleep(min(2**attempt, 4))

    error_class, error_message = last_error or ("unknown_error", "probe failed")
    return ProbeResult(
        source_url=url,
        retrieved_at=retrieved_at,
        ticker=ticker,
        year=year,
        quarter=quarter,
        report_id=report_id,
        function_name=function_name,
        attempt_count=attempts,
        http_status=(
            int(error_class.removeprefix("http_"))
            if error_class.startswith("http_")
            else None
        ),
        response_content_type=None,
        content_disposition=None,
        content_length=0,
        sha256=None,
        index_status="not_applicable",
        download_status="request_failed",
        parse_status="not_run",
        error_class=error_class,
        error_message=error_message,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("ticker")
    parser.add_argument("year", type=int, help="Western year, e.g. 2026")
    parser.add_argument("quarter", type=int, choices=range(1, 5))
    parser.add_argument("--report-id", default="C", choices=("A", "C"))
    parser.add_argument("--function-name", default="t164sb01")
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--metadata-out", type=Path)
    parser.add_argument("--raw-out", type=Path)
    args = parser.parse_args()
    result = probe(
        args.ticker,
        args.year,
        args.quarter,
        args.report_id,
        args.function_name,
        args.timeout,
        args.retries,
        args.raw_out,
    )
    payload = json.dumps(asdict(result), ensure_ascii=False, indent=2) + "\n"
    if args.metadata_out:
        args.metadata_out.parent.mkdir(parents=True, exist_ok=True)
        args.metadata_out.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if result.download_status.startswith("success_") else 2


if __name__ == "__main__":
    sys.exit(main())
