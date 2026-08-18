"""
normalize_reports.py — Repair wikilink surface forms across existing reports.

Applies utils.normalize_wikilinks to reports already on disk: flattens links
that swallowed another link (e.g. [[AI[[伺服器]]]]), and folds aliases and
case/separator variants (Nvidia, MicroLED, AI伺服器) onto one canonical node.
Enrichment writes normalize on the way in; this is the catch-up pass for
content written before that, or before a name was added to the canonical set.

Financial tables are never touched — normalization stops at 財務概況.

Usage:
  python scripts/normalize_reports.py --dry-run          # report only
  python scripts/normalize_reports.py                    # ALL tickers
  python scripts/normalize_reports.py 2330 2454          # specific tickers
  python scripts/normalize_reports.py --batch 101
  python scripts/normalize_reports.py --sector Semiconductors
"""

import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import (
    find_ticker_files, get_ticker_from_filename, parse_scope_args, setup_stdout,
    canonical_wikilink, normalize_wikilinks, GENERIC_TERMS, WIKILINK_RE,
)


def normalize_title(content, ticker, company):
    """Rewrite the H1 to the documented `# {ticker} - [[{company}]]` form.

    The filename is ground truth for ticker/company identity (CLAUDE.md rule 2),
    and wikilinking the subject makes each report a node in its own right rather
    than only appearing when some other report happens to mention it.
    """
    want = f"# {ticker} - [[{canonical_wikilink(company)}]]"
    lines = content.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("# "):
            if line == want:
                return content, False
            lines[i] = want
            return "\n".join(lines), True
    return content, False


def changed_links(before, after):
    """Return a Counter describing how this pass altered the link set.

    Positional pairing breaks as soon as a link is removed, so compare link
    multisets instead: what disappeared, what appeared, and what merely
    changed spelling in place.
    """
    old = Counter(WIKILINK_RE.findall(before.split("## 財務概況")[0]))
    new = Counter(WIKILINK_RE.findall(after.split("## 財務概況")[0]))
    removed, added = old - new, new - old

    changes = Counter()
    for name, count in removed.items():
        if name in GENERIC_TERMS:
            changes[f"{name} -> (去連結)"] += count
        else:
            changes[f"{name} -> ?"] += count
    for name, count in added.items():
        changes[f"(新增) -> {name}"] += count
    return changes


def main():
    setup_stdout()

    args = [a for a in sys.argv[1:] if a != "--dry-run"]
    dry_run = "--dry-run" in sys.argv[1:]
    tickers, sector, desc = parse_scope_args(args)

    files = find_ticker_files(tickers, sector)
    if not files:
        print("No matching reports found.")
        return

    print(f"Normalizing {desc} ({len(files)} files){' — dry run' if dry_run else ''}")

    rewrites = Counter()
    touched = 0
    retitled = 0
    for ticker in sorted(files):
        path = files[ticker]
        with open(path, "r", encoding="utf-8") as f:
            before = f.read()

        _, company = get_ticker_from_filename(path)
        after, title_changed = normalize_title(before, ticker, company)
        after = normalize_wikilinks(after)
        if after == before:
            continue

        touched += 1
        retitled += title_changed
        rewrites.update(changed_links(before, after))
        if not dry_run:
            with open(path, "w", encoding="utf-8") as f:
                f.write(after)

    print(f"\n{touched} file(s) {'would change' if dry_run else 'updated'}.")
    print(f"{retitled} title(s) rewritten to `# ticker - [[company]]`.")
    if rewrites:
        print("Link rewrites:")
        for change, count in rewrites.most_common():
            print(f"  {count:4d}  {change}")


if __name__ == "__main__":
    main()
