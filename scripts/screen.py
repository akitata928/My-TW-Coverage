"""
screen.py — Find companies by topic, walk their supply chain, filter by numbers.

Three stages, each doing what it is actually good at:

1. Retrieval finds reports that talk about the topic. Chinese has no word
   boundaries, so scoring is BM25 over character bigrams plus whole ASCII
   tokens; a query that names a known entity also seeds that entity directly.
2. Graph expansion walks the typed edges from relations.py. This is the part a
   text search cannot do: --hops 2 --direction up answers "the suppliers of the
   suppliers", which no amount of keyword matching will reach.
3. Screening applies numeric predicates to the financial tables.

Retrieval is lexical on purpose — it needs no model, no API key and no network.
That leaves a measured gap on synonyms: 液冷 and 水冷 are the same idea and
share no bigram. `python scripts/eval_screen.py` quantifies it.

Usage:
  python scripts/screen.py "液冷散熱"
  python scripts/screen.py "CoWoS" --hops 1 --direction up
  python scripts/screen.py "AI 伺服器" --gross-margin ">30" --pe "<25" --limit 15
  python scripts/screen.py "矽光子" --json
"""

import argparse
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import (
    REPORTS_DIR, setup_stdout, WIKILINK_RE, canonical_wikilink,
    parse_financials,
)
from relations import extract_relations, SUPPLIES
from synonyms import SynonymIndex

BM25_K1, BM25_B = 1.5, 0.75
SEED_LIMIT = 40
HOP_DECAY = 0.45

# Screening flags map onto parse_financials keys.
NUMERIC_FIELDS = {
    "pe": "P/E",
    "forward-pe": "Forward P/E",
    "pb": "P/B",
    "ps": "P/S",
    "ev-ebitda": "EV/EBITDA",
    "gross-margin": "毛利率",
    "operating-margin": "營益率",
    "net-margin": "淨利率",
    "market-cap": "市值",
    "revenue": "營收",
}


def tokenize(text):
    """Character bigrams for CJK plus whole alphanumeric tokens."""
    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9.\-+]*", text.lower())
    cjk = re.sub(r"[^一-鿿]+", " ", text)
    for run in cjk.split():
        tokens.extend(run[i:i + 2] for i in range(len(run) - 1))
        if len(run) == 1:
            tokens.append(run)
    return tokens


class Corpus:
    """Reports, their entities, their financials, and the relation graph."""

    def __init__(self):
        self.reports = {}        # ticker -> {company, sector, text, entities, fin}
        self.by_entity = defaultdict(set)
        self.upstream = defaultdict(set)     # entity -> entities feeding it
        self.downstream = defaultdict(set)
        self.company_of = {}     # entity name -> ticker, when it has a report

        df = Counter()
        texts = []
        for root, _, files in os.walk(REPORTS_DIR):
            for f in sorted(files):
                m = re.match(r"^(\d{4})_(.+)\.md$", f)
                if not m:
                    continue
                ticker, company = m.group(1), m.group(2)
                raw = open(os.path.join(root, f), "r", encoding="utf-8").read()
                head = raw.split("## 財務概況")[0]
                texts.append(head)
                entities = set(WIKILINK_RE.findall(head))

                self.company_of[company] = ticker
                self.reports[ticker] = {
                    "company": company,
                    "sector": os.path.basename(root),
                    "tokens": Counter(tokenize(head)),
                    "entities": entities,
                    "fin": parse_financials(raw),
                }
                for e in entities:
                    self.by_entity[e].add(ticker)
                for r in extract_relations(head, company):
                    if r.kind == SUPPLIES:
                        self.upstream[r.target].add(r.source)
                        self.downstream[r.source].add(r.target)

        for rep in self.reports.values():
            df.update(rep["tokens"].keys())
        self.df = df
        self.n = len(self.reports)
        self.avg_len = sum(sum(r["tokens"].values()) for r in self.reports.values()) / max(self.n, 1)
        self.synonyms = SynonymIndex(texts)

    def bm25(self, terms):
        """Score every report against weighted query terms. Returns {ticker: score}."""
        weighted = Counter()
        for phrase, weight in terms:
            for token in set(tokenize(phrase)):
                if self.df.get(token):
                    weighted[token] = max(weighted[token], weight)

        scores = Counter()
        for token, weight in weighted.items():
            idf = math.log(1 + (self.n - self.df[token] + 0.5) / (self.df[token] + 0.5))
            for ticker, rep in self.reports.items():
                tf = rep["tokens"].get(token)
                if not tf:
                    continue
                length = sum(rep["tokens"].values())
                norm = tf * (BM25_K1 + 1) / (
                    tf + BM25_K1 * (1 - BM25_B + BM25_B * length / self.avg_len)
                )
                scores[ticker] += weight * idf * norm
        return scores

    def entity_seeds(self, query):
        """Entities named outright by the query."""
        direct = canonical_wikilink(query.strip())
        hits = {direct} if direct in self.by_entity else set()
        if not hits:
            lowered = query.strip().lower()
            hits = {e for e in self.by_entity
                    if e.lower() == lowered or (len(lowered) > 1 and lowered in e.lower())}
        return hits


