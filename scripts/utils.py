"""
utils.py — Shared utilities for all scripts.

Provides: file discovery, batch parsing, scope parsing, wikilink normalization,
category classification, valuation table rendering, metadata updates.
"""

import os
import re
import sys
import glob
from datetime import date, datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(PROJECT_ROOT, "Pilot_Reports")
TASK_FILE = os.path.join(PROJECT_ROOT, "task.md")


# =============================================================================
# File Discovery
# =============================================================================

def find_ticker_files(tickers=None, sector=None):
    """Find report files matching given tickers or sector.
    Returns dict: {ticker: filepath}
    """
    files = {}
    for fp in glob.glob(os.path.join(REPORTS_DIR, "**", "*.md"), recursive=True):
        fn = os.path.basename(fp)
        m = re.match(r"^(\d{4})_", fn)
        if not m:
            continue
        t = m.group(1)

        if sector:
            folder = os.path.basename(os.path.dirname(fp))
            if folder.lower() != sector.lower():
                continue

        if tickers is None or t in tickers:
            files[t] = fp

    return files


def get_ticker_from_filename(filepath):
    """Extract ticker number and company name from a report filename."""
    fn = os.path.basename(filepath)
    m = re.match(r"^(\d{4})_(.+)\.md$", fn)
    if m:
        return m.group(1), m.group(2)
    return None, None


# =============================================================================
# Batch & Scope Parsing
# =============================================================================

