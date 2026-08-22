"""
synonyms.py — Query expansion, built from data the database already contains.

Lexical retrieval matches characters, so a query that means the right thing in
the wrong words finds nothing: 水冷 and 液冷散熱 share no bigram. This widens a
query before it reaches BM25, using three sources that already exist — nothing
here is hand-written for a particular query.

  alias  utils.WIKILINK_ALIASES, the same map that normalises wikilinks
  gloss  「中文 (English)」 pairs mined from the reports themselves
  theme  build_themes.THEME_DEFINITIONS names and their related tags

Each tier carries a weight, so an exact alias counts for more than a merely
related theme tag. `python scripts/synonyms.py` prints the whole expansion so
it can be reviewed rather than trusted.
"""

import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import REPORTS_DIR, WIKILINK_ALIASES, canonical_wikilink, setup_stdout
from build_themes import THEME_DEFINITIONS

WEIGHTS = {"query": 1.0, "manual": 0.85, "alias": 0.75, "gloss": 0.7,
           "theme": 0.55, "related": 0.3}

# The one hand-maintained tier, for Chinese wordings that mean the same thing
# without sharing characters — no automatic source contains these. Extend it
# freely; `python scripts/eval_screen.py` reports covered and uncovered queries
# separately, so a query this table names stops measuring generalisation and
# starts measuring the table's own coverage.
MANUAL_SYNONYMS = {
    "液冷散熱": ["水冷", "液冷", "浸沒式冷卻", "浸沒式散熱", "液冷板", "冷卻液"],
    "散熱模組": ["熱管理", "散熱方案", "均熱", "散熱器"],
    "碳化矽": ["功率半導體", "第三代半導體", "寬能隙半導體"],
    "氮化鎵": ["第三代半導體", "寬能隙半導體"],
    "ABF 載板": ["封裝基板", "覆晶載板"],
    "矽光子": ["光通訊晶片", "光收發", "光電整合"],
    "低軌衛星": ["衛星通訊", "太空通訊", "衛星寬頻"],
    "HBM": ["高頻寬記憶體", "堆疊記憶體", "記憶體堆疊"],
    "CoWoS": ["先進封裝", "晶圓級封裝"],
    "EUV": ["先進製程", "極紫外光"],
    "光阻液": ["感光材料", "微影材料", "光阻劑"],
    "矽晶圓": ["晶圓材料", "晶圓基板", "長晶"],
    "電動車": ["車用晶片", "新能源車", "三電系統"],
    "AI 伺服器": ["AI 算力", "加速運算", "GPU 伺服器"],
    "儲能系統": ["電池儲能", "併網儲能"],
    "光收發模組": ["光模組", "光通訊模組"],
    "MLCC": ["積層陶瓷電容", "被動元件"],
    "矽中介層": ["中介層", "interposer"],
}

# 「中文 (English)」 as the reports write it: 均熱片 (Vapor Chamber).
_GLOSS_RE = re.compile(r"([一-鿿]{2,10})\s*[（(]\s*([A-Za-z][A-Za-z0-9 .\-/]{1,28})\s*[)）]")
_MIN_GLOSS_COUNT = 2
_MIN_GLOSS_LEN = 3          # drops PC, SI, CP — abbreviations with several meanings


def mine_glosses(texts):
    """Map an English gloss to the Chinese term it names, where unambiguous.

    The regex has no way to find where a Chinese noun phrase starts, so it
    picks up leading context: PCB appears as 印刷電路板, 多層印刷電路板 and
    一家專業的印刷電路板. When one candidate is contained in all the others it
    is the noun itself and the rest are that noun with a prefix. When they are
    unrelated the gloss genuinely has two meanings — EMS is both 電子代工 and
    能源管理 — and the whole entry is dropped rather than guessed.
    """
    pairs = Counter()
    for text in texts:
        for m in _GLOSS_RE.finditer(text.replace("[[", "").replace("]]", "")):
            pairs[(m.group(1), m.group(2).strip())] += 1

    by_gloss = defaultdict(set)
    for (zh, en), count in pairs.items():
        if count >= _MIN_GLOSS_COUNT and len(en) >= _MIN_GLOSS_LEN:
            by_gloss[en.lower()].add(zh)

    out = {}
    for gloss, terms in by_gloss.items():
        shortest = min(terms, key=len)
        if len(shortest) >= 2 and all(shortest in t for t in terms):
            out[gloss] = shortest
    return out


