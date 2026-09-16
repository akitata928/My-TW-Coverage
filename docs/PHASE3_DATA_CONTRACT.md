# Phase 3：MOPS canonical data contract

## Canonical row

每一列代表一個來源 fact；JSON 是主要結構化輸出，CSV 是供表格工具／Perch 測試使用的等價輸出。Markdown 不作為唯一機器介面。欄位由 `scripts/emit_mops_canonical.py` 固定產出：

| 欄位群 | 欄位 | 契約 |
|---|---|---|
| Identity | `ticker`, `company_name`, `report_period` | 來源公司與申報期間；不從 local name 猜公司名稱 |
| Statement | `statement_type`, `consolidation_scope` | `balance_sheet`／`income_statement`／`cash_flow_statement`／`unknown`；`consolidated`／`individual`。`unknown` 僅表示 live instance 尚未取得可驗證的 statement boundary。 |
| Period semantics | `period_role`, `accumulation`, `period_start`, `period_end`, `period_instant` | `current`／`comparative`／`unknown`；`instant`／`single_period`／`year_to_date`／`unknown`；原始 context 日期保留 |
| Concept | `concept_qname`, `label_zh_tw`, `label_en` | qualified name 必須包含 namespace；中文缺失時為 `null`，英文可為 local fallback |
| Value | `value`, `raw_value`, `unit`, `raw_unit`, `decimals`, `value_status`, `missing_value_reason` | 不把缺值補成 0；缺值使用 `missing` 與原因，原始／正規化值並存 |
| Context | `context_ref`, `entity_scheme`, `entity_identifier`, `dimensions` | 保留 entity 與維度，避免同 local name facts 被合併 |
| Provenance | `source_url`, `retrieved_at`, `source_input_sha256` | 每列均可回溯來源與輸入 hash |

## 語意處理政策

- **缺值：** 沒有 source fact 不產生虛構列；若來源列存在但 value 不可用，`value_status=missing`、`missing_value_reason=source_value_unavailable`，不補零。
- **重述：** `restatement_status` 只接受 `as_filed`、`restated`、`unknown`。沒有來源明確證據就使用 `unknown`；重述版本不能覆寫舊列，需以不同 provenance／輸入 hash 保存。
- **比較期：** `period_role` 明確標成 `current`、`comparative` 或 `unknown`。Arelle context 日期本身永遠保留；無法由來源契約判斷時不猜測。
- **累計／單季：** duration context 若有來源映射才標 `single_period` 或 `year_to_date`；否則 `unknown`。instant context 標 `instant`。
- **合併／個別：** 由下載請求的 `report_id` 契約提供，不由 fact local name 推測。
- **單位與 decimals：** `raw_value`／`raw_unit`／`decimals` 永遠保留；`value`／`unit` 是 Phase 2 明確正規化結果。

## Fixture 與 Gate

- Sanitized JSON／CSV：`tests/fixtures/mops_xbrl/2330_2026Q2_C_canonical.sample.json`、`.csv`。
- 測試：`tests/test_emit_mops_canonical.py` 驗證欄位、provenance、unknown policy、JSON／CSV deterministic output 與 statement type。
- 只新增隔離 fixture 與 parser／schema 文件；不寫入、不覆蓋 `Pilot_Reports/`。
