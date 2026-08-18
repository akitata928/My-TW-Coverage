"""
build_obsidian_vault.py — Generate the entity notes that make [[links]] clickable.

Obsidian resolves [[名稱]] by filename only. Frontmatter `aliases` are offered
by autocomplete but a bare [[alias]] written by these scripts does NOT resolve
(that is what community plugins like Alias Linker exist to add), so every
wikilink needs a real file named after it or it shows as an unresolved link.

This writes one note per wikilink into entities/, outside Pilot_Reports/ so the
report scanners — which all require a `NNNN_` filename — never pick them up.
A company that has its own report gets `id:` set to its ticker and a link
through to that report; Phase 2 will use `id` as the entity key.

Usage:
  python scripts/build_obsidian_vault.py                 # all wikilinks
  python scripts/build_obsidian_vault.py --min-reports 2 # only linked entities
  python scripts/build_obsidian_vault.py --clean         # remove stale notes first
"""

import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import (
    PROJECT_ROOT, REPORTS_DIR, setup_stdout,
    WIKILINK_RE, WIKILINK_ALIASES, classify_wikilink, CATEGORY_LABELS,
)
from relations import extract_relations, SUPPLIES

ENTITIES_DIR = os.path.join(PROJECT_ROOT, "entities")

# Characters Obsidian or the filesystem cannot carry in a note name. A wikilink
# containing one can never resolve, so it is reported rather than sanitised —
# renaming the file would break the very link it is meant to satisfy.
UNSAFE_NAME = re.compile(r'[\\/:*?"<>|#^\[\]]')

TOP_NEIGHBOURS = 10
TOP_CHAIN = 15
MIN_SHARED_REPORTS = 2


def scan_reports():
    """Return (mentions, reports, co_occurrence, tickers, upstream, downstream)."""
    mentions = Counter()
    reports = Counter()
    co = defaultdict(Counter)
    ticker_by_company = {}
    upstream = defaultdict(Counter)
    downstream = defaultdict(Counter)

    for root, _, files in os.walk(REPORTS_DIR):
        for f in sorted(files):
            m = re.match(r"^(\d{4})_(.+)\.md$", f)
            if not m:
                continue
            ticker, company = m.group(1), m.group(2)
            ticker_by_company[company] = ticker

            with open(os.path.join(root, f), "r", encoding="utf-8") as fh:
                head = fh.read().split("## 財務概況")[0]

            for r in extract_relations(head, company):
                if r.kind == SUPPLIES:
                    upstream[r.target][r.source] += 1
                    downstream[r.source][r.target] += 1

            links = WIKILINK_RE.findall(head)
            mentions.update(links)
            unique = sorted(set(links))
            reports.update(unique)
            for i, a in enumerate(unique):
                for b in unique[i + 1:]:
                    co[a][b] += 1
                    co[b][a] += 1

    return mentions, reports, co, ticker_by_company, upstream, downstream


def aliases_for(name):
    """Alias surface forms that point at this canonical name."""
    return sorted(a for a, c in WIKILINK_ALIASES.items() if c == name)


def build_note(name, mentions, reports, co, ticker_by_company, upstream, downstream):
    """Render one entity note."""
    category = classify_wikilink(name)
    ticker = ticker_by_company.get(name)

    front = ["---"]
    if ticker:
        front.append(f'id: "{ticker}"')
    front.append(f"type: {category}")
    front.append(f"mentions: {mentions[name]}")
    front.append(f"reports: {reports[name]}")
    alias_list = aliases_for(name)
    if alias_list:
        front.append("aliases:")
        front.extend(f"  - {a}" for a in alias_list)
    front.append("---")

    body = [
        "",
        f"# {name}",
        "",
        f"{CATEGORY_LABELS[category]} · {reports[name]} 份報告提及 · 共 {mentions[name]} 次",
        "",
    ]
    if ticker:
        body += [f"**完整研究報告：** [[{ticker}_{name}]]", ""]

    # Direction comes from what the reports state, so these two lists are the
    # part a plain co-occurrence graph could never give: who feeds this entity
    # and who it feeds.
    for heading, chain in (("上游 — 供應給它", upstream[name]),
                           ("下游 — 它供應給", downstream[name])):
        entries = chain.most_common(TOP_CHAIN)
        if entries:
            body += [f"## {heading} ({len(chain)})", ""]
            body += [f"- [[{other}]]" for other, _ in entries]
            if len(chain) > TOP_CHAIN:
                body += [f"- …另有 {len(chain) - TOP_CHAIN} 個"]
            body += [""]

    neighbours = [
        (other, count)
        for other, count in co[name].most_common(TOP_NEIGHBOURS)
        if count >= MIN_SHARED_REPORTS
    ]
    if neighbours:
        body += ["## 最常一起出現", ""]
        body += [f"- [[{other}]] — 同時出現於 {count} 份報告" for other, count in neighbours]
        body += [""]

    body += [
        "---",
        "",
        "*自動產生：`python scripts/build_obsidian_vault.py`。"
        "左側反向連結面板會列出所有提及此實體的報告。*",
        "",
    ]
    return "\n".join(front + body)


def main():
    setup_stdout()

    args = sys.argv[1:]
    min_reports = 1
    if "--min-reports" in args:
        min_reports = int(args[args.index("--min-reports") + 1])

    mentions, reports, co, tickers, upstream, downstream = scan_reports()

    if "--clean" in args and os.path.isdir(ENTITIES_DIR):
        for f in os.listdir(ENTITIES_DIR):
            if f.endswith(".md"):
                os.remove(os.path.join(ENTITIES_DIR, f))

    os.makedirs(ENTITIES_DIR, exist_ok=True)

    wanted = sorted(n for n in reports if reports[n] >= min_reports)
    unsafe = [n for n in wanted if UNSAFE_NAME.search(n)]

    # A case-insensitive filesystem (macOS, Windows) would silently collapse
    # SOC.md into SoC.md, so keep the better-attested spelling and report the
    # loser instead of writing one over the other.
    by_fold = defaultdict(list)
    for n in wanted:
        by_fold[n.lower()].append(n)
    shadowed = []
    for group in by_fold.values():
        if len(group) > 1:
            group.sort(key=lambda n: (-reports[n], n))
            shadowed.extend(group[1:])

    skip = set(unsafe) | set(shadowed)
    written = 0
    for name in wanted:
        if name in skip:
            continue
        path = os.path.join(ENTITIES_DIR, f"{name}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(build_note(name, mentions, reports, co, tickers,
                               upstream, downstream))
        written += 1

    total_links = sum(mentions.values())
    resolved = sum(mentions[n] for n in wanted if n not in skip)
    print(f"Wrote {written} entity notes to entities/")
    print(f"  link occurrences resolved: {resolved}/{total_links} ({100 * resolved / total_links:.1f}%)")
    if unsafe:
        print(f"  skipped {len(unsafe)} name(s) unusable as a filename: {unsafe}")
    if shadowed:
        print(f"  skipped {len(shadowed)} name(s) that collide when case is folded: {shadowed}")


if __name__ == "__main__":
    main()
