# Phase 4 Replan：不依賴 Perch runtime 的資料分析設計

## 已確認的限制

- Perch Desktop／CLI／Web 需要付費訂閱或 runtime。
- 本機不部署 Perch，因此 Desktop／CLI／Web 三者無法取得實測證據。
- 現有本機 harness 只驗證 canonical JSON／CSV 契約、欄位／單位保留與 deterministic calculation；它不是 Perch 相容性證明。

## 候選設計

### 選項 A（推薦）：移除 Perch 作為必要依賴

把 canonical JSON／CSV 視為穩定交付介面，分析與查詢改由本機可驗證的 SQLite／DuckDB／Python（必要時 Polars 或 pandas）執行。Phase 4 改測「本機分析介面契約」：schema import、欄位／單位保留、查詢、計算、輸出 hash 與 provenance。

優點：零訂閱成本、可在目前主機完整測試、可排程與可回溯；缺點：不再提供 Perch 原生操作體驗。

### 選項 B：Perch 僅作未來外部匯出目標

保留目前 canonical JSON／CSV 與 export manifest，但不把 Perch 相容性列入 MVP Gate；日後 Stan 若取得合法帳號或 runtime，再以獨立 adapter 實測 Desktop／CLI／Web。

優點：保留未來相容性可能、不阻擋本機 pipeline；缺點：Phase 4 長期維持 pending，且不能保證匯入結果。

### 選項 C：尋找其他免費 GUI／雲端分析工具

另做工具調查與逐一相容性驗證，再決定替換 Perch。此選項會增加供應鏈、介面與維護範圍，不能直接假設任何替代工具相容。

## 已確認決策

Stan 已確認採 **A + B**：MVP 移除 Perch 必要依賴，使用本機可驗證分析介面繼續 Phase 5；同時保留 canonical JSON／CSV 作為未來 Perch 匯出邊界，但不宣稱相容性。

Phase 4 的新驗收是：本機 JSON／CSV import、query、Decimal calculation、provenance 與 deterministic hash。實作入口為 `scripts/local_analysis.py`；Perch 僅保留為未來外部匯出目標。
