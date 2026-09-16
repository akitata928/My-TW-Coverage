# My-TW-Coverage Reset Handoff

## 2026-08-26 最新 checkpoint（新 session 先讀）

- Repo：https://github.com/akitata928/My-TW-Coverage
- 本機位置：repos/My-TW-Coverage
- 分支／狀態：master，目前 clean，追蹤 origin/master；最近 commit
  875d223（2026-07-19，修正 3046／3622 重複報告與 37 個未渲染 template title）。
- 目前內容：實際 Pilot_Reports 有 1,733 份 Markdown 報告、themes 有 21 份
  主題檔，network/ 有互動圖與 graph_data.json。README 宣稱涵蓋 1,735 家、
  99 個產業、4,900+ wikilinks；README 現載的品質稽核結果為 1,733/1,733
  （100%）通過。本次只是讀取既有結果，沒有重跑全量稽核或更新資料。
- task.md 的個別 Batch 條目目前都標為完成；但 Execution、Scale-Up／Batch
  Enrichment、Verification 的上層 phase 仍標 [/]，不可直接把整個專案標成
  「所有工作已正式結案」。

## 未完成／需要先釐清

1. **數量口徑不一致**：README／歷史 task.md 曾出現 1,735／1,737 的描述，但
   目前檔案計數與稽核分母是 1,733。先釐清缺少的兩份、歷史重複檔與預期 universe，
   再修改 README 或 task，不要用盲目新增報告來消除差異。
2. **Phase 標記尚未收斂**：個別批次完成不等於所有驗證、索引與產出都已重新核准；
   需依 CLAUDE.md 的品質規則決定是否補做一次可重現的全量 audit，並在確認後
   才更新 phase 標記。
3. **資料新鮮度**：財務與估值依賴 yfinance，研究／供應鏈內容是靜態人工整理；
   這是維護限制，不是目前已發現的 audit failure。

## 下一步（依序）

1. 先以 task.md、README.md、CLAUDE.md 為準備文件，釐清 1,733／1,735／1,737
   的數量差異及 phase [/] 的正式完成條件。
2. 若 Stan 要更新資料，再選定範圍執行 update_valuation.py、update_financials.py
   或 update_enrichment.py；每次變更後依規則做 audit，並視內容變更重建
   WIKILINKS.md、themes 與 network。
3. 不要在沒有明確資料範圍與品質驗證前，直接對全部 1,733 份報告做 yfinance
refresh 或 AI enrichment；那會製造大 diff、成本與難以回溯的變化。

## 2026-09-16 MOPS XBRL Phase 3A checkpoint

- Draft PR #2 分支：`plan/mops-xbrl-test-development`。
- Phase 3A SQLite migration、raw／semantic layer、產業 views、Python query 與去敏 multi-industry fixture 已完成；詳見 `docs/SQLITE_FINANCIAL_SCHEMA.md`。
- 離線驗證涵蓋 2330 一般產業、2882 金控、2801 銀行；SQLite `integrity_check=ok`、foreign key check 空、migration 可重跑且資料冪等。
- 尚未完成：正式金融業 MOPS concept mapping、保險／證券 fixture、2330＋金控＋銀行 live pilot。未下載全量資料，未修改 `Pilot_Reports/`。
- 本機環境沒有 pytest 模組；已以 `compileall`、`git diff --check` 與獨立 SQLite smoke test 驗證。安裝測試套件前需另行確認。

## 新 session 入口

cd /Users/stanchen/.openclaw/workspace/repos/My-TW-Coverage
sed -n '1,220p' RESET_HANDOFF.md

重要規則：以檔名的 ticker/company identity 為準、維持繁體中文、每份報告至少
8 個有效 wikilinks、保留財務表格、不得留 placeholder；不要把 credential、token
或本機資料庫提交進 repo。
