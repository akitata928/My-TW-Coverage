"""
query_theme.py — Read-only wikilink query for ticker reports.

Searches non-financial report sections for a wikilink such as [[CoWoS]] and
prints matching Taiwan-listed companies in Markdown, JSON, or TSV.

Usage:
  python scripts/query_theme.py "CoWoS"
  python scripts/query_theme.py "AI 伺服器" --format json
  python scripts/query_theme.py "液冷散熱" --include-bare
  python scripts/query_theme.py "CoWoS" --sector Semiconductors
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import PROJECT_ROOT, REPORTS_DIR, setup_stdout


SECTION_PATTERNS = {
    "desc": r"## 業務簡介\n(.*?)(?=\n## |\Z)",
    "supply_chain": r"## 供應鏈位置\n(.*?)(?=\n## |\Z)",
    "customer_supplier": r"## 主要客戶及供應商\n(.*?)(?=\n## |\Z)",
}

ROLE_LABELS = {
    "upstream": "上游",
    "midstream": "中游",
    "downstream": "下游",
    "supply_chain": "供應鏈",
    "customer_supplier": "客戶/供應商",
    "core_business": "核心業務",
    "mentioned": "其他提及",
}

ROLE_ORDER = [
    "core_business",
    "upstream",
    "midstream",
    "downstream",
    "supply_chain",
    "customer_supplier",
    "mentioned",
]


def clean_text(text):
    return re.sub(r"\s+", " ", text).strip()


def extract_sections(content):
    text = content.split("## 財務概況")[0]
    sections = {}
    for name, pattern in SECTION_PATTERNS.items():
        match = re.search(pattern, text, re.DOTALL)
        sections[name] = match.group(1) if match else ""
    return sections


def find_mentions(section_text, query, include_bare=False, max_snippets=1):
    patterns = [r"\[\[" + re.escape(query) + r"\]\]"]
    if include_bare:
        patterns.append(r"(?<!\[\[)" + re.escape(query) + r"(?!\]\])")

    mentions = []
    for pattern in patterns:
        for match in re.finditer(pattern, section_text):
            start = max(0, match.start() - 60)
            end = min(len(section_text), match.end() + 80)
            mentions.append(
                {
                    "start": match.start(),
                    "linked": pattern.startswith(r"\[\["),
                    "snippet": clean_text(section_text[start:end]),
                }
            )

    mentions.sort(key=lambda item: item["start"])
    return mentions[:max_snippets]


def infer_supply_role(section_text, position):
    prefix = section_text[:position]
    markers = [
        (prefix.rfind("上游"), "upstream"),
        (prefix.rfind("中游"), "midstream"),
        (prefix.rfind("下游"), "downstream"),
    ]
    idx, role = max(markers, key=lambda item: item[0])
    return role if idx >= 0 else "supply_chain"


def query_reports(query, include_bare=False, sector=None, max_snippets=1):
    results = []

    for sector_dir in sorted(os.listdir(REPORTS_DIR)):
        if sector and sector_dir.lower() != sector.lower():
            continue

        sector_path = os.path.join(REPORTS_DIR, sector_dir)
        if not os.path.isdir(sector_path):
            continue

        for filename in sorted(os.listdir(sector_path)):
            if not filename.endswith(".md"):
                continue
            match = re.match(r"^(\d{4})_(.+)\.md$", filename)
            if not match:
                continue

            ticker, company = match.group(1), match.group(2)
            filepath = os.path.join(sector_path, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                sections = extract_sections(f.read())

            file_matches = []
            for section_name, section_text in sections.items():
                mentions = find_mentions(
                    section_text,
                    query,
                    include_bare=include_bare,
                    max_snippets=max_snippets,
                )
                if not mentions:
                    continue

                if section_name == "supply_chain":
                    role = infer_supply_role(section_text, mentions[0]["start"])
                elif section_name == "customer_supplier":
                    role = "customer_supplier"
                elif section_name == "desc":
                    role = "core_business"
                else:
                    role = "mentioned"

                file_matches.append(
                    {
                        "section": section_name,
                        "role": role,
                        "snippets": [m["snippet"] for m in mentions],
                        "linked": any(m["linked"] for m in mentions),
                    }
                )

            if file_matches:
                primary = min(
                    file_matches,
                    key=lambda item: ROLE_ORDER.index(item["role"])
                    if item["role"] in ROLE_ORDER
                    else len(ROLE_ORDER),
                )
                results.append(
                    {
                        "ticker": ticker,
                        "company": company,
                        "sector": sector_dir,
                        "role": primary["role"],
                        "linked": any(item["linked"] for item in file_matches),
                        "snippets": [
                            snippet
                            for item in file_matches
                            for snippet in item["snippets"]
                        ][:max_snippets],
                        "path": os.path.relpath(filepath, PROJECT_ROOT),
                    }
                )

    return results


def render_markdown(query, results, show_snippets=True):
    lines = [f"# {query} 關聯公司", "", f"共 {len(results)} 家", ""]
    if not results:
        lines.append("沒有找到符合條件的公司。")
        lines.append("")
        lines.append("## 下一步")
        lines.append("")
        lines.append("- 用 `--include-bare` 再查一次，確認是否有未標記的裸文字。")
        lines.append("- 檢查拼字或同義詞，例如 `CoPoS` 可能需要同時查相關封裝名詞。")
        lines.append("- 若仍為 0 筆，改走 web research fallback：搜尋「題材 台灣 上市 供應鏈 概念股」，再確認公司是否已存在於 `Pilot_Reports/`。")
        lines.append("- 找到候選公司後，先人工驗證來源，再決定是否用 `discover.py --apply` 或 `update_enrichment.py` 補資料。")
        return "\n".join(lines)

    by_role = defaultdict(list)
    for item in results:
        by_role[item["role"]].append(item)

    for role in ROLE_ORDER:
        entries = by_role.get(role, [])
        if not entries:
            continue
        lines.append(f"## {ROLE_LABELS.get(role, role)} ({len(entries)})")
        lines.append("")
        for item in sorted(entries, key=lambda row: row["ticker"]):
            status = "linked" if item["linked"] else "bare"
            lines.append(
                f"- **{item['ticker']} {item['company']}** "
                f"({item['sector']}) — {status}"
            )
            if show_snippets:
                for snippet in item["snippets"]:
                    lines.append(f"  - {snippet}")
        lines.append("")

    return "\n".join(lines).rstrip()


def render_tsv(results):
    lines = ["ticker\tcompany\tsector\trole\tlinked"]
    for item in results:
        lines.append(
            "\t".join(
                [
                    item["ticker"],
                    item["company"],
                    item["sector"],
                    item["role"],
                    "yes" if item["linked"] else "no",
                ]
            )
        )
    return "\n".join(lines)


def main():
    setup_stdout()
    parser = argparse.ArgumentParser(
        description="Read-only query for wikilink relationships in ticker reports."
    )
    parser.add_argument("query", help="Wikilink or topic to search, e.g. CoWoS")
    parser.add_argument(
        "--format",
        choices=["markdown", "json", "tsv"],
        default="markdown",
        help="Output format",
    )
    parser.add_argument(
        "--include-bare",
        action="store_true",
        help="Also match plain text mentions that are not wrapped in [[wikilinks]]",
    )
    parser.add_argument("--sector", help="Limit search to one sector folder")
    parser.add_argument(
        "--no-snippets",
        action="store_true",
        help="Hide context snippets in Markdown output",
    )
    parser.add_argument(
        "--max-snippets",
        type=int,
        default=1,
        help="Maximum snippets per company",
    )
    args = parser.parse_args()

    results = query_reports(
        args.query,
        include_bare=args.include_bare,
        sector=args.sector,
        max_snippets=max(0, args.max_snippets),
    )

    if args.format == "json":
        print(json.dumps(results, ensure_ascii=False, indent=2))
    elif args.format == "tsv":
        print(render_tsv(results))
    else:
        print(render_markdown(args.query, results, show_snippets=not args.no_snippets))


if __name__ == "__main__":
    main()
