# Web Research Fallback SOP

這份 SOP 專門處理 `RESEARCH_LOOP.md` 裡的兩段：

```text
3. Web Research Fallback
4. Source Verification
```

目標是：當 repo 內查不到題材，或查到但資料不足時，用外部來源找候選公司，再用一手來源驗證，最後先寫研究筆記，不直接污染 `Pilot_Reports/`。

## 目前 repo 內已有的支援

### Python scripts

```bash
python scripts/query_theme.py "題材" --include-bare
python scripts/discover.py "題材" --smart
python scripts/match_candidates.py "3131 弘塑" "3583 辛耘"
```

用途：

- `query_theme.py`：唯讀查 repo 內 wikilink / 裸文字。
- `discover.py`：原 repo 的題材搜尋，可加 `--apply` 寫入 wikilink，但正式補資料前要小心。
- `match_candidates.py`：把外部查到的候選 ticker / 公司名對回 `Pilot_Reports/`。

### Agent / skill instructions

```text
CLAUDE.md
.claude/skills/discover.md
.claude/skills/update-enrichment.md
RESEARCH_LOOP.md
```

用途：

- `CLAUDE.md`：品質規則，尤其是不要猜、不要改財務表、確認公司身份。
- `.claude/skills/discover.md`：原始 discover fallback 流程。
- `.claude/skills/update-enrichment.md`：補公司業務 / 供應鏈 / 客戶供應商時的規則。
- `RESEARCH_LOOP.md`：我們整理後的高層流程。

## Decision Gate

只有符合以下任一情況，才進入 web fallback：

```text
1. query_theme.py 查到 0 家
2. 只有 bare mention，缺乏明確 wikilink
3. 題材明顯是新題材，repo 資料可能過舊
4. 使用者要求補強某題材供應鏈
```

如果 repo 已有清楚 wikilink 和主題頁，先用既有資料，不急著 web research。

## Step 1: Local Baseline

先跑本地查詢。

```bash
python scripts/query_theme.py "題材"
python scripts/query_theme.py "題材" --include-bare
python scripts/discover.py "題材" --smart
```

記錄：

```text
linked companies:
bare mentions:
0-result status:
related terms:
```

相關詞要一起想，例如：

```text
CoPoS -> FOPLP / 玻璃基板 / TGV / 先進封裝 / CoWoS
液冷散熱 -> CDU / 冷板 / 快接頭 / 浸沒式冷卻
矽光子 -> CPO / 光收發模組 / EML / VCSEL / InP
```

## Step 2: Web Search Queries

用多組查詢，不要只靠一篇概念股文章。

```text
"題材" 台灣 上市 供應鏈 概念股
"題材" 台股 相關個股
"題材" Taiwan listed company supply chain
"題材" 法說會
"題材" 年報
"題材" 投資人簡報
"題材" site:mops.twse.com.tw
"題材" site:*.com.tw 法說會
```

如果題材是台積電或供應鏈：

```text
"題材" 台積電 供應鏈
"題材" 先進封裝 設備 材料
"題材" TSMC supplier Taiwan
```

## Step 3: Candidate Extraction

從搜尋結果整理候選公司，先不要改 repo。

候選清單格式：

```text
3131 弘塑 - 濕式製程設備 - 來源 A / 來源 B
3583 辛耘 - 濕式製程設備 - 來源 A
6640 均華 - 固晶 / 封裝設備 - 來源 B
7734 印能科技 - 熱製程設備 - 來源 A
```

把候選公司對回 repo：

```bash
python scripts/match_candidates.py "3131 弘塑" "3583 辛耘" "7734 印能科技"
```

或用檔案：

```bash
python scripts/match_candidates.py --file research/candidates.txt
```

輸出要分成：

```text
matched:
  repo 內已有公司

unmatched:
  repo 內沒有，可能是未上市櫃、興櫃、漏收、或名稱不完整
```

## Step 4: Source Verification

來源信心等級：

| 等級 | 來源類型 | 可否寫入 Pilot_Reports |
|---|---|---|
| High | 公司年報、法說會、投資人簡報、公司公告、公開資訊觀測站 | 可以，小批次補 |
| Medium | 可信媒體、券商報告摘要、產業報告、交易所新聞 | 先寫 research note，必要時補但要標註謹慎 |
| Low | 部落格、論壇、未具名概念股清單、社群轉述 | 不直接補公司報告 |

驗證問題：

```text
1. 公司身份是否確認？ticker 和公司名有沒有對錯？
2. 這家公司和題材的角色是什麼？設備、材料、封測、客戶、供應商、品牌？
3. 來源是否明確提到題材？還是只是相鄰概念？
4. 資料日期是否過舊？
5. 是否有第二來源交叉確認？
```

## Step 5: Research Note First

先建立：

```text
research/<題材>.md
```

建議段落：

```md
# <題材> Research Note

## 結論摘要

## Repo 內查詢結果

## Web fallback 來源

## 高信心候選

## 中信心候選

## 低信心 / 暫不採用

## Repo 內未對到

## 供應鏈分層

## 下一步
```

原則：

- research note 可以收 medium / low 來源，但要標信心。
- `Pilot_Reports/` 只放較高信心、角色明確的資訊。
- 不要把媒體概念股清單直接寫成事實。

## Step 6: Enrichment Patch

只有在使用者確認後，才進入正式補檔。

補檔規則：

```text
1. 一次 3 到 5 家
2. 只新增已驗證脈絡
3. 不重寫整份公司報告
4. 不修改 ## 財務概況
5. 不把普通名詞硬包成 wikilink
6. 改完跑 audit
```

建議指令：

```bash
git status
python scripts/audit_batch.py --all
git diff --stat
```

需要重建索引時：

```bash
python scripts/build_wikilink_index.py
python scripts/build_themes.py
python scripts/build_network.py --min-weight 10
```

## Step 7: Theme Promotion

題材至少符合以下條件，才升級成正式 theme：

```text
1. 5 家以上已驗證公司
2. 供應鏈角色可分層
3. 至少部分公司有 High confidence 來源
4. 已有 research note
```

升級後可加入：

```text
scripts/build_themes.py 的 THEME_DEFINITIONS
```

## Anti-Rules

不要做：

```text
不要只因媒體說「概念股」就批次改 Pilot_Reports
不要把未上市櫃公司硬塞進既有 ticker
不要改 ## 財務概況
不要把一個題材硬套到所有相鄰供應鏈
不要在來源不足時寫成確定語氣
不要一次大批量改幾十家公司
```

## Output Template

回報給使用者時，用這個格式：

```text
題材：<題材>

repo 內查詢：
- linked: N 家
- bare mention: N 家
- 0-result: yes/no

web fallback：
- 來源數：N
- 高信心候選：N
- 中信心候選：N
- repo 未對到：N

建議：
1. 先建立 / 更新 research/<題材>.md
2. 高信心候選先處理 X / Y / Z
3. 暫不直接批次寫入 Pilot_Reports
```
