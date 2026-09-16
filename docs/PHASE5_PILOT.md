# Phase 5：pipeline 整合與單季 pilot

## 交付範圍

Phase 5 將 MOPS XBRL transport、cache、parser boundary、canonical output 與本機分析介面串成可重跑的 pilot 流程。Perch 不再是 MVP 依賴或 Gate。

SQLite semantic layer 依 `docs/SQLITE_FINANCIAL_SCHEMA.md` 採原始長表、版本化 concept mapping 與產業 views。一般製造／科技、金控、銀行、保險、證券不得共用單一固定寬表；未知科目保留為 unknown／NULL，不補零。

正式 runtime cache 應放在 repo 外，例如：

```text
~/.openclaw/data/my-tw-coverage/mops_xbrl/
```

`MopsXbrlAdapter` 只保存指定 cache 目錄中的 raw bytes、sanitized metadata 與 JSONL event log；它不會把 raw 財報或 cache sidecar 寫入 Git。相同工作鍵在 raw bytes 與 metadata hash 通過時直接 cache hit，避免重複下載。

## 錯誤與隔離政策

- transport 層沿用 Phase 1 的 TLS、有限退避與 `http_403`／`timeout`／`network_error`／空內容／非 XBRL 分類。
- fetch 失敗與 parser 失敗分開記錄；單一公司失敗不會寫出 partial canonical output，也不會阻擋其他 pilot job。
- 每個成功 job 保留來源 URL、抓取時間與 raw input SHA-256；結果 manifest 以穩定排序輸出，支援重跑比對。
- canonical JSON／CSV 交給 `scripts/local_analysis.py` 做 import、query、Decimal calculation 與 provenance；不需要 Perch runtime。
- canonical JSON／CSV 仍是匯入／匯出邊界；SQLite 是本機持久化分析後端，不需要 Perch runtime。
- 第一輪 live pilot 建議為 2330（一般製造／科技）＋一家金控＋一家銀行，單一季度合併報表；保險與證券列為第二輪。
- pilot 只允許 3 家以內、單一季度；不執行全量下載，不修改 `Pilot_Reports/`。

## 驗證結果

- 離線 pilot harness 已以成功與 HTTP 403 fixture job 驗證成功／失敗隔離。
- 相同成功 job 重跑會產生 `cache_hit` event，probe 不會再次呼叫。
- 目前尚未宣稱多產業 SQLite migration、金融業 mapping 或上述 live pilot 已完成；這些是下一個獨立 Gate。
- 完整測試與既有資料 audit 由 PR comment 記錄；目前未提交任何 raw MOPS 財報。

## 尚未宣稱

這個 Phase 5 交付是可測試的 pipeline／pilot 骨架，不是正式全量同步，也不代表所有 MOPS 報表 function 或所有公司的來源可用。正式啟用前仍須由獨立決策確認 SQLite migration、mapping fixture、公司範圍、季度、排程與 runtime DB 路徑。保險與證券需另行驗證 IFRS 17 及各自業務科目後才納入。
