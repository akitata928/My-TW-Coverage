# Safe Run Guide

這份文件把常用指令分成「唯讀」、「會改檔」和「會連外」，方便在研究或二次實作前先判斷風險。

## 建議環境

使用專案自己的 Python virtual environment，不要把套件裝進系統 Python。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

離開環境：

```bash
deactivate
```

## 唯讀指令

這些指令只讀取 repo 內的 Markdown 或設定檔，不會修改檔案。

```bash
python scripts/audit_batch.py --all
python scripts/discover.py "CoWoS" --smart
python scripts/query_theme.py "CoWoS"
python scripts/query_theme.py "AI 伺服器" --format json
python scripts/build_themes.py --list
```

## 會產生或覆寫輸出檔

這些指令會改 repo 內的產物檔，執行前後建議看 `git status`。

```bash
python scripts/build_wikilink_index.py
python scripts/build_themes.py
python scripts/build_network.py
python scripts/build_network.py --min-weight 10
```

主要會動到：

- `WIKILINKS.md`
- `themes/*.md`
- `network/graph_data.json`
- `network/index.html`

## 會修改公司報告

這些指令會直接改 `Pilot_Reports/` 裡的公司 Markdown，建議先建立分支並確認 diff。

```bash
python scripts/discover.py "題材" --apply
python scripts/discover.py "題材" --apply --rebuild
python scripts/update_enrichment.py --data enrichment.json 2330
python scripts/add_ticker.py 2330 台積電
```

## 會連外抓資料

這些指令會透過 yfinance / Yahoo Finance 連外抓資料，也會在非 dry-run 模式改檔。

```bash
python scripts/update_valuation.py --dry-run 2330
python scripts/update_financials.py --dry-run 2330
python scripts/update_valuation.py 2330
python scripts/update_financials.py 2330
```

第一次研究時建議只跑 `--dry-run`，確認輸出符合預期再移除。

## 暫時不建議直接跑

歷史產生器保留了舊的 Windows 路徑與搬檔流程，不是主要工作流。

```bash
python scripts/generators/01_prototype.py
python scripts/generators/02_generate_base_reports.py
python scripts/generators/03_organize_reports.py
```

## 基本流程

每次要跑會改檔的指令前：

```bash
git status
```

跑完後：

```bash
git status
git diff --stat
```

如果只是研究，優先使用唯讀指令。若要維護自己的 fork，再把改檔流程納入 commit。