def get_batch_tickers(batch_num):
    """Get ticker list for a batch from task.md."""
    try:
        with open(TASK_FILE, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading task.md: {e}")
        return []

    pattern = re.compile(
        r"Batch\s+" + str(batch_num) + r"\*\*.*?:[:\s]*(.*)$",
        re.IGNORECASE | re.MULTILINE,
    )
    match = pattern.search(content)
    if match:
        raw = match.group(1).strip().rstrip(".")
        return [
            re.search(r"(\d{4})", t).group(1)
            for t in raw.split(",")
            if re.search(r"\d{4}", t)
        ]
    print(f"Error: Batch {batch_num} not found in task.md")
    return []


def parse_scope_args(args):
    """Parse CLI arguments into scope: tickers list, sector, or None (all).
    Returns (tickers_list_or_None, sector_or_None, description_string)
    """
    if not args:
        return None, None, "ALL tickers"
    elif args[0] == "--batch":
        if len(args) < 2:
            print("Error: --batch requires a batch number")
            sys.exit(1)
        batch_num = args[1]
        tickers = get_batch_tickers(batch_num)
        return tickers, None, f"{len(tickers)} tickers in Batch {batch_num}"
    elif args[0] == "--sector":
        if len(args) < 2:
            print("Error: --sector requires a sector name")
            sys.exit(1)
        sector = " ".join(args[1:])
        return None, sector, f"all tickers in sector: {sector}"
    else:
        tickers = [t.strip() for t in args if re.match(r"^\d{4}$", t.strip())]
        return tickers, None, f"{len(tickers)} tickers: {', '.join(tickers)}"


def setup_stdout():
    """Configure stdout for UTF-8 on Windows."""
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# =============================================================================
# Wikilink Aliases
# =============================================================================

# Canonical name mapping: alias -> canonical
# Taiwan companies use Chinese, foreign companies use English
WIKILINK_ALIASES = {
    # Taiwan companies: English -> Chinese
    "TSMC": "台積電", "MediaTek": "聯發科", "Foxconn": "鴻海",
    "UMC": "聯電", "ASE": "日月光投控", "SPIL": "矽品",
    "Pegatron": "和碩", "Compal": "仁寶", "Quanta": "廣達",
    "Wistron": "緯創", "Inventec": "英業達",
    "ASUS": "華碩", "Acer": "宏碁", "Realtek": "瑞昱",
    "Novatek": "聯詠", "Himax": "奇景光電",
    "AUO": "友達", "Innolux": "群創",
    "Yageo": "國巨", "GlobalWafers": "環球晶",
    "KYEC": "京元電子", "ChipMOS": "南茂",
    "Unimicron": "欣興", "Delta": "台達電", "Lite-On": "光寶",
    "Largan": "大立光", "CTCI": "中鼎", "PTI": "力成",
    "WIN Semi": "穩懋", "Walsin": "華新科",
    "日月光": "日月光投控", "臻鼎": "臻鼎-KY",
    "消費電子": "消費性電子", "儲能": "儲能系統",
    # Foreign companies: Chinese -> English
    "艾司摩爾": "ASML", "應用材料": "Applied Materials", "AMAT": "Applied Materials",
    "東京威力": "Tokyo Electron", "TEL": "Tokyo Electron",
    "科林研發": "Lam Research", "科磊": "KLA", "愛德萬": "Advantest",
    "英特爾": "Intel", "高通": "Qualcomm", "博通": "Broadcom",
    "輝達": "NVIDIA", "美光": "Micron", "海力士": "SK Hynix",
    "英飛凌": "Infineon", "恩智浦": "NXP", "瑞薩": "Renesas",
    "德州儀器": "Texas Instruments", "意法半導體": "STMicroelectronics",
    "安森美": "ON Semiconductor",
    "蘋果": "Apple", "三星": "Samsung", "索尼": "Sony",
    "谷歌": "Google", "微軟": "Microsoft", "特斯拉": "Tesla",
    "亞馬遜": "Amazon", "戴爾": "Dell", "惠普": "HP",
    "聯想": "Lenovo", "思科": "Cisco",
    "新思": "Synopsys", "益華": "Cadence", "安謀": "Arm", "ARM": "Arm",
    "博世": "Bosch", "電裝": "Denso",
    "信越": "Shin-Etsu", "信越化學": "Shin-Etsu",
    "Sumco": "SUMCO", "味之素": "Ajinomoto",
    "西門子": "Siemens", "霍尼韋爾": "Honeywell", "漢威": "Honeywell",
    "勞斯萊斯": "Rolls-Royce", "奇異": "GE Aerospace",
    "耐吉": "Nike", "耐克": "Nike", "愛迪達": "Adidas", "戴森": "Dyson",
    # Tech terms: standardize
    "SiC": "碳化矽", "GaN": "氮化鎵", "InP": "磷化銦", "GaAs": "砷化鎵",
    "共封裝光學": "CPO", "Co-Packaged Optics": "CPO",
    "IoT": "物聯網", "EV": "電動車", "印刷電路板": "PCB",
}


# =============================================================================
# Category Classification (shared by build_wikilink_index, build_themes, build_network)
# =============================================================================

TECH_TERMS = {
    "AI", "PCB", "5G", "HBM", "CoWoS", "InFO", "EUV", "CPO", "FOPLP",
    "VCSEL", "EML", "MLCC", "MOSFET", "IGBT", "DRAM", "NAND", "SSD",
    "DDR5", "DDR4", "PCIe", "USB", "Wi-Fi", "Bluetooth",
    "OLED", "AMOLED", "Mini LED", "Micro LED",
    "MCU", "SoC", "ASIC", "FPGA", "RF", "IC", "LED", "LCD", "TFT",
    "CMP", "CVD", "PVD", "ALD", "AOI", "SMT", "BGA", "QFN", "SOP",
    "ABF 載板", "BT 載板", "ABF", "SerDes", "PMIC", "LDO",
    "TSV", "RDL", "WLCSP", "FC-BGA", "FCCSP",
    "NOR Flash", "NAND Flash", "eMMC", "UFS",
    "MEMS", "CIS", "ToF", "LiDAR", "TFT-LCD",
    "矽光子", "光收發模組",
    "磊晶", "蝕刻", "微影", "封裝測試", "晶圓代工", "IC 設計",
    "2.5D 封裝", "3D 封裝", "第三代半導體",
    "連接器", "被動元件",
    "散熱模組", "散熱片", "散熱鰭片", "散熱風扇", "散熱基板",
    "均熱片", "均熱板", "熱管", "液冷散熱", "浸沒式散熱",
    "導熱膏", "熱介面材料",
}

MATERIAL_TERMS = {
    "碳化矽", "氮化鎵", "磷化銦", "砷化鎵", "矽晶圓",
    "銅箔", "玻纖布", "光阻液", "研磨液", "超純水",
    "氦氣", "氖氣", "鈦酸鋇", "聚醯亞胺",
    "導線架", "探針卡", "BT 樹脂", "銀漿", "銅漿", "氧化鋁",
}

APPLICATION_TERMS = {
    "AI 伺服器", "電動車", "物聯網", "資料中心", "低軌衛星",
    "智慧家庭", "車用電子", "綠能", "太陽能",
    "風電", "儲能系統", "離岸風電", "自動駕駛", "智慧城市",
    "行車記錄器", "無人機",
    "伺服器", "工業電腦", "消費性電子", "機器人", "光通訊",
}

# Category words that must never be wikilinked (CLAUDE.md rule 1: wikilinks are
# specific proper nouns). These stay useful as plain-text context, so
# normalize_wikilinks unlinks them rather than deleting the words. Terms that
# looked generic but are real Taiwan market segments — 連接器, 工業電腦,
# IC 設計 — moved into the sets above instead; the test is whether the label
# narrows a search, not whether it is a common noun.
GENERIC_TERMS = {
    "半導體", "記憶體", "散熱", "自動化", "網通",
    "面板", "電源供應器", "雲端服務",
}

CATEGORY_COLORS = {
    "taiwan_company": "#e74c3c",
    "international_company": "#3498db",
    "technology": "#2ecc71",
    "material": "#f39c12",
    "application": "#9b59b6",
    "generic": "#7f8c8d",
}

CATEGORY_LABELS = {
    "taiwan_company": "台灣公司",
    "international_company": "國際公司",
    "technology": "技術/標準",
    "material": "材料/基板",
    "application": "終端應用",
    "generic": "泛稱 (待收斂)",
}


def is_cjk(s):
    """Check if a string is primarily CJK characters."""
    return sum(1 for c in s if "\u4e00" <= c <= "\u9fff") > len(s) * 0.3


def classify_wikilink(name):
    """Classify a wikilink into a category."""
    if name in TECH_TERMS:
        return "technology"
    if name in MATERIAL_TERMS:
        return "material"
    if name in APPLICATION_TERMS:
        return "application"
    if name in GENERIC_TERMS:
        return "generic"
    if is_cjk(name):
        return "taiwan_company"
    return "international_company"


# =============================================================================
# Wikilink Normalization
# =============================================================================

# Preferred surface form for entities that appeared under several spellings.
# Only the winner is listed: the index below matches any case/separator variant.
CANONICAL_FORMS = (
    "AI 伺服器", "3D 列印", "Aisin", "ASICS", "Coach", "DeWalt", "E-Bike",
    "Elan", "Epson", "Fanuc", "GAP", "Hill-Rom", "Hoka", "Honda", "HOYA",
    "IC 載板", "IP Camera", "JCPenney", "Lululemon", "Micro LED", "Momo",
    "Nichicon", "Nippon Chemi-Con", "Ohara", "Omron", "ON Semi", "Osram",
    "Pfaff", "PING", "PUMA", "PU 合成皮", "Rohm", "rPET", "Schott", "Shimano",
    "Singer", "Tata", "TFT-LCD", "Uniqlo", "VeriFone", "Visa", "vivo",
    "Williams-Sonoma", "Yamaha", "Zara",
)

# Case carries meaning for these, so they are kept out of the folding index:
# [[SOC]] in 6690_安碁資訊 is a security operations centre, not [[SoC]].
CASE_SENSITIVE_TERMS = {"SoC"}

WIKILINK_RE = re.compile(r"\[\[([^\[\]]+)\]\]")

# discover.py used to tag a bare substring that already sat inside a link,
# producing one level of nesting such as [[AI[[伺服器]]]] or [[精[[聯電]]子]].
# Both the repair pass and every write path flatten it back to a single link.
_NESTED_WIKILINK_RE = re.compile(r"\[\[(?:[^\[\]]|\[\[[^\[\]]*\]\])*?\]\]")


def _surface_key(name):
    """Case- and separator-insensitive key used to merge spelling variants."""
    return re.sub(r"[\s\-_·.]", "", name).lower()


# Any registered canonical name also matches its own variants, so "Nvidia",
# "MicroLED", and "AI伺服器" collapse without one alias entry per spelling.
_CANONICAL_BY_KEY = {}
for _name, _canonical in (
    list(WIKILINK_ALIASES.items())
    + [(c, c) for c in WIKILINK_ALIASES.values()]
    + [(c, c) for c in CANONICAL_FORMS]
    + [(t, t) for t in TECH_TERMS | MATERIAL_TERMS | APPLICATION_TERMS]
):
    if _canonical in CASE_SENSITIVE_TERMS:
        continue
    _CANONICAL_BY_KEY.setdefault(_surface_key(_name), _canonical)


def canonical_wikilink(name):
    """Map a wikilink surface form to its canonical name."""
    return _CANONICAL_BY_KEY.get(_surface_key(name), name)


# A link that covers only the head of a longer name, e.g. [[散熱]]模組 or
# [[AI]] [[伺服器]]. Absorption is self-limiting: the merged text must already
# be a registered canonical term AND must resolve to something other than the
# head alone, so this can neither invent a node nor swallow trailing spaces
# (_surface_key ignores whitespace, so "台積電 " would otherwise look like a hit).
_FRAGMENT_RE = re.compile(r"\[\[([^\[\]]+)\]\]([\u4e00-\u9fffA-Za-z]{1,5})")
_BRIDGED_RE = re.compile(r"\[\[([^\[\]]+)\]\]\s*\[\[([^\[\]]+)\]\]")


def _absorbed(head, suffix):
    """Canonical name for head+suffix, or None if that is not a known term."""
    merged = canonical_wikilink(head + suffix)
    if _surface_key(head + suffix) not in _CANONICAL_BY_KEY:
        return None
    return merged if merged != canonical_wikilink(head) else None


def absorb_fragment_links(text):
    """Extend a link that stops short of the full registered term."""

    def bridged(m):
        merged = _absorbed(m.group(1), " " + m.group(2))
        return f"[[{merged}]]" if merged else m.group(0)

    def fragment(m):
        head, tail = m.group(1), m.group(2)
        for n in range(len(tail), 0, -1):
            merged = _absorbed(head, tail[:n])
            if merged:
                return f"[[{merged}]]" + tail[n:]
        return m.group(0)

    return _FRAGMENT_RE.sub(fragment, _BRIDGED_RE.sub(bridged, text))


def unlink_generic_terms(text):
    """Strip brackets from category words, keeping them as plain-text context."""
    return WIKILINK_RE.sub(
        lambda m: m.group(1) if m.group(1) in GENERIC_TERMS else m.group(0), text
    )


# This database's convention is a bare [[name]] that resolves to an entity note
# of the same name; Obsidian's piped form [[path|label]] hard-codes a file path
# into the prose, and WIKILINK_RE reads the whole "path|label" as one node name.
_PIPED_RE = re.compile(r"\[\[([^\[\]|]+)\|([^\[\]|]+)\]\]")


def unpipe_wikilinks(text):
    """Reduce [[2330_台積電|台積電]] to [[台積電]] — the label is the entity."""
    return _PIPED_RE.sub(lambda m: "[[" + m.group(2).strip() + "]]", text)


def flatten_nested_wikilinks(text):
    """Collapse a link that swallowed another link: [[A[[B]]C]] -> [[ABC]]."""

    def repl(m):
        inner = m.group(0)[2:-2]
        if "[[" not in inner:
            return m.group(0)
        return "[[" + inner.replace("[[", "").replace("]]", "") + "]]"

    return _NESTED_WIKILINK_RE.sub(repl, text)


def normalize_wikilinks(content):
    """Normalize all wikilinks in content to canonical names.

    Flattens nested links, maps aliases and spelling variants to the canonical
    form, and collapses duplicate parentheticals like [[X]] ([[X]]).
    Only operates on text before 財務概況 to protect financial tables.
    """
    head, sep, tail = content.partition("## 財務概況")

    head = unpipe_wikilinks(head)
    head = flatten_nested_wikilinks(head)
    # Absorb before unlinking: [[散熱]]模組 must become [[散熱模組]] rather than
    # losing its brackets as a bare category word.
    head = absorb_fragment_links(head)
    head = WIKILINK_RE.sub(lambda m: "[[" + canonical_wikilink(m.group(1)) + "]]", head)
    head = unlink_generic_terms(head)

    # Collapse [[X]] ([[X]]) duplicate parentheticals
    head = re.sub(
        r"\[\[([^\]]+)\]\]\s*[\(（]\[\[([^\]]+)\]\][\)）]",
        lambda m: f"[[{m.group(1)}]]" if m.group(1) == m.group(2) else m.group(0),
        head,
    )

    return head + sep + tail


# =============================================================================
# Valuation Table Rendering (shared by update_financials and update_valuation)
# =============================================================================

def fetch_valuation_data(info):
    """Extract valuation multiples from yfinance info dict.
    Returns dict with display values and metadata.
    """
    valuation = {}
    for key, label in [
        ("trailingPE", "P/E (TTM)"),
        ("forwardPE", "Forward P/E"),
        ("priceToSalesTrailing12Months", "P/S (TTM)"),
        ("priceToBook", "P/B"),
        ("enterpriseToEbitda", "EV/EBITDA"),
    ]:
        val = info.get(key)
        valuation[label] = f"{val:.2f}" if val else "N/A"

    # Price
    cur_price = info.get("currentPrice")
    valuation["_price"] = f"{cur_price:,.2f}" if cur_price else None

    # Period info
    mrq = info.get("mostRecentQuarter")
    nfy = info.get("nextFiscalYearEnd")
    valuation["_ttm_end"] = (
        datetime.fromtimestamp(mrq).strftime("%Y-%m-%d") if mrq else None
    )
    valuation["_fwd_end"] = (
        datetime.fromtimestamp(nfy).strftime("%Y-%m-%d") if nfy else None
    )

    return valuation


def build_valuation_table(v):
    """Build the 估值指標 markdown section from valuation dict."""
    headers = ["P/E (TTM)", "Forward P/E", "P/S (TTM)", "P/B", "EV/EBITDA"]
    values = [v.get(h, "N/A") for h in headers]
    widths = [max(len(h), len(val)) for h, val in zip(headers, values)]
    header_row = "| " + " | ".join(h.rjust(w) for h, w in zip(headers, widths)) + " |"
    sep_row = "|" + "|".join("-" * (w + 2) for w in widths) + "|"
    val_row = "| " + " | ".join(val.rjust(w) for val, w in zip(values, widths)) + " |"

    today = date.today().strftime("%Y-%m-%d")
    period_parts = []
    if v.get("_price"):
        period_parts.append(f"股價 ${v['_price']} as of {today}")
    if v.get("_ttm_end"):
        period_parts.append(f"TTM 截至 {v['_ttm_end']}")
    if v.get("_fwd_end"):
        period_parts.append(f"Forward 預估至 {v['_fwd_end']}")
    period_note = " | ".join(period_parts) if period_parts else ""

    title = f"### 估值指標 ({period_note})\n" if period_note else "### 估值指標\n"
    return title + header_row + "\n" + sep_row + "\n" + val_row


# Frontmatter mirrors the 業務簡介 metadata block so Obsidian's Dataview can
# filter and sort on it. update_metadata writes both, so the two cannot drift.
FRONTMATTER_FIELDS = ("ticker", "company", "sector", "industry",
                      "market_cap", "enterprise_value")

_BODY_METADATA = {
    "sector": re.compile(r"\*\*板塊:\*\* *(.+)"),
    "industry": re.compile(r"\*\*產業:\*\* *(.+)"),
    "market_cap": re.compile(r"\*\*市值:\*\* *([\d,]+|N/A)"),
    "enterprise_value": re.compile(r"\*\*企業價值:\*\* *([\d,]+|N/A)"),
}

_FRONTMATTER_BLOCK = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)


