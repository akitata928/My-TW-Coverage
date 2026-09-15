# Phase 0 基線盤點

**日期：** 2026-09-15
**分支：** `phase0/mops-source-contract`
**目的：** 為 MOPS XBRL／TIFRS 測試建立可回溯基線；本文件不修改既有報告或財務表格。

## Repo 與執行環境

| 項目 | 實測結果 |
|---|---|
| Git HEAD（Phase 0 起點） | `0a304e7`（Draft PR #2 計畫文件） |
| Python（系統） | 3.14.6 |
| Python（repo `.venv`） | 3.9.6 |
| 依賴宣告 | `requirements.txt`：`yfinance`、`pandas`、`tabulate` |
| 既有測試套件 | repo 沒有既定 `tests/` 或 pytest 設定；以既有 audit script 作為 baseline check |
| 報告檔 | 1,733 個 `Pilot_Reports/**/*.md` |
| 產業目錄 | 98 個 |
| README 宣稱報告數 | 1,735 |
| task／verification 狀態 | Verification Phase 為 `[ / ]`；Unit Verification、Wikilinking 已標記完成 |

## 現有資料口徑差異

- 實際檔案盤點為 **1,733**。
- README 多處仍寫 **1,735**。
- Draft PR 計畫的風險清單提到 1,733／1,735／1,737 三種歷史口徑；本次沒有修改任何數量或報告檔。
- 既有品質 audit：`.venv/bin/python scripts/audit_batch.py --all`，結果 **1,733/1,733（100%）**，exit code 0。
- 這個 audit 是既有報告品質檢查，不等同於 MOPS XBRL 解析或財務數值正確性驗證。

## Phase 0 邊界

本階段只建立 baseline、來源契約與 fixture 安全規範；不下載全量財報、不寫 parser、不修改 `Pilot_Reports/`，也不把真實財報檔或登入狀態提交到 Git。
