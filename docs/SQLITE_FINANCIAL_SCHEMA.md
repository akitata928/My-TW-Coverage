# 多產業財報 SQLite／Python 資料模型規劃

## 目的與決策

MVP 不把 Perch 當成必要依賴，改以 SQLite 保存可追溯的 XBRL 原始事實與語意映射，Python 負責查詢、Decimal 計算、品質檢查與報表呈現。Canonical JSON／CSV 仍保留為匯入／匯出邊界，但不宣稱 Perch 相容性。

製造業與金融業不能共用一張固定寬表。金融業至少分為金控、銀行、保險、證券；各類科目、期間語意、單位與適用準則不同。因此採「原始長表 + 版本化語意映射 + 產業查詢 view」，不以缺值補零或公司名稱猜科目。

## 產業分類邊界

`industry_family` 使用明確枚舉：

- `general_industrial`：一般製造、科技與非金融產業
- `financial_holding`：金控集團層級
- `bank`：銀行
- `insurance`：保險
- `securities`：證券
- `unknown`：尚未驗證，不猜測

公司可另有 `institution_type`、`parent_ticker`、`taxonomy_version`；產業分類不是由中文公司名稱推導，而應由 MOPS／官方分類或經核准的 issuer registry 提供。

## SQLite 分層 schema

### 1. Raw／provenance layer

保留來源原貌，任何後續映射都不能覆寫：

- `issuers`：ticker、公司名稱、industry_family、institution_type、parent_ticker、分類來源與生效日期。
- `raw_documents`：source_url、report_year、report_quarter、consolidation_scope、retrieved_at、raw_sha256、taxonomy_version、parser_version、HTTP metadata。
- `xbrl_contexts`：entity、instant／duration、start_date、end_date、period_role、segment／dimension JSON、context_ref。
- `xbrl_units`：unit_ref、measure、numerator、denominator、原始 unit JSON。
- `taxonomy_concepts`：namespace、qualified QName、local name、label_zh_tw、label_en、balance、period_type、taxonomy_version。
- `xbrl_facts`：raw_document_id、context_ref、unit_ref、concept_qname、raw_value、normalized_value、decimals、dimensions、fact hash 與 provenance。

主鍵與唯一性應以來源文件、qualified QName、context、unit 與 fact identity 組合處理；不能只用中文標籤或 local name 合併不同 taxonomy 的科目。

### 2. Semantic／analysis layer

- `statement_facts`：由 raw facts 投影出的分析事實，包含 statement_type、industry_family、report_scope、period_role、accumulation、concept_mapping_id、mapping_status。
- `concept_mappings`：`source_qname → canonical_concept`，包含適用產業、taxonomy_version、mapping_version、effective_from／to、confidence、mapping_status 與人工註記。
- 金融業 live pilot 使用 `config/mops_financial_mapping.json` 的版本化 registry；目前只接受 exact QName local-name 的保守 provisional anchors。未列入 registry 的 concept 維持 `unknown` 並產生 quality warning，不以中文名稱、子字串或數值猜測語意。
- `statement_templates`：各產業報表可呈現的概念集合、必要／選用規則、單位與期間條件。
- `data_quality_issues`：unknown concept、缺值、單位衝突、期間衝突、重述、重複 fact、映射未驗證等問題。

Canonical concept 只代表已驗證的分析語意；沒有可信映射的 fact 仍保留在 `xbrl_facts`，在 semantic layer 標記 `unknown`，不丟失也不補零。

## 報表語意要求

每筆分析事實至少要能區分：

- `statement_type`：balance sheet、income statement、cash flow statement，以及未來金融業專用 statement。
- `consolidation_scope`：consolidated／separate／unknown。
- `period_role`：instant、current_period、comparative_period、unknown。
- `accumulation`：quarter、year_to_date、annual、unknown。
- `restatement_status`：original、restated、unknown。
- `industry_family` 與 `institution_type`。

不把不存在的金融業科目寫成 0；沒有來源事實時使用 NULL／unknown，並可在品質表追蹤原因。

## 產業查詢介面

由長表與 mapping 產生唯讀 view，不複製或改寫 raw facts：

- `v_general_industrial_financials`
- `v_financial_holding_financials`
- `v_bank_financials`
- `v_insurance_financials`
- `v_securities_financials`

通用 Python query API 應支援 ticker、季度、statement、合併範圍、industry_family、canonical concept／source QName、period_role、unit、quality status 與 provenance 篩選。所有金額計算使用 `Decimal`，並保留輸入 fact hash 與 mapping version。

## 版本與官方依據

`taxonomy_version`、`mapping_version` 與 `effective_from` 必須入庫。金融業 2026 年起的分類及準則變更不可與舊年度映射混用；尤其要分別驗證 IFRS 9、IFRS 15、IFRS 17 相關科目。

設計查證依據：

- [TWSE XBRL 分類標準](https://www.twse.com.tw/rwd/XBRL/standard)
- [TWSE 金融業／金控業 IFRSs 會計項目修訂](https://twse-regulation.twse.com.tw/TW/int/DAT01.aspx?FLCODE=FE393643)
- [金管會證期局財務報告規範](https://www.sfb.gov.tw/ch/home.jsp?id=932&parentpath=0,2)

上述來源支持「金融業與金控業需分開分類」的設計方向；實際 concept mapping 仍須以各 pilot XBRL fixture 驗證，不以文件名稱推測完整科目表。

## 實作順序與 Gate

1. 先建立 migration、外鍵、版本欄位與 sanitized schema fixture。
2. 以 2330（一般製造／科技）驗證既有 canonical facts 不退化。
3. 再加入一家金控與一家銀行，驗證不同產業可共存且不互相污染。
4. 保險與證券列為第二輪：保險需額外驗證 IFRS 17，證券需額外驗證經紀、承銷、自營與客戶保證金語意。
5. 只有在上述 fixture、mapping、query、quality 與 provenance 測試通過後，才決定是否擴大 live pilot。

本文件是 schema／資料契約規劃，不代表已完成金融業 parser 或已下載金融業正式財報。