def _numeric(value):
    """Dataview needs a bare number to compare on; N/A stays absent."""
    plain = value.replace(",", "")
    return plain if plain.isdigit() else None


def apply_frontmatter(content, ticker, company):
    """Insert or refresh the YAML frontmatter from the body metadata block."""
    fields = {"ticker": f'"{ticker}"', "company": company}
    for key, pattern in _BODY_METADATA.items():
        match = pattern.search(content)
        if not match:
            continue
        raw = match.group(1).strip()
        value = _numeric(raw) if key.endswith(("cap", "value")) else raw
        if value:
            fields[key] = value

    block = "---\n" + "".join(
        f"{k}: {fields[k]}\n" for k in FRONTMATTER_FIELDS if k in fields
    ) + "---\n"

    if _FRONTMATTER_BLOCK.match(content):
        return _FRONTMATTER_BLOCK.sub(block, content, count=1)
    return block + content


def update_metadata(content, market_cap, enterprise_value):
    """Update 市值 and 企業價值 in the body and in the frontmatter mirror."""
    for label, key, value in (
        ("市值", "market_cap", market_cap),
        ("企業價值", "enterprise_value", enterprise_value),
    ):
        if not value:
            continue
        content = re.sub(
            rf"(\*\*{label}:\*\*) .+?百萬台幣",
            rf"\1 {value} 百萬台幣",
            content,
        )
        numeric = _numeric(str(value))
        if numeric:
            content = re.sub(
                rf"^{key}: .*$", f"{key}: {numeric}", content, count=1, flags=re.M
            )
    return content


