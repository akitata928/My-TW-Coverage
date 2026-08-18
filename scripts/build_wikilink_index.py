"""
build_wikilink_index.py — Regenerate WIKILINKS.md from all ticker reports.

Usage:
    python scripts/build_wikilink_index.py

This scans every .md file under Pilot_Reports/ and builds a categorized
index of all [[wikilinks]] with occurrence counts. Run after any enrichment
update to keep the index current.

Classification comes from utils.classify_wikilink so this index, the theme
pages, and the network graph always agree on what a wikilink is.
"""

import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import (
    REPORTS_DIR, PROJECT_ROOT, setup_stdout,
    WIKILINK_RE, classify_wikilink,
)

OUTPUT_FILE = os.path.join(PROJECT_ROOT, "WIKILINKS.md")

# Companies are long-tail: a name mentioned by a single report says something
# about that report, not about the graph, so the index lists only linked ones.
MIN_COMPANY_MENTIONS = 2

SECTION_TITLES = [
    ("technology", "Technologies & Standards", None),
    ("material", "Materials & Substrates", None),
    ("application", "Applications & End Markets", None),
    ("generic", "Generic Terms (should be plain text — see CLAUDE.md rule 1)", None),
    ("international_company", "International Companies", 200),
    ("taiwan_company", "Taiwan Companies", 300),
]


def collect_wikilinks():
    """Scan all reports. Returns (Counter of mentions, number of reports)."""
    mentions = Counter()
    reports = 0
    for root, dirs, files in os.walk(REPORTS_DIR):
        for f in files:
            if not (f.endswith(".md") and re.match(r"^\d{4}", f)):
                continue
            reports += 1
            with open(os.path.join(root, f), "r", encoding="utf-8") as fh:
                content = fh.read().split("## 財務概況")[0]
            mentions.update(WIKILINK_RE.findall(content))
    return mentions, reports


def categorize(mentions):
    """Group wikilinks by category. Returns {category: {name: count}}."""
    grouped = {key: {} for key, _, _ in SECTION_TITLES}
    for name, count in mentions.items():
        category = classify_wikilink(name)
        if category.endswith("_company") and count < MIN_COMPANY_MENTIONS:
            continue
        grouped[category][name] = count
    return grouped


def build_section(title, items, limit=None):
    """Build a markdown section from a dict."""
    lines = []
    sorted_items = sorted(items.items(), key=lambda x: (-x[1], x[0]))
    if limit and len(sorted_items) > limit:
        shown = sorted_items[:limit]
        total_label = f" ({len(items)} total, showing top {limit})"
    else:
        shown = sorted_items
        total_label = f" ({len(items)})"

    lines.append(f"## {title}{total_label}")
    lines.append("")
    for name, count in shown:
        lines.append(f"- [[{name}]] ({count})")
    lines.append("")
    return lines


def main():
    setup_stdout()

    mentions, reports = collect_wikilinks()
    grouped = categorize(mentions)

    lines = [
        "# Wikilink Index",
        "",
        f"> **{len(mentions)} unique wikilinks** across {reports:,} ticker reports. "
        "Auto-generated — do not edit manually.",
        "> Regenerate: `python scripts/build_wikilink_index.py`",
        "",
        "---",
        "",
    ]

    for key, title, limit in SECTION_TITLES:
        # The generic section is debt that should reach zero; once it does,
        # an empty heading is noise rather than information.
        if grouped[key]:
            lines.extend(build_section(title, grouped[key], limit))

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Generated WIKILINKS.md: {len(mentions)} unique wikilinks, {reports} reports")
    for key, title, _ in SECTION_TITLES:
        print(f"  {title.split(' (')[0]}: {len(grouped[key])}")


if __name__ == "__main__":
    main()
