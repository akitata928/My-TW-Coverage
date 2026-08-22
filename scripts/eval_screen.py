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


class Args:
    def __init__(self, query, limit):
        self.query = query
        self.hops = 0
        self.direction = "up"
        self.limit = limit
        self.min_hop = 0
        self.filters = []


def score(corpus, query, tag, k):
    expected = corpus.by_entity.get(tag, set())
    if not expected:
        return None
    got = {r["ticker"] for r in run(corpus, Args(query, k))}
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


def report(corpus, title, cases, k):
    print(f"\n{title}")
    print(f"{'查詢':<14}{'目標標籤':<12}{'應命中':>7}{'命中':>6}"
          f"{'召回率':>9}{'上限':>8}{'達成率':>9}{'精確率':>9}")
    print("-" * 78)
    recalls, precisions = [], []
    for query, tag in cases:
        s = score(corpus, query, tag, k)
        if not s:
            print(f"{query:<14}{tag:<12}  (標籤不存在，略過)")
            continue
        recalls.append(s["attained"])
        precisions.append(s["precision"])
        print(f"{query:<14}{tag:<12}{s['expected']:>7}{s['hit']:>6}"
              f"{s['recall']:>8.0%}{s['ceiling']:>8.0%}{s['attained']:>8.0%}{s['precision']:>9.0%}")
    if recalls:
        print("-" * 78)
        print(f"{'平均達成率 / 精確率':<30}{'':>21}{sum(recalls)/len(recalls):>8.0%}"
              f"{sum(precisions)/len(precisions):>9.0%}")
    return (sum(recalls) / len(recalls)) if recalls else 0.0


def main():
    setup_stdout()
    p = argparse.ArgumentParser()
    p.add_argument("--k", type=int, default=20, help="取前幾名計分")
    args = p.parse_args()

    corpus = Corpus()
    direct = report(corpus, f"直接查詢（字面相符）— top {args.k}", DIRECT, args.k)
    para = report(corpus, f"換句話說（字面不符）— top {args.k}", PARAPHRASE, args.k)

    print(f"\n達成率落差：直接 {direct:.0%} vs 換句話說 {para:.0%}"
          f"（相差 {direct - para:.0%}）")
    print("「達成率」= 命中數 ÷ min(k, 應命中數)，扣掉了 top-k 造成的上限。")
    print("這個落差就是語意索引能補、而字面檢索補不了的部分。")


if __name__ == "__main__":
    main()
