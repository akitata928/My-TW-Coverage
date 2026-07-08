"""
import_research_article.py - Import a public research article into SQLite.

The database stores external research articles separately from Pilot_Reports so
new sources can be searched and reviewed before enriching company reports.

Usage:
  python scripts/import_research_article.py https://finlab.finance/blog/edge-ai-stocks
  python scripts/import_research_article.py URL --db data/research_knowledge.sqlite
"""

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from urllib.request import Request, urlopen

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import PROJECT_ROOT, setup_stdout


DEFAULT_DB = os.path.join(PROJECT_ROOT, "data", "research_knowledge.sqlite")
DEFAULT_MARKET_DB = os.environ.get(
    "TW_MARKET_DB",
    os.path.abspath(os.path.join(PROJECT_ROOT, "..", "data", "tw_market.sqlite")),
)

DEFAULT_TOPICS = [
    "邊緣運算",
    "邊緣 AI",
    "Edge AI",
    "工業電腦",
    "IPC",
    "NPU",
    "AI 伺服器",
    "雲端算力",
    "邊緣伺服器",
    "機器人控制器",
    "AIoT",
    "Jetson Thor",
    "DeepSeek",
    "NVIDIA",
    "Qualcomm",
    "高通",
    "FinLab 回測",
    "台股概念股",
]

GENERIC_NAME_ONLY_SYMBOLS = {
    "1326",  # 台化
    "1459",  # 聯發
    "2850",  # 新產
    "3118",  # 進階
    "4743",  # 合一
    "5287",  # 數字
    "5347",  # 世界
    "6486",  # 互動
}


class MainTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_main = False
        self.depth = 0
        self.skip = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "svg", "noscript"}:
            self.skip += 1
        if tag == "main":
            self.in_main = True
            self.depth = 1
        elif self.in_main:
            self.depth += 1
        if self.in_main and tag in {"h1", "h2", "h3", "p", "li", "td", "th", "figcaption"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if self.skip and tag in {"script", "style", "svg", "noscript"}:
            self.skip -= 1
        if self.in_main:
            if tag in {"h1", "h2", "h3", "p", "li", "tr", "table", "section", "article"}:
                self.parts.append("\n")
            self.depth -= 1
            if tag == "main" or self.depth <= 0:
                self.in_main = False

    def handle_data(self, data):
        if self.in_main and not self.skip:
            text = " ".join(unescape(data).split())
            if text:
                self.parts.append(text + " ")


def clean_text(text):
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def fetch_url(url):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=30) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, "replace")


def extract_json_ld(html):
    items = []
    for match in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        try:
            items.append(json.loads(unescape(match.group(1))))
        except json.JSONDecodeError:
            continue
    return items


def meta_content(html, name):
    pattern = r'<meta (?:property|name)="' + re.escape(name) + r'" content="(.*?)"'
    match = re.search(pattern, html)
    return unescape(match.group(1)) if match else None


def extract_title(html, blog):
    title = blog.get("headline") or meta_content(html, "og:title")
    if title:
        return title
    match = re.search(r"<title>(.*?)</title>", html, re.S)
    return clean_text(unescape(match.group(1))) if match else "Untitled"


def extract_main_text(html):
    parser = MainTextParser()
    parser.feed(html)
    text = clean_text("".join(parser.parts))
    if text:
        return text
    fallback = re.sub(r"<(script|style|svg|noscript).*?</\1>", "", html, flags=re.S)
    fallback = re.sub(r"<[^>]+>", " ", fallback)
    return clean_text(unescape(fallback))


def infer_source(url):
    match = re.search(r"https?://(?:www\.)?([^/]+)", url)
    if not match:
        return "unknown"
    domain = match.group(1)
    if domain == "finlab.finance":
        return "FinLab"
    return domain


def load_market_symbols(market_db):
    if not market_db or not os.path.exists(market_db):
        return []
    conn = sqlite3.connect(market_db)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            """
            SELECT symbol, name, market, industry_name
            FROM securities
            WHERE COALESCE(is_active, 1) = 1
            """
        ).fetchall()
    finally:
        conn.close()


