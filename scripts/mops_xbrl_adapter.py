#!/usr/bin/env python3
"""Runtime-safe MOPS XBRL download adapter and small pilot runner.

The adapter keeps raw responses and metadata in an explicit runtime cache
directory (outside the repository by default).  It is deliberately agnostic
about Arelle so the transport layer can be tested without network access.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Any


SUCCESS_PREFIX = "success_"
SAFE_PART = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class MopsJob:
    ticker: str
    year: int
    quarter: int
    report_id: str = "C"
    function_name: str = "t164sb01"

    def key(self) -> str:
        raw = f"{self.ticker}_{self.year}Q{self.quarter}_{self.report_id}_{self.function_name}"
        return SAFE_PART.sub("_", raw)


class MopsAdapterError(RuntimeError):
    def __init__(self, job: MopsJob, error_class: str, message: str):
        super().__init__(f"{job.key()}: {error_class}: {message}")
        self.job = job
        self.error_class = error_class
        self.message = message


class MopsXbrlAdapter:
    """Download MOPS files with a content-addressed, idempotent cache."""

    def __init__(self, cache_dir: Path, probe_fn: Callable[..., Any] | None = None):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.cache_dir / "adapter-events.jsonl"
        if probe_fn is None:
            from probe_mops_xbrl import probe

            probe_fn = probe
        self._probe = probe_fn

    def _paths(self, job: MopsJob) -> tuple[Path, Path]:
        stem = job.key()
        return self.cache_dir / f"{stem}.bin", self.cache_dir / f"{stem}.json"

    def _event(self, payload: dict[str, Any]) -> None:
        event = {"at": datetime.now(timezone.utc).isoformat(), **payload}
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")

    def fetch(self, job: MopsJob):
        raw_path, metadata_path = self._paths(job)
        if raw_path.is_file() and metadata_path.is_file():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            digest = hashlib.sha256(raw_path.read_bytes()).hexdigest()
            if metadata.get("sha256") == digest and str(metadata.get("download_status", "")).startswith(SUCCESS_PREFIX):
                self._event({"event": "cache_hit", "job": job.key(), "sha256": digest})
                return metadata

        result = self._probe(
            job.ticker,
            job.year,
            job.quarter,
            job.report_id,
            job.function_name,
            raw_out=raw_path,
        )
        metadata = asdict(result) if hasattr(result, "__dataclass_fields__") else vars(result).copy()
        metadata["cache_status"] = "downloaded"
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self._event({"event": "download", "job": job.key(), "download_status": result.download_status, "error_class": result.error_class})
        if not result.download_status.startswith(SUCCESS_PREFIX):
            raise MopsAdapterError(job, result.error_class or result.download_status, result.error_message or "download failed")
        return metadata


@dataclass(frozen=True)
class PilotResult:
    job: MopsJob
    status: str
    input_sha256: str | None = None
    error_class: str | None = None
    error_message: str | None = None


def run_pilot(
    jobs: Iterable[MopsJob],
    adapter: MopsXbrlAdapter,
    parser: Callable[[Path], Any],
    output_dir: Path,
) -> list[PilotResult]:
    """Run independent jobs; one failure cannot contaminate other outputs."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[PilotResult] = []
    for job in jobs:
        raw_path, _ = adapter._paths(job)
        try:
            metadata = adapter.fetch(job)
            parsed = parser(raw_path)
            destination = output_dir / f"{job.key()}.json"
            destination.write_text(json.dumps(parsed, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            results.append(PilotResult(job, "ok", metadata.get("sha256")))
        except MopsAdapterError as exc:
            results.append(PilotResult(job, "fetch_error", error_class=exc.error_class, error_message=exc.message))
        except Exception as exc:  # pilot records parser failures without partial output
            results.append(PilotResult(job, "parse_error", error_class=type(exc).__name__, error_message=str(exc)))
    (output_dir / "pilot-results.json").write_text(
        json.dumps([asdict(item) for item in results], ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return results
