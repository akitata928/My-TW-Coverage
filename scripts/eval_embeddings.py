"""
eval_embeddings.py — Decide whether a semantic index is worth installing.

The lexical pipeline answers reworded queries only when the synonym table names
them: 96% when it does, 3% when it does not (`python scripts/eval_screen.py`).
Closing that 3% is the only reason to add an embedding model, so this script
measures it before anything is committed to.

It is deliberately NOT a dependency of anything else. Nothing in this project
imports it, and screen.py keeps working with no model installed.

    pip install fastembed          # ~20MB of onnxruntime, no torch
    python scripts/eval_embeddings.py

The model downloads on first run — a few hundred MB, cached under
~/.cache/huggingface. Delete that directory and uninstall fastembed to undo.

What the numbers mean: the row that decides it is 「人工表未涵蓋」. If a
semantic index moves that from 3% to something usable while the direct queries
stay near 100%, the disk is buying something. If it does not, it is not.

A corpus-derived alternative was already tried and rejected — see todo.md. LSA
over the same character bigrams reached 13% on those queries alone, but only by
dropping direct queries from 100% to 84%, and contributed nothing under rank
fusion. That failure says nothing about a pretrained model: LSA can only learn
from these 1,733 reports, while a pretrained model already knows 水冷 ≈ 液冷
from general Chinese. That is exactly the difference this script measures.
"""

import argparse
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import PROJECT_ROOT, REPORTS_DIR, WIKILINK_RE, setup_stdout
from screen import Corpus, run
from eval_screen import DIRECT, PARAPHRASE, HELD_OUT, Args

# Multilingual by necessity: the reports are Traditional Chinese.
DEFAULT_MODEL = "intfloat/multilingual-e5-small"
CACHE = os.path.join(PROJECT_ROOT, ".embeddings_cache.npz")
RRF_K = 60


def load_reports():
    tickers, texts = [], []
    for root, _, files in os.walk(REPORTS_DIR):
        for f in sorted(files):
            m = re.match(r"^(\d{4})_", f)
            if m and f.endswith(".md"):
                with open(os.path.join(root, f), "r", encoding="utf-8") as fh:
                    tickers.append(m.group(1))
                    texts.append(fh.read().split("## 財務概況")[0])
    return tickers, texts


def require(module, hint):
    try:
        return __import__(module)
    except ImportError:
        sys.exit(f"需要 {module}。安裝：{hint}\n（安裝前請先讀本檔開頭的說明。）")


def embed(texts, model_name, rebuild):
    np = require("numpy", "pip install numpy")
    if os.path.exists(CACHE) and not rebuild:
        cached = np.load(CACHE, allow_pickle=True)
        if str(cached["model"]) == model_name and len(cached["vectors"]) == len(texts):
            print(f"沿用快取向量：{CACHE}")
            return cached["vectors"]

    fastembed = require("fastembed", "pip install fastembed")
    print(f"以 {model_name} 產生 {len(texts)} 筆向量（首次執行會下載模型）…")
    model = fastembed.TextEmbedding(model_name=model_name)
    vectors = np.array(list(model.embed(texts)), dtype="float32")
    vectors /= np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-9)
    np.savez(CACHE, vectors=vectors, model=model_name)
    print(f"已寫入快取 {CACHE}（{vectors.nbytes / 1048576:.1f} MB）")
    return vectors


def main():
    setup_stdout()
    p = argparse.ArgumentParser()
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--k", type=int, default=20)
    p.add_argument("--weight", type=float, default=1.0, help="融合時語意側的權重")
    p.add_argument("--rebuild", action="store_true", help="忽略既有快取")
    args = p.parse_args()

    np = require("numpy", "pip install numpy")
    tickers, texts = load_reports()
    doc_vectors = embed(texts, args.model, args.rebuild)

    by_entity = defaultdict(set)
    for ticker, text in zip(tickers, texts):
        for entity in set(WIKILINK_RE.findall(text)):
            by_entity[entity].add(ticker)

    corpus = Corpus()
    fastembed = require("fastembed", "pip install fastembed")
    query_model = fastembed.TextEmbedding(model_name=args.model)

    def semantic_rank(query, limit):
        vector = np.array(list(query_model.embed([query]))[0], dtype="float32")
        vector /= max(np.linalg.norm(vector), 1e-9)
        order = np.argsort(doc_vectors @ vector)[::-1][:limit]
        return [tickers[i] for i in order]

    def ranked(query, mode):
        if mode == "lexical":
            return [r["ticker"] for r in run(corpus, Args(query, args.k))]
        if mode == "semantic":
            return semantic_rank(query, args.k)
        # Rank fusion, because the two scores are on incomparable scales.
        fused = defaultdict(float)
        for rank, t in enumerate([r["ticker"] for r in run(corpus, Args(query, 300))], 1):
            fused[t] += 1.0 / (RRF_K + rank)
        for rank, t in enumerate(semantic_rank(query, 300), 1):
            fused[t] += args.weight / (RRF_K + rank)
        return [t for t, _ in sorted(fused.items(), key=lambda kv: -kv[1])[:args.k]]

    def attainment(cases, mode):
        scores = []
        for query, tag in cases:
            expected = by_entity.get(tag, set())
            if not expected:
                continue
            hit = len(set(ranked(query, mode)) & expected)
            scores.append(hit / min(args.k, len(expected)))
        return sum(scores) / len(scores) if scores else 0.0

    uncovered = [(q, tag) for q, tag in PARAPHRASE + HELD_OUT
                 if not corpus.synonyms.covered_manually(q, tag)]
    groups = [("直接查詢", DIRECT), ("換句話說", PARAPHRASE),
              ("保留題", HELD_OUT), ("人工表未涵蓋 ←關鍵", uncovered)]

    print(f"\n模型 {args.model} ｜ top-{args.k} 達成率\n")
    print(f"{'':<20}{'只用字面':>10}{'只用語意':>10}{'兩者融合':>10}")
    print("-" * 50)
    for name, cases in groups:
        row = [attainment(cases, m) for m in ("lexical", "semantic", "hybrid")]
        print(f"{name:<20}" + "".join(f"{v:>10.0%}" for v in row))

    print("\n判讀：若「人工表未涵蓋」在融合欄明顯高於字面欄，"
          "且「直接查詢」沒有掉下來，才值得為它裝這個模型。")


if __name__ == "__main__":
    main()
