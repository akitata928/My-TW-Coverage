# Phase 4：Perch 相容性測試

## 已完成的本機可驗證部分

- `scripts/run_perch_compatibility.py` 會把 canonical JSON／CSV 複製到指定隔離目錄，不接觸 `Pilot_Reports/`。
- 驗證 JSON／CSV 的 concept、value、unit、context 順序與內容一致。
- 驗證必要欄位：`concept_qname`、`value`、`unit`、`context_ref`、`source_url`、`source_input_sha256`。
- 以 `Decimal` 產生固定的按 unit 加總，並記錄 JSON／CSV SHA-256、輸入 hash 與結果 manifest。
- 固定 fixture：`tests/fixtures/mops_xbrl/2330_2026Q2_C_canonical.sample.json`／`.csv`。

## Perch runtime 狀態

本機未找到 `perch`／`perchai`／`perch-ai` CLI，也未找到 Perch Desktop application；因此本階段沒有宣稱 Perch Desktop／CLI／Web upload 已實測。`perch_runtime_not_available` 會明確寫入 harness manifest。

這不是 parser 或 canonical schema 的失敗：本機 harness 證明輸入是結構化、可回溯且 CSV／JSON 等價；但仍欠缺 Perch 實際 runtime 的讀取、計算與版本證據。

## Gate 決策

Stan 已接受 MVP 政策：**本機資料契約 harness 通過、Perch runtime pending**。因此 Phase 4 可進入 Phase 5；此決策不等同於宣稱 Perch Desktop、CLI 或 Web upload 相容性已通過。取得合法 runtime 後，仍須依下列流程分別補做三種介面的實測。

## 後續 Perch 實測最小流程

1. 取得可合法使用的 Perch Desktop／CLI 或 Web upload runtime。
2. 只匯入隔離 fixture，不提供 repo secrets 或既有報告資料。
3. 記錄 Perch 版本、input JSON／CSV hash、欄位保留結果與 deterministic calculation output hash。
4. 分別記錄 Desktop／CLI sandbox 與 Web upload；不能用其中一個推論另一個。
