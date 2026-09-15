# My-TW-Coverage 測試開發計畫

**狀態：** Draft PR／Phase 0 規劃，尚未修改既有報告與財務資料  
**建立日期：** 2026-09-15  
**主要測試主題：** MOPS XBRL／TIFRS 擷取、結構化轉換與 Perch 相容性

## 1. 目的

以可回溯、可重跑、低風險的方式，驗證本專案是否能將台灣公開資訊觀測站（MOPS）的 XBRL／iXBRL 財報轉換為結構化資料，供後續 Perch 或本機分析流程使用。

本計畫先建立測試證據與資料契約，再決定是否進入正式 pipeline；不因單次成功下載就宣稱已支援全部 TIFRS 財報。

## 2. 目前基線與限制

- 專案核心資料是 `Pilot_Reports/` 下的台股公司 Markdown 報告，並以 `[[wikilink]]` 建立供應鏈知識圖譜。
- 目前實際報告數量、README 宣稱數量與歷史 task 內容存在口徑差異；先不以新增報告方式掩蓋差異。
- `CLAUDE.md` 規定財務表格不可被 enrichment 流程修改，所有實驗輸出應放在隔離的測試資料夾。
- MOPS 下載端點在雲端測試環境曾回傳 HTTP 403；尚未證明是 MOPS IP 政策、出口網路限制、session／header 缺漏或 rate limit。
- Perch 文件未確認有內建 XBRL／MOPS 解析器，因此本計畫把「XBRL 解析」與「Perch 讀取結構化結果」分成兩個獨立驗收項目。

## 3. 範圍

### 包含

1. 官方 MOPS XBRL 下載路徑與參數契約。
2. 台灣 TIFRS taxonomy 的 Arelle 解析可行性。
3. 2330 台積電、2026 年第 2 季合併資產負債表作為第一個 golden fixture。
4. 資產負債表、損益表、現金流量表的欄位映射與單位正規化。
5. 來源 URL、下載時間、公司代號、年度／季度、報表類型、taxonomy 與 parser 版本的 provenance。
6. 供 Perch 或其他決定論分析工具使用的 CSV／JSON／Markdown 表格輸出契約。
7. 單元測試、fixture 測試、整合測試與失敗重試／封鎖行為測試。

### 不包含

- 不直接改寫既有 `Pilot_Reports/` 財務表格。
- 不先對全部 1,733 份公司報告批次下載或重建。
- 不繞過 CAPTCHA、IP 封鎖、robots 或其他 MOPS 存取控制。
- 不把 Perch 視為 XBRL parser；Perch 相容性必須以轉換後的結構化檔案實測確認。

## 4. 分階段 Jobs 與 Gate

### Phase 0 — 基線與來源契約（完成）

- [x] 確認 repo baseline、Python 版本、依賴安裝方式與測試指令。
- [x] 釐清報告數量（1,733／1,735／1,737）與既有 verification phase，不在此階段修改數據。
- [x] 記錄 MOPS 官方 URL pattern、必要參數、HTTP method、header、referer、cookie 與錯誤行為。
- [x] 建立 `tests/fixtures/mops_xbrl/` 隔離目錄規範，禁止把憑證或 session state 放入 Git。

**Gate：** 通過。來源契約、Mac mini 實測證據、403 原因分類與 Phase 1 驗證步驟見 `docs/MOPS_XBRL_SOURCE_CONTRACT.md`；基線見 `docs/PHASE0_BASELINE.md`。

### Phase 1 — 下載器可行性與 golden fixture（完成）

- [x] 在台灣境內本機測試 MOPS XBRL 下載 URL。
- [x] 測試 2330／2026 Q2／合併報表（`report_id=C`）。
- [x] 若下載成功，保存去除敏感資訊、可重跑的 fixture metadata；原始財報是否入庫需另行確認授權與檔案大小。
- [x] 測試 session cookie、User-Agent、Referer 與退避重試；不得使用 `verify=False` 或繞過存取限制。
- [x] 明確區分「索引成功」「下載成功」「檔案可解析」三種狀態。

**Gate：** 通過。探測器見 `scripts/probe_mops_xbrl.py`；成功 metadata 與錯誤頁分類 fixture 見 `tests/fixtures/mops_xbrl/`。A／其他報表 function 的未成功變體已記錄於來源契約，未被誤判為支援。

### Phase 2 — TIFRS／Arelle 解析器（完成，MVP fallback）

- [x] 固定 `arelle-release==2.45.1` 並記錄 parser 版本。
- [x] 驗證 `tifrs-*` namespace、qualified name 與英文 fallback。
- [x] 驗證 taxonomy linkbase 的中文標籤 `zh-TW`：目前官方 XSD／label linkbase 未能由來源取得；MVP 明確輸出 unavailable，英文使用 local fallback，待後續取得 taxonomy 再補強。
- [x] 驗證 entity identifier、period、unit、decimals 與 context 維度。
- [x] 對 `decimals` 負值做明確正規化，保留原始值與原始單位。
- [x] 產生 deterministic normalized facts，不以欄位 local name 單獨去重。

