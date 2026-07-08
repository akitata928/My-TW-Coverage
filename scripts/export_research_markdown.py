"""
export_research_markdown.py - Export research_knowledge.sqlite to Markdown wiki pages.

The export creates readable wiki pages from the local SQLite article knowledge
base without touching Pilot_Reports. By default it writes metadata, summaries,
topic links, stock links, and article-source links, but not full article text.

Usage:
  python scripts/export_research_markdown.py
  python scripts/export_research_markdown.py --include-full-text
"""

import argparse
import os
import re
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import PROJECT_ROOT, setup_stdout


DEFAULT_DB = os.path.join(PROJECT_ROOT, "data", "research_knowledge.sqlite")
DEFAULT_OUT = os.path.join(PROJECT_ROOT, "knowledge")


def connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_dirs(root):
    for name in ["articles", "topics", "stocks"]:
        os.makedirs(os.path.join(root, name), exist_ok=True)


def clean_generated(root):
    for name in ["articles", "topics", "stocks"]:
        path = os.path.join(root, name)
        if not os.path.isdir(path):
            continue
        for filename in os.listdir(path):
            if filename.endswith(".md"):
                os.remove(os.path.join(path, filename))


def safe_filename(value, max_len=90):
    value = (value or "untitled").strip()
    value = re.sub(r"[\\/:*?\"<>|#\[\]\n\r\t：，、；！？（）()]+", "_", value)
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"_+", "_", value).strip("._ ")
    return (value or "untitled")[:max_len]


def md_escape(value):
    return (value or "").replace("\r\n", "\n").strip()


def clean_summary(value, fallback=None):
    text = md_escape(value or fallback or "")
    text = text.replace(
        "Imported as an external research source for later review before Pilot_Reports enrichment.",
        "",
    )
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text or "尚無摘要。"


def yaml_escape(value):
    value = (value or "").replace("\\", "\\\\").replace('"', '\\"')
    return f'"{value}"'


def wiki_link(target, label=None):
    target = target.replace(".md", "")
    if label and label != target:
        return f"[[{target}|{label}]]"
    return f"[[{target}]]"


def article_filename(article):
    date = article["published_at"] or article["captured_at"][:10] or "undated"
    return f"{date}_{safe_filename(article['title'])}.md"


def topic_filename(topic):
    return f"{safe_filename(topic)}.md"


def stock_filename(symbol, name):
    return f"{symbol}_{safe_filename(name, max_len=40)}.md"


def fetch_articles(conn):
    return conn.execute(
        """
        SELECT *
        FROM research_articles
        ORDER BY COALESCE(published_at, captured_at), id
        """
    ).fetchall()


def fetch_symbols(conn, article_id):
    return conn.execute(
        """
        SELECT symbol, name, market, industry_name
        FROM research_article_symbols
        WHERE article_id = ?
        ORDER BY symbol
        """,
        (article_id,),
    ).fetchall()


def fetch_topics(conn, article_id):
    return conn.execute(
        """
        SELECT topic
        FROM research_article_topics
        WHERE article_id = ?
        ORDER BY topic
        """,
        (article_id,),
    ).fetchall()


def article_path_for(article):
    return os.path.join("articles", article_filename(article))


def write_file(path, content):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content.rstrip() + "\n")


def render_article(article, symbols, topics, include_full_text=False):
    title = md_escape(article["title"])
    article_link = wiki_link(article_path_for(article), title)
    lines = [
        "---",
        f'id: {article["id"]}',
        f'title: {yaml_escape(title)}',
        f'source: {yaml_escape(article["source"])}',
        f'url: {yaml_escape(article["url"])}',
        f'published_at: {yaml_escape(article["published_at"] or "")}',
        f'modified_at: {yaml_escape(article["modified_at"] or "")}',
        f'captured_at: {yaml_escape(article["captured_at"] or "")}',
        "---",
        "",
        f"# {title}",
        "",
        f"- 來源：{article['source']}",
        f"- 網址：{article['url']}",
        f"- 發布：{article['published_at'] or 'N/A'}",
        f"- 更新：{article['modified_at'] or 'N/A'}",
        f"- SQLite article_id：{article['id']}",
        "",
        "## 摘要",
        "",
        clean_summary(article["summary"], article["description"]),
        "",
        "## 關聯股票",
        "",
    ]

    if symbols:
        for item in symbols:
            target = os.path.join("stocks", stock_filename(item["symbol"], item["name"]))
            label = f"{item['symbol']} {item['name']}"
            extra = f"｜{item['market']}" if item["market"] else ""
            lines.append(f"- {wiki_link(target, label)}{extra}")
    else:
        lines.append("- 尚未標記。")

    lines.extend(["", "## 主題標籤", ""])
    if topics:
        for item in topics:
            target = os.path.join("topics", topic_filename(item["topic"]))
            lines.append(f"- {wiki_link(target, item['topic'])}")
    else:
        lines.append("- 尚未標記。")

    lines.extend(
        [
            "",
            "## Wiki 位置",
            "",
            f"- 本頁：{article_link}",
            "- 來源全文保留在本機 SQLite；此 Markdown 預設只保存整理後索引與摘要。",
        ]
    )

    if include_full_text:
        lines.extend(["", "## 原文全文", "", md_escape(article["full_text"])])

    return "\n".join(lines)