def walk(corpus, entities, hops, direction):
    """Expand along supply edges. Returns {entity: (hop, via)}.

    `via` is the entity one step closer to the seed, so a result can say which
    link in the chain reached it — without it a two-hop row cannot be told
    apart from a one-hop row.
    """
    reached = {e: (0, None) for e in entities}
    frontier = set(entities)
    for hop in range(1, hops + 1):
        nxt = {}
        for e in frontier:
            neighbours = set()
            if direction in ("up", "both"):
                neighbours |= corpus.upstream.get(e, set())
            if direction in ("down", "both"):
                neighbours |= corpus.downstream.get(e, set())
            for n in neighbours:
                if n not in reached and n not in nxt:
                    nxt[n] = e
        for e, via in nxt.items():
            reached[e] = (hop, via)
        frontier = set(nxt)
        if not frontier:
            break
    return reached


def parse_predicate(raw):
    """Turn '>30', '<=20' or '10-25' into a test function."""
    raw = raw.strip()
    m = re.fullmatch(r"(>=|<=|>|<|=)?\s*(-?[\d.]+)", raw)
    if m:
        op, value = m.group(1) or ">=", float(m.group(2))
        ops = {">": lambda v: v > value, ">=": lambda v: v >= value,
               "<": lambda v: v < value, "<=": lambda v: v <= value,
               "=": lambda v: v == value}
        return ops[op]
    m = re.fullmatch(r"(-?[\d.]+)\s*-\s*(-?[\d.]+)", raw)
    if m:
        lo, hi = float(m.group(1)), float(m.group(2))
        return lambda v: lo <= v <= hi
    raise SystemExit(f"Cannot read the filter {raw!r}. Use >30, <20, <=15 or 10-25.")


