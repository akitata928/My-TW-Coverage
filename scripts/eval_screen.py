"""
eval_screen.py — Measure what screen.py retrieves, and what it misses.

Ground truth is the database's own wikilinks: for a topic tag, the companies
that belong are exactly the ones whose reports link it. A query is scored by
how many of those it returns in the top K.

The question set is split deliberately. Direct queries name the tag, or share
characters with it, and lexical retrieval should handle them. Paraphrase
queries mean the same thing while sharing almost no characters — 水冷 and
液冷散熱 have no bigram in common — and lexical retrieval cannot bridge that.
Reporting the two groups separately is the point: the gap between them is the
size of the problem a semantic index would solve, stated as a number instead
of an assumption.

Usage:
  python scripts/eval_screen.py
  python scripts/eval_screen.py --k 30
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import setup_stdout
from screen import Corpus, run

# (query, tag the query means)
DIRECT = [
    ("CoWoS", "CoWoS"),
    ("HBM", "HBM"),
    ("矽光子", "矽光子"),
    ("碳化矽", "碳化矽"),
    ("低軌衛星", "低軌衛星"),
    ("ABF 載板", "ABF 載板"),
    ("光阻液", "光阻液"),
    ("電動車", "電動車"),
    ("液冷散熱", "液冷散熱"),
    ("矽晶圓", "矽晶圓"),
]

PARAPHRASE = [
    ("水冷", "液冷散熱"),
    ("浸沒式冷卻", "液冷散熱"),
    ("先進封裝", "CoWoS"),
    ("第三代半導體", "碳化矽"),
    ("衛星通訊", "低軌衛星"),
    ("高頻寬記憶體", "HBM"),
    ("光通訊晶片", "矽光子"),
    ("感光材料", "光阻液"),
]


# Frozen before the synonym table was written, and not consulted while writing
# it. PARAPHRASE above overlaps with the theme names the table is derived from,
# so only this set measures the gain on wording the table never saw.
HELD_OUT = [
    ("先進製程", "EUV"),
    ("功率半導體", "碳化矽"),
    ("散熱模組", "液冷散熱"),
    ("光收發", "矽光子"),
    ("太空通訊", "低軌衛星"),
    ("記憶體模組", "HBM"),
    ("車用晶片", "電動車"),
    ("封裝基板", "ABF 載板"),
    ("晶圓材料", "矽晶圓"),
    ("微影材料", "光阻液"),
]


class Args:
    def __init__(self, query, limit, no_expand=False):
        self.query = query
        self.no_expand = no_expand
        self.hops = 0
        self.direction = "up"
        self.limit = limit
        self.min_hop = 0
        self.filters = []


def score(corpus, query, tag, k, no_expand=False):
    expected = corpus.by_entity.get(tag, set())
    if not expected:
        return None
    got = {r["ticker"] for r in run(corpus, Args(query, k, no_expand))}
    hit = got & expected
    # A tag with more companies than k cannot be fully recalled at k, so the
    # raw figure would read as a failure of retrieval rather than of the cutoff.
    ceiling = min(k, len(expected)) / len(expected)
    return {
        "expected": len(expected),
        "returned": len(got),
        "hit": len(hit),
        "recall": len(hit) / len(expected),
        "ceiling": ceiling,
        "attained": len(hit) / min(k, len(expected)),
        "precision": len(hit) / len(got) if got else 0.0,
    }


def report(corpus, title, cases, k, no_expand=False):
    print(f"\n{title}")
    print(f"{'查詢':<14}{'目標標籤':<12}{'應命中':>7}{'命中':>6}"
          f"{'召回率':>9}{'上限':>8}{'達成率':>9}{'精確率':>9}")
    print("-" * 78)
    recalls, precisions = [], []
    split = {True: [], False: []}
    for query, tag in cases:
        s = score(corpus, query, tag, k, no_expand)
        if not s:
            print(f"{query:<14}{tag:<12}  (標籤不存在，略過)")
            continue
        recalls.append(s["attained"])
        precisions.append(s["precision"])
        covered = corpus.synonyms.covered_manually(query, tag)
        split[covered].append(s["attained"])
        mark = "＊" if covered else "  "
        print(f"{mark}{query:<12}{tag:<12}{s['expected']:>7}{s['hit']:>6}"
              f"{s['recall']:>8.0%}{s['ceiling']:>8.0%}{s['attained']:>8.0%}{s['precision']:>9.0%}")
    if recalls:
        print("-" * 78)
        print(f"{'平均達成率 / 精確率':<30}{'':>21}{sum(recalls)/len(recalls):>8.0%}"
              f"{sum(precisions)/len(precisions):>9.0%}")
        for covered, label in ((True, "＊人工表已涵蓋"), (False, "  人工表未涵蓋")):
            if split[covered]:
                avg = sum(split[covered]) / len(split[covered])
                print(f"{label}（{len(split[covered])} 題）達成率 {avg:.0%}")
    return {
        "all": (sum(recalls) / len(recalls)) if recalls else 0.0,
        "uncovered": (sum(split[False]) / len(split[False])) if split[False] else None,
    }


def main():
    setup_stdout()
    p = argparse.ArgumentParser()
    p.add_argument("--k", type=int, default=20, help="取前幾名計分")
    p.add_argument("--no-expand", action="store_true", help="關閉同義詞擴展以取得基準線")
    args = p.parse_args()

    corpus = Corpus()
    direct = report(corpus, f"直接查詢（字面相符）— top {args.k}", DIRECT, args.k, args.no_expand)
    para = report(corpus, f"換句話說（字面不符）— top {args.k}", PARAPHRASE, args.k, args.no_expand)
    held = report(corpus, f"保留題（建表時未參考）— top {args.k}", HELD_OUT, args.k, args.no_expand)

    print(f"\n達成率：直接 {direct['all']:.0%} ｜ 換句話說 {para['all']:.0%} "
          f"｜ 保留題 {held['all']:.0%}")
    unc = [g["uncovered"] for g in (para, held) if g["uncovered"] is not None]
    if unc:
        print(f"人工表未涵蓋的換句話說題目：達成率 {sum(unc)/len(unc):.0%}"
              " ← 這才是一般化能力，不是表的覆蓋率。")
    print("「達成率」= 命中數 ÷ min(k, 應命中數)，扣掉了 top-k 造成的上限。")
    print("這個落差就是語意索引能補、而字面檢索補不了的部分。")


if __name__ == "__main__":
    main()
