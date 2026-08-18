# 在 Obsidian 中使用本資料庫

把 repo 資料夾本身當作 vault 開啟即可（Obsidian → Open folder as vault）。
不需要複製或轉檔。

## 為什麼有 `entities/`

Obsidian 解析 `[[名稱]]` **只看檔名**。報告的檔名是 `2330_台積電.md`，
所以 `[[台積電]]` 找不到對應檔案，會顯示為未解析的紅色連結。

Frontmatter 的 `aliases` 不能解決這件事：別名只會出現在自動完成選單，
由腳本寫入的裸 `[[別名]]` 在原生 Obsidian 中不會解析
（社群外掛 Alias Linker、obsidian-auto-linker 存在的原因正是如此）。

因此 `entities/` 為每個 wikilink 各建一則筆記，檔名就是實體名稱。
目前涵蓋 6,083 個實體，**100% 的報告連結出現位置可以點開**
（全 vault 僅餘 11 處無法解析，見下方限制）。

每則實體筆記包含：

- `type` — 台灣公司／國際公司／技術／材料／終端應用
- `mentions` / `reports` — 被提及次數與報告份數
- `id` — 台股代號（僅限本資料庫有報告的公司）
- **上游 — 供應給它** 與 **下游 — 它供應給**，方向取自報告自己寫的
  `上游`／`下游`／`主要客戶`／`主要供應商` 結構
- 該實體最常一起出現的其他實體
- 若有對應個股報告，直接連往該報告

「**哪些報告提到這個實體**」由 Obsidian 左側的反向連結面板原生提供，
不需要額外查詢。

## Dataview 查詢

以下查詢需要安裝社群外掛 **Dataview**。
每份個股報告的 frontmatter 都帶有 `ticker`／`company`／`sector`／`industry`／
`market_cap`／`enterprise_value`，可直接篩選排序。

### 某個主題的概念股，依市值排序

`FROM [[CoWoS]]` 的意思是「所有連往 CoWoS 的筆記」。
把 `[[CoWoS]]` 換成任何實體即可。

````
```dataview
TABLE company AS 公司, industry AS 產業, market_cap AS 市值
FROM [[CoWoS]]
WHERE ticker
SORT market_cap DESC
```
````

### 某產業的所有公司

````
```dataview
TABLE company AS 公司, market_cap AS 市值
FROM "Pilot_Reports"
WHERE industry = "Semiconductors"
SORT market_cap DESC
LIMIT 30
```
````

### 市值門檻篩選

````
```dataview
TABLE company AS 公司, sector AS 板塊, market_cap AS 市值
FROM "Pilot_Reports"
WHERE market_cap > 100000
SORT market_cap DESC
```
````

### 被最多報告提及的實體

````
```dataview
TABLE type AS 類別, reports AS 報告數, mentions AS 提及次數
FROM "entities"
SORT reports DESC
LIMIT 40
```
````

## 重建

報告內容有變動後（新增個股、enrichment、正規化），重建實體筆記：

```bash
python scripts/normalize_reports.py        # 正規化連結並更新 frontmatter
python scripts/build_obsidian_vault.py     # 重建 entities/
```

`--clean` 會先刪除既有實體筆記再重建，適合實體大量更名之後使用：

```bash
python scripts/build_obsidian_vault.py --clean
```

## 已知限制

- **5 個實體名稱含 `/`**，無法作為檔名，因此不會解析：
  `DC/DC`、`Low Dk/Df`、`PIC/S GDP`、`PIC/S GMP`、`Super I/O`。
  這些是名稱本身就帶斜線的正當術語。原本另有 4 個是兩個實體被寫成一個
  （`CPU/晶片組`、`LED/雷射光源`、`PVC/橡膠料`、`牙科/工業應用`），已拆開修正。
- **`SOC` 與 `SoC` 在不分大小寫的檔案系統上會撞檔**（macOS、Windows）。
  兩者語意不同——`SOC` 是資安維運中心，`SoC` 是系統單晶片——
  目前保留較常用的 `SoC`，`SOC` 不建檔。
- 實體筆記是**產生物**，不要手動編輯；下次重建會被覆蓋。