**Gate：** 部分通過（MVP accepted）。qualified facts／context／unit／decimals 與 deterministic sample 已完成；`zh-TW` label 依決策採 `null` fallback，不宣稱中文標籤已驗證，但不阻擋 Phase 3 schema。

### Phase 3 — 報表資料契約（完成）

- [x] 定義 balance sheet、income statement、cash flow statement 的 canonical schema。
- [x] 每筆 fact 至少保留：`ticker`、`company_name`、`report_period`、`statement_type`、`concept_qname`、`label_zh_tw`、`value`、`unit`、`decimals`、`context_ref`、`source_url`、`retrieved_at`。
- [x] 定義缺值、重述、比較期、累計／單季、合併／個別報表的處理方式。
- [x] 輸出 CSV 與 JSON；Markdown 只作為人工檢查呈現，不作為唯一機器介面。

**Gate：** 通過。schema、JSON／CSV fixture 與 deterministic 測試完成，且未覆寫現有報告財務表格；契約詳見 `docs/PHASE3_DATA_CONTRACT.md`。

### Phase 4 — Perch 相容性測試（MVP accepted；Perch runtime pending）

- [x] 將 normalized CSV／JSON 複製到隔離測試目錄。
- [ ] 驗證 Perch 是否能讀取、執行 deterministic calculation、保留欄位名稱與單位；本機找不到 Perch runtime，待取得後實測。
- [ ] 分別測試 Desktop／CLI sandbox 與 Web upload 能力；不要把 Web 版能力推論成 Desktop／CLI 能力。
- [x] 以固定輸入驗證相同本機 calculation 結果，並記錄輸入檔 hash；Perch 版本／輸出 hash 待 runtime。

**Gate：** Stan 已接受「本機資料契約 harness 通過、Perch runtime pending」政策，可進入 Phase 5；不能宣稱 Desktop／CLI／Web 相容性已通過。即使 Perch 後續測試失敗，本機 parser 與 normalized output 仍可獨立交付。詳見 `docs/PHASE4_PERCH_COMPATIBILITY.md`。

### Phase 5 — pipeline 整合與 Pilot（pilot harness 完成）

- [x] 以現有 pipeline 的 adapter／cache／logging 模式建立獨立 MOPS XBRL adapter。
- [x] 沿用 rate limit、403、timeout、空檔案、解析錯誤與非 XBRL 回應的分類錯誤。
- [x] 以成功與失敗 fixture job 驗證 1–3 家公司、單一季度 pilot 隔離，不碰全量資料。
- [x] 驗證 provenance、冪等下載、重跑一致性與失敗不污染既有報告。
- [ ] 只有在 pilot 通過且取得獨立決策後，才提出更大範圍的季度更新方案。

**Gate：** pilot harness 具備可回滾、可重跑、可審計的骨架；正式 live pilot／更大範圍季度更新仍由獨立決策確認。詳見 `docs/PHASE5_PILOT.md`。

## 5. 測試矩陣

| 類型 | 測試內容 | 通過條件 |
|---|---|---|
| Transport | 官方 URL、headers、session、403、timeout | 錯誤分類正確，不繞過限制 |
| Fixture | 2330／2026 Q2／C | fixture 可重跑且 metadata 完整 |
| Parser | TIFRS namespace、context、unit、decimals | normalized facts 穩定且可回溯 |
| Schema | 三大財報與合併／個別 | 欄位契約與單位契約通過 |
| Determinism | 同一輸入重跑 | output hash／語意結果一致 |
| Perch | CSV／JSON 匯入與計算 | 能讀取或明確記錄不相容原因 |
| Regression | 現有報告與 wikilink graph | 既有檔案 checksum／測試不受影響 |

## 6. 交付物

1. 本計畫文件。
2. MOPS XBRL source contract 與錯誤分類文件。
3. 隔離的 golden fixture metadata。
4. 下載器與 Arelle parser（僅在 Phase 0–1 Gate 通過後實作）。
5. canonical schema、CSV／JSON sample output。
6. 測試報告與 Perch 相容性結論。
7. Pilot handoff：限制、已知問題、回滾方式與下一步建議。

## 7. PR 工作方式

- 本 PR 先只放測試開發計畫，不修改 `Pilot_Reports/`、財務表格或全量索引。
- 後續實作以 Phase 為單位提交，所有變更附測試與驗證結果。
- 任何需要修改資料格式、正式下載範圍、外部服務或排程的動作，先在 PR 中列出決策點。
- Draft PR 不代表功能完成；只有各階段 Gate、回歸測試與 pilot 證據齊全後，才評估轉為 Ready for review。
