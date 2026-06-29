# Financial Snapshots Plan

這份文件評估是否要把每檔個股 Markdown 裡的財務表拉出來，建立 SQLite 歷史資料庫，讓研究可以做時間序列觀察。

## 現況判斷

目前 `Pilot_Reports/*/*.md` 裡的 `## 財務概況` 是「最新版摘要」，不是歷史資料庫。

`scripts/update_financials.py` 的行為：

- 從 yfinance 抓最新年度與季度資料。
- 年度表保留近 3 年。
- 季度表保留近 4 季。
- 每次更新會替換整個 `## 財務概況` section。
- 不會保存「上一次更新時看到的數值」。

`scripts/update_valuation.py` 的行為：

- 只更新估值表，例如 P/E、Forward P/E、P/S、P/B、EV/EBITDA、股價。
- 保留既有年度 / 季度財務表。
- 同樣沒有保存歷史估值快照。

所以如果只靠 Markdown，會有兩個限制：

1. 舊快照會被覆蓋，無法看「資料庫在不同時間點看到什麼」。
2. 很難跨公司做時間序列篩選，例如最近 8 季毛利率、營益率、現金流趨勢。

## 結論

建議新增 SQLite，但不要取代 Markdown。

合理分工：

```text
Markdown
  = 人看的最新版公司摘要與供應鏈筆記

SQLite
  = 程式查詢用的歷史財務快照與時間序列資料
```

也就是說：

- `Pilot_Reports/` 繼續保留最新 3 年 / 4 季財務概況。
- SQLite 另外保存每次抓取的 raw snapshot 和標準化後的 metric rows。
- 研究查詢、趨勢比較、跨公司篩選，走 SQLite。

## 建議檔案位置

```text
data/
├── financial_snapshots.sqlite
└── README.md
```

`data/` 可先加入 `.gitignore`，避免把大型資料庫或可能衍生的快照檔直接提交。

如果未來要分享乾淨資料，可另外輸出：

```text
exports/
├── financial_metrics.parquet
├── financial_metrics.csv
└── valuation_snapshots.csv
```

## 建議 SQLite Schema

### companies

公司主檔，從檔名與 Markdown metadata 建立。

