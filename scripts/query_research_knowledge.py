"""
query_research_knowledge.py - Search imported external research articles.

Usage:
  python scripts/query_research_knowledge.py --text "邊緣 AI"
  python scripts/query_research_knowledge.py --symbol 2395
  python scripts/query_research_knowledge.py --topic NPU
  python scripts/query_research_knowledge.py --list
"""

import argparse
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import PROJECT_ROOT, setup_stdout


DEFAULT_DB = os.path.join(PROJECT_ROOT, "data", "research_knowledge.sqlite")


def connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def article_to_dict(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "source": row["source"],
        "published_at": row["published_at"],
        "modified_at": row["modified_at"],
        "url": row["url"],
        "summary": row["summary"],
    }


def article_symbols(conn, article_id):
    rows = conn.execute(
        """
        SELECT symbol, name, market, industry_name
        FROM research_article_symbols
        WHERE article_id = ?
        ORDER BY symbol
        """,
        (article_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def article_topics(conn, article_id):
    rows = conn.execute(
        """
        SELECT topic
        FROM research_article_topics
        WHERE article_id = ?
        ORDER BY topic
        """,
        (article_id,),
    ).fetchall()
    return [row["topic"] for row in rows]


def enrich(conn, rows):
    results = []
    for row in rows:
        item = article_to_dict(row)
        item["symbols"] = article_symbols(conn, row["id"])
        item["topics"] = article_topics(conn, row["id"])
        results.append(item)
    return results


def query_text(conn, text):
    return conn.execute(
        """
        SELECT ra.*
        FROM research_articles_fts f
        JOIN research_articles ra ON ra.id = f.rowid
        WHERE research_articles_fts MATCH ?
        ORDER BY rank
        """,
        (text,),
    ).fetchall()


def query_symbol(conn, symbol):
    return conn.execute(
        """
        SELECT ra.*
        FROM research_article_symbols ras
        JOIN research_articles ra ON ra.id = ras.article_id
        WHERE ras.symbol = ?
        ORDER BY ra.published_at DESC
        """,
        (symbol,),
    ).fetchall()


def query_topic(conn, topic):
    return conn.execute(
        """
        SELECT ra.*
        FROM research_article_topics rat
        JOIN research_articles ra ON ra.id = rat.article_id
        WHERE rat.topic = ?
        ORDER BY ra.published_at DESC
        """,
        (topic,),
    ).fetchall()


def list_articles(conn):
    return conn.execute(
        """
        SELECT *
        FROM research_articles
        ORDER BY COALESCE(published_at, captured_at) DESC, id DESC
        """
    ).fetchall()


def render_markdown(results):
    lines = [f"共 {len(results)} 篇", ""]
    for item in results:
        lines.append(f"- **{item['id']}｜{item['title']}**")
        lines.append(f"  - 來源：{item['source']}｜發布：{item['published_at'] or 'N/A'}｜修改：{item['modified_at'] or 'N/A'}")
        if item["symbols"]:
            symbols = "、".join(f"{row['symbol']} {row['name']}" for row in item["symbols"])
            lines.append(f"  - 關聯股票：{symbols}")
        if item["topics"]:
            lines.append(f"  - 主題：{'、'.join(item['topics'])}")
        lines.append(f"  - URL：{item['url']}")
    return "\n".join(lines).rstrip()


def main():
    setup_stdout()
    parser = argparse.ArgumentParser(description="Query research_knowledge.sqlite.")
    parser.add_argument("--db", default=DEFAULT_DB, help=f"SQLite DB path. Default: {DEFAULT_DB}")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text", help="Full-text search query")
    group.add_argument("--symbol", help="Ticker symbol, e.g. 2395")
    group.add_argument("--topic", help="Exact topic tag")
    group.add_argument("--list", action="store_true", help="List all imported articles")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    args = parser.parse_args()

    if not os.path.exists(args.db):
        raise SystemExit(f"DB not found: {args.db}")

    conn = connect(args.db)
    if args.text:
        rows = query_text(conn, args.text)
    elif args.symbol:
        rows = query_symbol(conn, args.symbol)
    elif args.topic:
        rows = query_topic(conn, args.topic)
    else:
        rows = list_articles(conn)

    results = enrich(conn, rows)
    if args.format == "json":
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(results))


if __name__ == "__main__":
    main()