def render_topic(topic, entries):
    lines = [
        f"# {topic}",
        "",
        "## 相關文章",
        "",
    ]
    for article, symbols in entries:
        lines.append(f"- {wiki_link(article_path_for(article), article['title'])}")
        if symbols:
            labels = []
            for item in symbols:
                target = os.path.join("stocks", stock_filename(item["symbol"], item["name"]))
                labels.append(wiki_link(target, f"{item['symbol']} {item['name']}"))
            lines.append(f"  - 關聯股票：{'、'.join(labels)}")
        lines.append(f"  - 來源：{article['source']}｜發布：{article['published_at'] or 'N/A'}")
    return "\n".join(lines)


def render_stock(symbol, name, entries):
    lines = [
        f"# {symbol} {name}",
        "",
        "## 相關文章",
        "",
    ]
    for article, topics in entries:
        lines.append(f"- {wiki_link(article_path_for(article), article['title'])}")
        if topics:
            topic_links = [
                wiki_link(os.path.join("topics", topic_filename(item["topic"])), item["topic"])
                for item in topics
            ]
            lines.append(f"  - 主題：{'、'.join(topic_links)}")
        lines.append(f"  - 來源：{article['source']}｜發布：{article['published_at'] or 'N/A'}")
    return "\n".join(lines)


def export(conn, out_dir, include_full_text=False):
    ensure_dirs(out_dir)
    articles = fetch_articles(conn)
    topic_entries = {}
    stock_entries = {}

    for article in articles:
        symbols = fetch_symbols(conn, article["id"])
        topics = fetch_topics(conn, article["id"])
        article_path = os.path.join(out_dir, "articles", article_filename(article))
        write_file(article_path, render_article(article, symbols, topics, include_full_text))

        for item in topics:
            topic_entries.setdefault(item["topic"], []).append((article, symbols))
        for item in symbols:
            key = (item["symbol"], item["name"])
            stock_entries.setdefault(key, []).append((article, topics))

    for topic, entries in sorted(topic_entries.items()):
        path = os.path.join(out_dir, "topics", topic_filename(topic))
        write_file(path, render_topic(topic, entries))

    for (symbol, name), entries in sorted(stock_entries.items()):
        path = os.path.join(out_dir, "stocks", stock_filename(symbol, name))
        write_file(path, render_stock(symbol, name, entries))

    return {
        "articles": len(articles),
        "topics": len(topic_entries),
        "stocks": len(stock_entries),
    }


def main():
    setup_stdout()
    parser = argparse.ArgumentParser(description="Export research article SQLite data to Markdown wiki pages.")
    parser.add_argument("--db", default=DEFAULT_DB, help=f"SQLite DB path. Default: {DEFAULT_DB}")
    parser.add_argument("--out", default=DEFAULT_OUT, help=f"Output directory. Default: {DEFAULT_OUT}")
    parser.add_argument("--include-full-text", action="store_true", help="Write full article text into article markdown pages")
    parser.add_argument("--clean", action="store_true", help="Remove existing generated Markdown pages before exporting")
    args = parser.parse_args()

    if not os.path.exists(args.db):
        raise SystemExit(f"DB not found: {args.db}")

    conn = connect(args.db)
    if args.clean:
        clean_generated(args.out)
    result = export(conn, args.out, include_full_text=args.include_full_text)
    print(f"Exported {result['articles']} articles, {result['topics']} topics, {result['stocks']} stocks")
    print(f"Output: {args.out}")


if __name__ == "__main__":
    main()
