# Taiwan Stock Research Loop

這份文件把本 repo 的台股研究方式整理成一個可重複的 Loop。目標是先用現有資料庫快速縮小範圍，再用外部來源驗證，最後才小批次補資料與重建索引。

## 核心概念

這個 repo 不是即時行情工具，而是「供應鏈知識庫」。最適合的用法是：

1. 從題材、技術、客戶或材料開始搜尋。
2. 找出相關台股公司。
3. 用公司報告理解它在供應鏈的位置。
4. 對查不到或資料過舊的題材做 web research fallback。
5. 經驗證後再補回 Markdown、wikilink、themes 和 network。

## Research Loop

```text
題材 / 個股問題
      |
      v
1. Database Search
   先查 repo 內既有資料
      |
      v
2. Result Triage
   分類：已知公司 / 裸文字提及 / 查無結果
      |
      v
3. Web Research Fallback
   查無或資料不足時，用外部來源找候選公司
      |
      v
4. Source Verification
   用法說會、年報、公告、投資人簡報驗證
      |
      v
5. Research Note
   先寫 research/*.md，不直接污染 Pilot_Reports
      |
      v
6. Small Batch Enrichment
   小批次補公司報告，只新增已驗證脈絡
      |
      v
7. Rebuild Indexes
   重建 WIKILINKS / themes / network
      |
      v
8. Audit & Diff Review
   跑 audit、看 git diff，確認沒有品質退化
      |
      v
回到下一個題材 / 個股問題
```

## Step 1: Database Search

先使用唯讀查詢，不改任何檔案。

```bash
source .venv/bin/activate
python scripts/query_theme.py "CoWoS"
python scripts/query_theme.py "液冷散熱" --include-bare
python scripts/discover.py "AI 伺服器" --smart
```

判讀方式：

- 找到很多公司：先看分組，分辨核心業務、供應鏈、客戶供應商。
- 只有 bare mention：代表資料可能提過但尚未 wikilink 化。
- 0 家：進入 web research fallback。

## Step 2: Result Triage

把結果分成三層：

| 層級 | 意義 | 下一步 |
|---|---|---|
| 高信心 | 公司報告已明確出現 `[[題材]]` 或強相關 wikilink | 可直接列入候選名單 |
| 中信心 | 有裸文字、相鄰技術或供應鏈脈絡 | 需要補來源確認 |
| 低信心 | 只在媒體概念股清單出現 | 先放研究筆記，不直接改報告 |

## Step 3: Web Research Fallback

當 repo 內查不到時，先做外部搜尋。

```text
"題材" 台灣 上市 供應鏈 概念股
"題材" Taiwan listed company supply chain
"題材" 台股 相關個股
```

找到候選公司後，不要直接寫入 `Pilot_Reports/`。先確認：

- 公司是否為台灣上市櫃或興櫃。
- repo 內是否已有對應 Markdown。
- 來源是否只是媒體概念股清單，還是有公司公告 / 法說會 / 年報支持。
- 角色是否清楚，例如設備、材料、封測、客戶、供應商、通路。

細部行動 SOP 見：

```text
WEB_RESEARCH_FALLBACK_SOP.md
```

候選公司可先用這支工具對回 repo：

```bash
python scripts/match_candidates.py "3131 弘塑" "3583 辛耘"
```

## Step 4: Research Note First

新增或更新 `research/<題材>.md`，先把證據整理好。

建議格式：

```md
# 題材 Research Note

## 結論摘要

## Repo 內查詢結果

## 主要來源

## 高信心候選

## 中信心候選

## 來源提及但 repo 內未對到

## 供應鏈分層

## 建議下一步

## 暫不建議
```

目前範例：

```bash
research/CoPoS.md
```

## Step 5: Small Batch Enrichment

確認來源後，再小批次補公司報告。原則是「只補已驗證資訊，不重寫整份報告」。

建議一次先處理 3 到 5 家，例如：

```text
3131 弘塑
3583 辛耘
6640 均華
2360 致茂
2467 志聖
```

補資料時要遵守：

- 不修改 `## 財務概況`。
- 不把媒體概念股名單當成唯一證據。
- 不把普通名詞硬包成 wikilink。
- 不新增無法確認 ticker 的公司。
- 每次修改前後都看 `git status` 和 `git diff`。

## Step 6: Rebuild Indexes

修改 `Pilot_Reports/` 後，再重建衍生資料。

```bash
python scripts/build_wikilink_index.py
python scripts/build_themes.py
python scripts/build_network.py --min-weight 10
```

如果某題材已驗證公司超過 5 家，可考慮把它加入 `scripts/build_themes.py` 的 `THEME_DEFINITIONS`。

## Step 7: Audit & Review

每次批次更新後都跑：

```bash
python scripts/audit_batch.py --all
git status
git diff --stat
```

看三件事：

- audit 是否仍通過。
- 是否誤改財務表。
- 產物檔是否只是合理重建。

## 建議改善

### 1. 建立正式的研究筆記目錄規格

目前 `research/` 是我們新增的，建議把格式固定下來。每個新題材都先進 research note，驗證後才更新主資料庫。

### 2. 讓 `query_theme.py` 支援 `--save-note`

可新增：

```bash
python scripts/query_theme.py "CoPoS" --include-bare --save-note
```

自動產生 `research/CoPoS.md` 草稿，包含 repo 查詢結果與待補來源欄位。

### 3. 加入來源信心等級欄位

未來 enrichment JSON 可多一層 metadata：

```json
{
  "source_confidence": "high",
  "sources": [
    "2026 法說會",
    "公司年報"
  ]
}
```

這樣可區分「一手來源驗證」和「媒體推測」。

### 4. 把 web fallback 結果和正式補檔分離

目前 `.claude/skills/discover.md` 會在使用者同意後直接補報告。建議改成兩段：

1. 先產生 `research/*.md`。
2. 使用者確認後，再產生 enrichment patch。

### 5. 對財務更新加更明確保護

`update_financials.py` 和 `update_valuation.py` 已有用途，但建議預設要求 `--dry-run` 或在文件中強調「財務表是外部資料，不和題材補強混跑」。

### 6. 建立主題成熟度

每個題材可分成：

| 狀態 | 意義 |
|---|---|
| Draft | 只有 research note |
| Candidate | 有候選公司但未全部驗證 |
| Verified | 主要公司已有一手來源 |
| Indexed | 已寫入 Pilot_Reports 並重建 themes/network |

這樣之後問「CoPoS 到哪一步了」會很清楚。

## 推薦日常用法

### 查題材

```bash
python scripts/query_theme.py "題材" --include-bare
```

### 查個股

```bash
rg -n "題材|客戶|材料" "Pilot_Reports/產業/代號_公司.md"
```

### 查不到

建立或更新：

```bash
research/題材.md
```

### 要正式補資料

先小批次，後 audit：

```bash
python scripts/audit_batch.py --all
git diff --stat
```

## 我的看法

這個 repo 最有價值的不是 1,735 份靜態報告，而是 wikilink 形成的題材反查能力。二次實作應該優先加強「研究流程可信度」，而不是急著大量補題材。

我會把改善順序排成：

1. 先固定 `research/*.md` 工作流。
2. 再讓查詢工具能自動產生研究筆記草稿。
3. 接著建立來源信心等級。
4. 最後才做批次 enrichment 與主題頁擴充。

這樣資料庫會越用越準，不會變成媒體概念股剪貼簿。