def run(corpus, args):
    if args.query:
        terms = ([(args.query, 1.0)] if args.no_expand
                 else corpus.synonyms.expand(args.query))
    else:
        terms = []
    scores = corpus.bm25(terms) if terms else Counter()

    # An expanded term that names a known entity seeds that entity too, so
    # "先進封裝" reaches the reports tagged [[CoWoS]] and not only those whose
    # characters happen to match.
    seeds = {}
    for phrase, weight in terms:
        for entity in corpus.entity_seeds(phrase):
            seeds[entity] = max(seeds.get(entity, 0), weight)

    # A report that links the named entity is a stronger signal than one that
    # merely scores well on characters, so it is boosted rather than ranked
    # against the text score.
    best = max(scores.values(), default=1.0) or 1.0
    hits = {}
    # Seed strength tracks how confident the expansion is. Giving a merely
    # related tag the same boost as the queried tag lets 「CoWoS」 be answered
    # with HBM companies, which measured as a drop from 100% to 46%.
    for entity, weight in sorted(seeds.items(), key=lambda kv: -kv[1]):
        boost = best * weight
        for ticker in corpus.by_entity[entity]:
            if hits.get(ticker, {}).get("score", 0) >= boost:
                continue
            hits[ticker] = {"score": boost, "why": f"提及 [[{entity}]]", "hop": 0}

    for ticker, score in scores.most_common(SEED_LIMIT):
        if ticker not in hits and score > 0:
            hits[ticker] = {"score": score, "why": "內文相符", "hop": 0}

    if args.hops:
        seeds = set(seeds)

    if args.hops and seeds:
        reached = walk(corpus, seeds, args.hops, args.direction)
        label = {"up": "上游", "down": "下游", "both": "供應鏈"}[args.direction]
        for entity, (hop, via) in reached.items():
            if hop == 0:
                continue
            # Only entities this database actually covers become rows. Falling
            # back to "every report mentioning this entity" would turn one
            # material into hundreds of unrelated companies.
            ticker = corpus.company_of.get(entity)
            if not ticker or ticker in hits:
                continue
            hits[ticker] = {
                "score": best * (HOP_DECAY ** hop),
                "why": f"{label} {hop} 階（經由 {via}）",
                "hop": hop,
            }

    rows = []
    for ticker, meta in hits.items():
        rep = corpus.reports[ticker]
        fin = rep["fin"]
        keep = True
        for flag, test in args.filters:
            value = fin.get(flag.replace("-", "_"))
            if value is None or not test(value):
                keep = False
                break
        if keep and meta["hop"] >= args.min_hop:
            rows.append({
                "ticker": ticker, "company": rep["company"], "sector": rep["sector"],
                "hop": meta["hop"], "score": round(meta["score"], 3),
                "why": meta["why"], **fin,
            })

    rows.sort(key=lambda r: (r["hop"], -r["score"]))
    # Limit per hop, otherwise the hundreds of direct mentions bury the very
    # chain the --hops flag was asked for.
    kept, seen = [], Counter()
    for row in rows:
        if seen[row["hop"]] < args.limit:
            seen[row["hop"]] += 1
            kept.append(row)
    return kept


def main():
    setup_stdout()
    p = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    p.add_argument("query", nargs="?", default="", help="主題或實體名稱")
    p.add_argument("--hops", type=int, default=0, help="沿供應鏈擴展幾階")
    p.add_argument("--direction", choices=("up", "down", "both"), default="up")
    p.add_argument("--limit", type=int, default=20, help="每一階最多顯示幾家")
    p.add_argument("--min-hop", type=int, default=0,
                   help="只看第 N 階之後，例如 --hops 2 --min-hop 2 就是「供應商的供應商」")
    p.add_argument("--json", action="store_true")
    p.add_argument("--no-expand", action="store_true",
                   help="關閉同義詞擴展，只用原始字串檢索")
    for flag in NUMERIC_FIELDS:
        p.add_argument(f"--{flag}", metavar="EXPR", help=f"{NUMERIC_FIELDS[flag]} 條件，如 >30 或 10-25")
    args = p.parse_args()

    args.filters = [
        (flag, parse_predicate(getattr(args, flag.replace("-", "_"))))
        for flag in NUMERIC_FIELDS if getattr(args, flag.replace("-", "_"))
    ]
    if not args.query and not args.filters:
        p.error("需要一個查詢字串或至少一個數值條件")

    rows = run(Corpus(), args)

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return

    if not rows:
        if args.min_hop:
            print(f"第 {args.min_hop} 階沒有新公司。若種子是技術或材料，"
                  "它的上游供應商多半就是直接提及它的那些公司，因此第 1 階不會有新結果——"
                  "試 --hops 2 --min-hop 2。")
        else:
            print("沒有符合條件的公司。")
        return

    def num(v, w):
        return f"{v:>{w}.2f}" if isinstance(v, float) else f"{'—':>{w}}"

    current = None
    for r in rows:
        if r["hop"] != current:
            current = r["hop"]
            heading = "直接提及" if current == 0 else f"第 {current} 階"
            print(f"\n【{heading}】")
            print(f"{'代號':<6}{'公司':<12}{'毛利率':>8}{'淨利率':>8}{'P/E':>8}{'P/B':>7}  依據")
            print("-" * 86)
        print(f"{r['ticker']:<6}{r['company']:<12}{num(r['gross_margin'],8)}"
              f"{num(r['net_margin'],8)}{num(r['pe'],8)}{num(r['pb'],7)}  {r['why']}")
    print(f"\n共 {len(rows)} 家")


if __name__ == "__main__":
    main()
