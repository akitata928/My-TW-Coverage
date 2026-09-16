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
- canonical JSON／CSV 先由 `scripts/sqlite_financial.py import-canonical --csv-input` 做全欄位一致性檢查，再匯入 SQLite；`query`、`quality` 與 Python Decimal calculation 保留 provenance，不需要 Perch runtime。
- canonical JSON／CSV 仍是匯入／匯出邊界；SQLite 是本機持久化分析後端，不需要 Perch runtime。
- 第一輪 live pilot 建議為 2330（一般製造／科技）＋一家金控＋一家銀行，單一季度合併報表；保險與證券列為第二輪。
- pilot 只允許 3 家以內、單一季度；不執行全量下載，不修改 `Pilot_Reports/`。

## 驗證結果

- 離線 pilot harness 已以成功與 HTTP 403 fixture job 驗證成功／失敗隔離。
- 相同成功 job 重跑會產生 `cache_hit` event，probe 不會再次呼叫。
- 多產業 SQLite migration、離線 fixture、本機 query、quality report、JSON／CSV mismatch rejection 與 Decimal/provenance 已完成；金融業正式 MOPS mapping 與上述 live pilot 仍是下一個獨立 Gate。
- 2026 Q2／report_id=C／`t164sb01` live pilot 已完成：2330、2882、2801 均 HTTP 200、Arelle 2.45.1 解析成功，分別產出 1,102、957、1,711 numeric facts；三家公司均匯入同一個 repo 外 SQLite，`integrity_check=ok`、foreign key check 為空。
- Pilot mapping registry `mops-tifrs-2026-09-pilot-1` 僅提供 exact-name provisional anchors；覆蓋率為 2330：75 provisional／1,027 unknown、2882：102／855、2801：66／1,645。所有 unknown 保留原始 QName 並產生 warning。
- Arelle diagnostics 仍為 2,669／3,489／2,542，因官方 taxonomy／label linkbase 未納入 runtime；`label_zh_tw` 維持 unavailable，未宣稱中文標籤或完整 semantic mapping 已驗證。
- 新增 exact-name statement anchors：只將少數可明確辨識的 Assets／Liabilities／Equity、金融資產／存款／放款、利息與現金流 anchor 分類；其餘 facts 仍為 `statement_type=unknown`，不以子字串推斷。
- 局部分類結果：2330 `67/8/8/1,019`、2882 `106/4/8/839`、2801 `68/4/8/1,631`（balance／income／cash flow／unknown）。
- 完整測試與既有資料 audit 由 PR comment 記錄；目前未提交任何 raw MOPS 財報。

## 尚未宣稱

這個 Phase 5 交付是可測試的 pipeline／pilot 骨架，不是正式全量同步，也不代表所有 MOPS 報表 function 或所有公司的來源可用。正式啟用前仍須由獨立決策確認 SQLite migration、mapping fixture、公司範圍、季度、排程與 runtime DB 路徑。保險與證券需另行驗證 IFRS 17 及各自業務科目後才納入。此輪 canonical live output 的 `period_role`、`accumulation`、`restatement_status` 以 `unknown` 保存，statement_type 僅採 exact-name anchors，其餘仍為 unknown；取得完整可驗證 statement boundary 前，不宣稱三大報表 semantic Gate 通過。
