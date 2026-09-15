# Phase 2：TIFRS／Arelle 解析驗證

## 執行環境

- `arelle-release==2.45.1`，固定於 `requirements-xbrl.txt`。
- Arelle 2.45.1 要求 Python >= 3.10；既有 repo `.venv` 是 Python 3.9.6，因此使用隔離的 Python 3.14 parser environment，沒有改動既有環境。
- 輸入：2330／2026 Q2／合併資產負債表，輸入 SHA-256：`351b4e59781a71504b30cec9d977e060ab4f978d31695e027252ecfe793d1e55`。

## 已完成的解析能力

`scripts/parse_mops_xbrl.py` 會：

1. 使用 Arelle 載入 iXBRL，保留 parser diagnostics，不把 HTTP 200 或 Arelle warning 誤判成完整 taxonomy 驗證。
2. 以 `{namespace}local_name` 保存 qualified name；不以 local name 單獨去重。
3. 保存 entity scheme／identifier、period、context reference、dimensions、unit 與 decimals。
4. 以 `Decimal` 做 deterministic 數值輸出；有限負 decimals 依本專案契約套用 `10 ** (-decimals)`，同時保留 `raw_value`、`raw_decimals` 與 `raw_unit`。
5. 依 qualified name、context、unit、decimals、raw value 排序，輸出穩定 JSON。
6. 若 taxonomy linkbase 可用，優先取 `zh-TW` 與英文 label；否則明確使用 qualified-name local fallback，不假裝取得中文標籤。

## 實測結果

| 項目 | 結果 |
|---|---|
| Arelle model facts | 1,228 |
| numeric facts | 1,102 |
| contexts | 99 |
| units | 4 |
| parser diagnostics | 2,669 |
| `tifrs-*` qualified names | 已取得 |
| entity `http://www.twse.com.tw`／`2330` | 已取得 |
| TWD／shares／EPS／pure units | 已取得 |
| dimensions | 已取得，包含 IFRS ComponentsOfEquityAxis |
| zh-TW taxonomy label | 尚未取得 |

## 已知限制與 Gate 狀態

MOPS 回傳的 iXBRL 會引用相對 XSD，例如 `tifrs-ci-cr-2026-03-31.xsd`；目前官方下載端點未提供可重現的 XSD URL，且輸入本身未包含 label linkbase。因此 Arelle 仍能抽取 facts／contexts／units，但 `fact.concept` 可能為空，產生 2,669 個 schema/linkbase diagnostics，中文 label 只能標記 unavailable。

已提交 sanitized sample：`tests/fixtures/mops_xbrl/2330_2026Q2_C_normalized.sample.json`。在沒有 taxonomy linkbase 的前提下，qualified name、context、unit、decimals 與 deterministic normalized facts 已完成；**Phase 2 Gate 的 `zh-TW` label 子項暫為 blocked，不宣稱整體 Gate 已通過**。

下一個可執行步驟是取得同一版本的官方 TIFRS XSD／label linkbase，再以相同輸入重跑並比較 normalized output；不會把猜測的 taxonomy 或自行編造標籤提交進 repo。