# =============================================================================
# Financial Parsing (for screening)
# =============================================================================

# The 估值指標 table is rendered right-aligned with a fixed column order, so the
# values row is read positionally rather than by header.
_VALUATION_ROW = re.compile(
    r"### 估值指標[^\n]*\n\|[^\n]*\n\|[-|\s]*\n\|([^\n]*)\|"
)
_VALUATION_KEYS = ("pe", "forward_pe", "ps", "pb", "ev_ebitda")

_ANNUAL_TABLE = re.compile(r"### 年度關鍵財務數據[^\n]*\n(.*?)(?=\n###|\n##|\Z)", re.DOTALL)

# Latest period is the first numeric column of the annual table.
_MARGIN_ROWS = {
    "gross_margin": "Gross Margin (%)",
    "operating_margin": "Operating Margin (%)",
    "net_margin": "Net Margin (%)",
    "revenue": "Revenue",
}


def _as_float(cell):
    cell = cell.strip().replace(",", "")
    try:
        return float(cell)
    except ValueError:
        return None


def parse_financials(content):
    """Extract the screenable numbers from a report. Missing values are None."""
    out = {k: None for k in _VALUATION_KEYS}
    out.update({k: None for k in _MARGIN_ROWS})

    match = _VALUATION_ROW.search(content)
    if match:
        cells = [c for c in match.group(1).split("|")]
        for key, cell in zip(_VALUATION_KEYS, cells):
            out[key] = _as_float(cell)

    annual = _ANNUAL_TABLE.search(content)
    if annual:
        for line in annual.group(1).split("\n"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 2:
                continue
            for key, label in _MARGIN_ROWS.items():
                if cells[0] == label:
                    out[key] = _as_float(cells[1])

    front = re.search(r"^market_cap: *(\d+)", content, re.M)
    out["market_cap"] = float(front.group(1)) if front else None
    return out


# =============================================================================
# Section Replacement
# =============================================================================

def replace_section(content, section_header, new_body, next_section_header=None):
    """Replace content between section_header and next_section_header.
    If next_section_header is None, replaces to end of file.
    """
    if next_section_header:
        pattern = rf"({re.escape(section_header)}\n)(.*?)(?=\n{re.escape(next_section_header)})"
        return re.sub(pattern, rf"\g<1>{new_body}\n", content, flags=re.DOTALL)
    else:
        pattern = rf"{re.escape(section_header)}.*"
        return re.sub(pattern, f"{section_header}\n{new_body}\n", content, flags=re.DOTALL)