```sql
CREATE TABLE companies (
  ticker TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  sector TEXT,
  industry TEXT,
  report_path TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

### financial_metrics

標準化財務指標表，一列代表一家公司、一個期間、一個指標。

```sql
CREATE TABLE financial_metrics (
  ticker TEXT NOT NULL,
  period_type TEXT NOT NULL,      -- annual / quarterly
  period_end TEXT NOT NULL,       -- YYYY-MM-DD
  metric TEXT NOT NULL,           -- Revenue, Gross Profit, Net Income...
  value REAL,
  unit TEXT NOT NULL,             -- million_ntd / percent
  source TEXT NOT NULL,           -- yfinance / markdown
  fetched_at TEXT NOT NULL,
  PRIMARY KEY (ticker, period_type, period_end, metric, fetched_at)
);
```

### latest_financial_metrics

方便查詢的最新版視圖或表。

```sql
CREATE VIEW latest_financial_metrics AS
SELECT fm.*
FROM financial_metrics fm
JOIN (
  SELECT ticker, period_type, period_end, metric, MAX(fetched_at) AS fetched_at
  FROM financial_metrics
  GROUP BY ticker, period_type, period_end, metric
) latest
ON fm.ticker = latest.ticker
AND fm.period_type = latest.period_type
AND fm.period_end = latest.period_end
AND fm.metric = latest.metric
AND fm.fetched_at = latest.fetched_at;
```

### valuation_snapshots

估值是「抓取當下」的快照，和財報期間不同，應該獨立存。

```sql
CREATE TABLE valuation_snapshots (
  ticker TEXT NOT NULL,
  fetched_at TEXT NOT NULL,
  price REAL,
  trailing_pe REAL,
  forward_pe REAL,
  price_to_sales REAL,
  price_to_book REAL,
  ev_to_ebitda REAL,
  market_cap_million_ntd REAL,
  enterprise_value_million_ntd REAL,
  source TEXT NOT NULL,
  PRIMARY KEY (ticker, fetched_at)
);
```

### ingest_runs

記錄每次匯入或更新。

```sql
CREATE TABLE ingest_runs (
  run_id TEXT PRIMARY KEY,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  mode TEXT NOT NULL,             -- markdown / yfinance
  scope TEXT NOT NULL,            -- ticker / sector / all
  status TEXT NOT NULL,           -- success / partial / failed
  notes TEXT
);
```

## 兩種匯入模式

### Mode A: From Markdown

先把目前 1,735 份 `.md` 的財務表解析進 SQLite。

優點：

- 不連外。
- 很安全。
- 可快速建立 baseline。
- 可驗證 parser 和 schema 是否合理。

限制：

- 只能得到 Markdown 目前保存的近 3 年 / 4 季。
- 不會補回更久以前的資料。

建議先做這個。

### Mode B: From yfinance

把 `update_financials.py` 的抓取結果，同步寫進 SQLite。

優點：

- 每次更新都能留下新的 fetched_at 快照。
- 可建立真正的長期追蹤。
- 可保留 yfinance 後來修正過的歷史數字版本。

限制：

- 會連外。
- 批次抓 1,735 家會較慢，也可能遇到缺資料或 API 不穩。
- 需要節流和錯誤恢復。

建議第二階段再做。

## 最小可行版本

先做一支唯讀腳本：

```bash
python scripts/build_financial_sqlite.py --from-markdown
```

功能：

1. 掃描 `Pilot_Reports/**/*.md`。
2. 解析公司代號、公司名、sector、industry、report path。
3. 解析年度表與季度表。
4. 寫入 `data/financial_snapshots.sqlite`。
5. 產出匯入摘要。

第一版不需要改任何 Markdown，也不需要連外。

### MVP 實作狀態

已完成：

```bash
python scripts/build_financial_sqlite.py --from-markdown
```

目前會產生：

```text
data/financial_snapshots.sqlite
```

已實作：

- 掃描 `Pilot_Reports/**/*.md`
- 支援標準檔名 `2308_台達電.md`
- 支援少數反向檔名，例如 `洋華_3622.md`
- 解析公司主檔
- 解析年度關鍵財務數據
- 解析季度關鍵財務數據
- 解析估值快照
- 建立 `companies`
- 建立 `financial_metrics`
- 建立 `valuation_snapshots`
- 建立 `ingest_runs`
- 建立 `latest_financial_metrics` view
- `data/*.sqlite` 已加入 `.gitignore`

目前 baseline 匯入結果：

```text
reports: 1735
unique companies: 1733
financial metric rows: 163674
valuation rows: 1729
duplicate tickers collapsed: 3046, 3622
```

`3046` 與 `3622` 各有一份重複或異常檔名；SQLite 以 ticker 作為唯一公司主鍵，因此不會把它們算成兩家公司。

## 第二階段

讓 yfinance 更新流程多一個選項：

```bash
python scripts/update_financials.py 2330 --save-snapshot
python scripts/update_financials.py --sector Semiconductors --save-snapshot
```

或者獨立一支：

```bash
python scripts/fetch_financial_snapshots.py 2330
python scripts/fetch_financial_snapshots.py --sector Semiconductors
```

我比較建議獨立腳本，因為：

- Markdown 更新和 SQLite 快照是兩種不同目的。
- SQLite 失敗時不應影響 Markdown 更新。
- 之後比較容易排程，例如每週更新估值、每季更新財報。

## 第三階段：研究查詢

有 SQLite 後，可以做這些查詢：

```bash
python scripts/query_financials.py 2308 --metric "Gross Margin (%)"
python scripts/query_financials.py --sector "Electronic Components" --metric "Revenue" --period quarterly
python scripts/screen_financials.py --revenue-growth-yoy 20 --gross-margin-up
```

可支援的研究問題：

- 最近 4 季營收是否連續成長？
- 毛利率是否連續改善？
- 營業利益率是否高於同產業中位數？
- 自由現金流是否轉正？
- 高 P/B 是否被高 ROE 或成長支撐？
- 同一題材公司裡，誰的財務趨勢最好？

## 排程建議

```text
每日或每週：
  update_valuation / valuation_snapshots

每季財報公告後：
  financial_snapshots

研究新題材時：
  query_theme + query_financials 合併看
```

估值和股價變動快，適合比較頻繁。

年度 / 季度財報變動慢，不需要每天抓。

## 風險與注意事項

- yfinance 資料可能缺漏或修正，SQLite 要保留 `source` 和 `fetched_at`。
- 金融股財報欄位和電子股不同，不應硬套同一套毛利率 / 營益率邏輯。
- Markdown 表格裡的 `-` 要轉成 NULL，不要轉成 0。
- 單位要固定為 `million_ntd` 或 `percent`。
- 不要把 SQLite database 直接當成唯一真相，重要研究仍要回頭看財報與公開資訊觀測站。

## 我的建議

可以做，而且值得做。

但順序要保守：

1. 先做 `build_financial_sqlite.py --from-markdown`，建立 baseline。
2. 再做 `query_financials.py`，先能查單一公司與單一 metric。
3. 確認好用後，再接 yfinance snapshot。
4. 最後才做排程和篩選器。

這樣不會影響現有 Markdown，也能開始建立可回溯的財務時間序列。
