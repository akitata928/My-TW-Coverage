"""
match_candidates.py — Match web-research candidate tickers/names to reports.

Use this after web research fallback to verify whether candidate companies
already exist in Pilot_Reports before writing any enrichment.

Usage:
  python scripts/match_candidates.py "3131 弘塑" "3583 辛耘"
  python scripts/match_candidates.py --file research/candidates.txt
  python scripts/match_candidates.py --format json "7734 印能科技"
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import PROJECT_ROOT, REPORTS_DIR, setup_stdout


def clean_wikilink(text):
    return re.sub(r"\[\[([^\]]+)\]\]", r"\1", text).strip()


def parse_ticker_from_filename(filename):
    normal = re.match(r"^(\d{4})_(.+)\.md$", filename)
    if normal:
        return normal.group(1), normal.group(2)

    reversed_name = re.match(r"^(.+)_(\d{4})\.md$", filename)
    if reversed_name:
        return reversed_name.group(2), reversed_name.group(1)

    return None, None


def load_reports():
    records = []
    for root, _, filenames in os.walk(REPORTS_DIR):
        for filename in filenames:
            if not filename.endswith(".md"):
                continue
            ticker, filename_name = parse_ticker_from_filename(filename)
            if not ticker:
                continue

            path = os.path.join(root, filename)
            company = filename_name
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    first_line = fh.readline()
                match = re.match(r"^#\s+\d{4}\s+-\s+(.+)$", first_line.strip())
                if match:
                    company = clean_wikilink(match.group(1))
            except OSError:
                pass

            records.append(
                {
                    "ticker": ticker,
                    "company": company,
                    "sector": os.path.basename(os.path.dirname(path)),
                    "path": os.path.relpath(path, PROJECT_ROOT),
                }
            )
    return records


def read_candidates(args):
    candidates = list(args.candidates or [])
    if args.file:
        with open(args.file, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("#"):
                    candidates.append(line)
    return candidates


def normalize_candidate(candidate):
    ticker_match = re.search(r"\b(\d{4})\b", candidate)
    ticker = ticker_match.group(1) if ticker_match else None
    name = candidate
    if ticker:
        name = re.sub(r"\b" + re.escape(ticker) + r"\b", "", name)
    name = re.sub(r"[-—|,，:：].*$", "", name).strip()
    return ticker, name


def match_candidate(candidate, records):
    ticker, name = normalize_candidate(candidate)

    matches = []
    if ticker:
        matches = [record for record in records if record["ticker"] == ticker]
        if matches:
            return {
                "candidate": candidate,
                "status": "matched",
                "match_type": "ticker",
                "matches": matches,
            }

    if name:
        exact = [record for record in records if record["company"] == name]
        if exact:
            return {
                "candidate": candidate,
                "status": "matched",
                "match_type": "exact_name",
                "matches": exact,
            }

        contains = [
            record
            for record in records
            if name in record["company"] or record["company"] in name
        ]
        if contains:
            return {
                "candidate": candidate,
                "status": "possible",
                "match_type": "partial_name",
                "matches": contains[:10],
            }

    return {
        "candidate": candidate,
        "status": "unmatched",
        "match_type": "none",
        "matches": [],
    }


def render_markdown(results):
    matched = [item for item in results if item["status"] == "matched"]
    possible = [item for item in results if item["status"] == "possible"]
    unmatched = [item for item in results if item["status"] == "unmatched"]

    lines = [
        "# Candidate Match Results",
        "",
        f"- matched: {len(matched)}",
        f"- possible: {len(possible)}",
        f"- unmatched: {len(unmatched)}",
        "",
    ]

    for title, rows in [
        ("Matched", matched),
        ("Possible", possible),
        ("Unmatched", unmatched),
    ]:
        lines.append(f"## {title}")
        lines.append("")
        if not rows:
            lines.append("- none")
            lines.append("")
            continue
        for item in rows:
            if item["matches"]:
                for match in item["matches"]:
                    lines.append(
                        f"- {item['candidate']} -> "
                        f"{match['ticker']} {match['company']} "
                        f"({match['sector']}) `{match['path']}` "
                        f"[{item['match_type']}]"
                    )
            else:
                lines.append(f"- {item['candidate']}")
        lines.append("")

    return "\n".join(lines).rstrip()


def render_tsv(results):
    lines = ["candidate\tstatus\tmatch_type\tticker\tcompany\tsector\tpath"]
    for item in results:
        if item["matches"]:
            for match in item["matches"]:
                lines.append(
                    "\t".join(
                        [
                            item["candidate"],
                            item["status"],
                            item["match_type"],
                            match["ticker"],
                            match["company"],
                            match["sector"],
                            match["path"],
                        ]
                    )
                )
        else:
            lines.append(
                "\t".join(
                    [
                        item["candidate"],
                        item["status"],
                        item["match_type"],
                        "",
                        "",
                        "",
                        "",
                    ]
                )
            )
    return "\n".join(lines)


def main():
    setup_stdout()
    parser = argparse.ArgumentParser(
        description="Match web-research candidate companies to Pilot_Reports."
    )
    parser.add_argument("candidates", nargs="*", help="Ticker/name candidates.")
    parser.add_argument("--file", help="Read candidates from a text file.")
    parser.add_argument(
        "--format",
        choices=["markdown", "json", "tsv"],
        default="markdown",
        help="Output format.",
    )
    args = parser.parse_args()

    candidates = read_candidates(args)
    if not candidates:
        parser.error("provide candidates as arguments or with --file")

    records = load_reports()
    results = [match_candidate(candidate, records) for candidate in candidates]

    if args.format == "json":
        print(json.dumps(results, ensure_ascii=False, indent=2))
    elif args.format == "tsv":
        print(render_tsv(results))
    else:
        print(render_markdown(results))


if __name__ == "__main__":
    main()