def match_symbols(text, market_db):
    rows = load_market_symbols(market_db)
    matches = []
    seen = set()
    for row in rows:
        symbol = row["symbol"]
        name = row["name"]
        if not symbol or not name or len(name) < 2:
            continue
        explicit_symbol = re.search(rf"(?<!\d){re.escape(symbol)}(?!\d)", text)
        explicit_name = name in text
        if not explicit_name:
            continue
        if symbol in GENERIC_NAME_ONLY_SYMBOLS and not explicit_symbol:
            continue
        if symbol in seen:
            continue
        seen.add(symbol)
        idx = text.find(name)
        context = text[max(0, idx - 80):idx + 120] if idx >= 0 else None
        matches.append(
            {
                "symbol": symbol,
                "name": name,
                "market": row["market"],
                "industry_name": row["industry_name"],
                "context": context,
            }
        )
    return matches


def match_topics(text, extra_topics=None):
    candidates = list(DEFAULT_TOPICS)
    if extra_topics:
        candidates.extend(extra_topics)
    seen = set()
    topics = []
    lower = text.lower()
    for topic in candidates:
        key = topic.lower()
        if key in lower and key not in seen:
            seen.add(key)
            topics.append(topic)
    return topics


def init_db(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS research_articles (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          source TEXT NOT NULL,
          source_type TEXT NOT NULL,
          url TEXT NOT NULL UNIQUE,
          canonical_url TEXT NOT NULL,
          url_hash TEXT NOT NULL UNIQUE,
          title TEXT NOT NULL,
          description TEXT,
          author TEXT,
          published_at TEXT,
          modified_at TEXT,
          captured_at TEXT NOT NULL,
          language TEXT NOT NULL DEFAULT 'zh-TW',
          article_section TEXT,
          image_url TEXT,
          word_count INTEGER,
          summary TEXT,
          full_text TEXT NOT NULL,
          raw_html_sha256 TEXT NOT NULL,
          content_sha256 TEXT NOT NULL,
          metadata_json TEXT NOT NULL DEFAULT '{}',
          created_at TEXT NOT NULL DEFAULT (datetime('now')),
          updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS research_article_symbols (
          article_id INTEGER NOT NULL,
          symbol TEXT NOT NULL,
          name TEXT NOT NULL,
          market TEXT,
          industry_name TEXT,
          context TEXT,
          created_at TEXT NOT NULL DEFAULT (datetime('now')),
          PRIMARY KEY (article_id, symbol),
          FOREIGN KEY (article_id) REFERENCES research_articles(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS research_article_topics (
          article_id INTEGER NOT NULL,
          topic TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT (datetime('now')),
          PRIMARY KEY (article_id, topic),
          FOREIGN KEY (article_id) REFERENCES research_articles(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_research_articles_source
          ON research_articles(source, published_at DESC);
        CREATE INDEX IF NOT EXISTS idx_research_article_symbols_symbol
          ON research_article_symbols(symbol, article_id);
        CREATE INDEX IF NOT EXISTS idx_research_article_topics_topic
          ON research_article_topics(topic, article_id);
        CREATE VIRTUAL TABLE IF NOT EXISTS research_articles_fts USING fts5(
          title, description, summary, full_text,
          content='research_articles',
          content_rowid='id',
          tokenize='unicode61'
        );
        """
    )


def upsert_article(conn, article):
    conn.execute(
        """
        INSERT INTO research_articles (
          source, source_type, url, canonical_url, url_hash, title, description,
          author, published_at, modified_at, captured_at, language,
          article_section, image_url, word_count, summary, full_text,
          raw_html_sha256, content_sha256, metadata_json, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(url) DO UPDATE SET
          canonical_url=excluded.canonical_url,
          title=excluded.title,
          description=excluded.description,
          author=excluded.author,
          published_at=excluded.published_at,
          modified_at=excluded.modified_at,
          captured_at=excluded.captured_at,
          language=excluded.language,
          article_section=excluded.article_section,
          image_url=excluded.image_url,
          word_count=excluded.word_count,
          summary=excluded.summary,
          full_text=excluded.full_text,
          raw_html_sha256=excluded.raw_html_sha256,
          content_sha256=excluded.content_sha256,
          metadata_json=excluded.metadata_json,
          updated_at=excluded.updated_at
        """,
        (
            article["source"],
            article["source_type"],
            article["url"],
            article["canonical_url"],
            article["url_hash"],
            article["title"],
            article["description"],
            article["author"],
            article["published_at"],
            article["modified_at"],
            article["captured_at"],
            article["language"],
            article["article_section"],
            article["image_url"],
            article["word_count"],
            article["summary"],
            article["full_text"],
            article["raw_html_sha256"],
            article["content_sha256"],
            article["metadata_json"],
            article["updated_at"],
        ),
    )
    article_id = conn.execute("SELECT id FROM research_articles WHERE url = ?", (article["url"],)).fetchone()[0]
    conn.execute("DELETE FROM research_article_symbols WHERE article_id = ?", (article_id,))
    conn.execute("DELETE FROM research_article_topics WHERE article_id = ?", (article_id,))
    for item in article["symbols"]:
        conn.execute(
            """
            INSERT INTO research_article_symbols (
              article_id, symbol, name, market, industry_name, context
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                article_id,
                item["symbol"],
                item["name"],
                item.get("market"),
                item.get("industry_name"),
                item.get("context"),
            ),
        )
    for topic in article["topics"]:
        conn.execute(
            "INSERT INTO research_article_topics (article_id, topic) VALUES (?, ?)",
            (article_id, topic),
        )
    conn.execute("INSERT INTO research_articles_fts(research_articles_fts) VALUES('rebuild')")
    return article_id


def build_article(url, html, market_db, extra_topics):
    json_ld = extract_json_ld(html)
    blog = next(
        (
            item
            for item in json_ld
            if isinstance(item, dict) and item.get("@type") == "BlogPosting"
        ),
        {},
    )
    text = extract_main_text(html)
    canonical_url = blog.get("url") or url
    author = blog.get("author")
    if isinstance(author, dict):
        author = author.get("name")
    image = blog.get("image")
    if isinstance(image, list):
        image = image[0] if image else None
    symbols = match_symbols(text, market_db)
    topics = match_topics((blog.get("description") or "") + "\n" + text, extra_topics)
    summary = "\n".join(
        [
            (blog.get("description") or meta_content(html, "description") or "").strip(),
            "Imported as an external research source for later review before Pilot_Reports enrichment.",
        ]
    ).strip()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    metadata = {
        "json_ld": blog,
        "source_request_url": url,
        "raw_html_length": len(html),
        "extracted_text_length": len(text),
        "symbols_json": symbols,
        "topics_json": topics,
    }
    return {
        "source": infer_source(canonical_url),
        "source_type": "blog",
        "url": url,
        "canonical_url": canonical_url,
        "url_hash": hashlib.sha256(canonical_url.encode("utf-8")).hexdigest(),
        "title": extract_title(html, blog),
        "description": blog.get("description") or meta_content(html, "description") or meta_content(html, "og:description"),
        "author": author,
        "published_at": blog.get("datePublished") or meta_content(html, "article:published_time"),
        "modified_at": blog.get("dateModified") or meta_content(html, "article:modified_time"),
        "captured_at": now,
        "language": blog.get("inLanguage") or "zh-TW",
        "article_section": blog.get("articleSection"),
        "image_url": image,
        "word_count": int(blog.get("wordCount") or 0),
        "summary": summary,
        "full_text": text,
        "raw_html_sha256": hashlib.sha256(html.encode("utf-8")).hexdigest(),
        "content_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "metadata_json": json.dumps(metadata, ensure_ascii=False),
        "updated_at": now,
        "symbols": symbols,
        "topics": topics,
    }


def main():
    setup_stdout()
    parser = argparse.ArgumentParser(description="Import a research article into SQLite.")
    parser.add_argument("url", help="Article URL to import")
    parser.add_argument("--db", default=DEFAULT_DB, help=f"SQLite DB path. Default: {DEFAULT_DB}")
    parser.add_argument("--market-db", default=DEFAULT_MARKET_DB, help="tw_market.sqlite path for ticker/name matching")
    parser.add_argument("--topic", action="append", default=[], help="Extra topic tag; can be repeated")
    args = parser.parse_args()

    html = fetch_url(args.url)
    article = build_article(args.url, html, args.market_db, args.topic)
    os.makedirs(os.path.dirname(os.path.abspath(args.db)), exist_ok=True)
    conn = sqlite3.connect(args.db)
    conn.execute("PRAGMA foreign_keys = ON")
    init_db(conn)
    article_id = upsert_article(conn, article)
    conn.commit()
    print(f"Imported article_id={article_id}: {article['title']}")
    print(f"DB: {args.db}")
    print(f"Symbols: {len(article['symbols'])}")
    print(f"Topics: {len(article['topics'])}")


if __name__ == "__main__":
    main()