def theme_equivalents():
    """(tag, other name) pairs and (tag, related tag) pairs from the themes."""
    same, related = [], []
    for tag, defn in THEME_DEFINITIONS.items():
        # Names read "CoWoS 先進封裝" or "碳化矽 SiC": the tag plus its other name.
        other = defn["name"].replace(tag, " ").strip()
        if other and other != tag:
            same.append((tag, other))
        for r in defn.get("related", ()):
            related.append((tag, r))
    return same, related


class SynonymIndex:
    """Expands a query string into weighted terms."""

    def __init__(self, texts):
        self.tiers = defaultdict(dict)   # term -> {other: tier}

        def link(a, b, tier):
            if a and b and a != b:
                self.tiers[a].setdefault(b, tier)
                self.tiers[b].setdefault(a, tier)

        self.manual_terms = set()
        for canonical, others in MANUAL_SYNONYMS.items():
            self.manual_terms.add(canonical)
            for other in others:
                self.manual_terms.add(other)
                link(canonical, other, "manual")

        for alias, canonical in WIKILINK_ALIASES.items():
            link(alias, canonical, "alias")

        self.glosses = mine_glosses(texts)
        for gloss, term in self.glosses.items():
            link(gloss, term, "gloss")

        same, related = theme_equivalents()
        for a, b in same:
            link(a, b, "theme")
        for a, b in related:
            link(a, b, "related")

    def covered_manually(self, query, target):
        """True when the manual tier actually links this query to this target.

        Merely appearing in MANUAL_SYNONYMS is not enough: 散熱模組 has its own
        entry but does not lead to 液冷散熱, so counting it as covered would
        hide a real miss inside the covered group.
        """
        query, target = query.strip(), target.strip()
        if self.tiers.get(query, {}).get(target) == "manual":
            return True
        return self.tiers.get(target, {}).get(query) == "manual"

    def expand(self, query):
        """Return [(term, weight)], the query itself first."""
        query = query.strip()
        out = {query: WEIGHTS["query"]}
        for form in {query, canonical_wikilink(query), query.lower()}:
            for other, tier in self.tiers.get(form, {}).items():
                out[other] = max(out.get(other, 0), WEIGHTS[tier])
        return sorted(out.items(), key=lambda kv: -kv[1])


def load_report_texts():
    texts = []
    for root, _, files in os.walk(REPORTS_DIR):
        for f in files:
            if re.match(r"^\d{4}_", f) and f.endswith(".md"):
                with open(os.path.join(root, f), "r", encoding="utf-8") as fh:
                    texts.append(fh.read().split("## 財務概況")[0])
    return texts


def main():
    setup_stdout()
    index = SynonymIndex(load_report_texts())
    print(f"從語料挖出 {len(index.glosses)} 組中英對照，"
          f"人工表 {len(MANUAL_SYNONYMS)} 組，"
          f"合計 {len(index.tiers)} 個詞有擴展。\n")
    query = sys.argv[1] if len(sys.argv) > 1 else None
    if query:
        for term, weight in index.expand(query):
            print(f"  {weight:.2f}  {term}")
        return
    for term in sorted(index.tiers)[:40]:
        others = ", ".join(f"{o}({t})" for o, t in index.tiers[term].items())
        print(f"  {term:<16} → {others}")
    print(f"\n（只列前 40 個；帶查詢字串執行可看單一詞的擴展）")


if __name__ == "__main__":
    main()
