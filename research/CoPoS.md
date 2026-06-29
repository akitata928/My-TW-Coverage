# CoPoS Research Note

> 狀態：web research fallback 初稿，尚未寫入 `Pilot_Reports/`。  
> 建立日期：2026-06-29  
> 目的：整理 `CoPoS` 在原資料庫查無結果後的外部來源、候選台股與後續驗證步驟。

## 結論摘要

`CoPoS` 是台積電下一代面板級先進封裝路線，完整名稱常見為 Chip-on-Panel-on-Substrate。它和既有 `CoWoS` 的差異在於嘗試把封裝載體從圓形晶圓推向方形面板，提高大尺寸 AI/HPC 晶片封裝的面積使用率與產能效率。

目前 repo 內：

- `python scripts/query_theme.py "CoPoS"`：0 家
- `python scripts/query_theme.py "CoPoS" --include-bare`：0 家

Web fallback 初篩後，可先整理出 **19 家 repo 內已有的台股候選公司**，但尚未逐家公司完成一手來源驗證，因此暫不直接批次寫入公司報告。

## 主要來源

| 來源 | 重點 | 信心 |
|---|---|---|
| 商業周刊：`CoPoS是什麼？概念股有哪些？台積電下一代先進封裝技術全解析` | 直接列出 CoPoS 首波設備供應鏈、采鈺實驗線、封測受惠環節與常見概念股 | 中高 |
| 工商時報：`不只辛耘、弘塑！嘉義躍台積先進封裝重鎮 CoPoS設備供應鏈名單盤點` | 點名台積電嘉義 AP7、CoPoS 首波供應鏈大致底定，台廠包含辛耘、弘塑、均華、致茂等 | 中高 |
| 今周刊：`台積電CoPoS系列4...一表看30家供應鏈名單` | 補充面板級封裝設備、材料、封測與非台積電供應鏈候選，例如力成、萬潤、群翊、山太士、群創等 | 中 |
| 富果：`解析台積電下一世代 2.5D 封裝技術 CoPoS 與供應鏈的機會` | 標題與摘要確認主題存在，但全文需登入，暫不作公司名單依據 | 低到中 |

## Repo 內已有候選公司

### 高信心候選

這些公司被商業周刊或工商時報直接點名，且 repo 內已有對應報告。

| 代號 | 公司 | Repo 路徑 | 初步角色 |
|---|---|---|---|
| 3131 | 弘塑 | `Pilot_Reports/Semiconductor Equipment & Materials/3131_弘塑.md` | 濕式製程設備 |
| 3583 | 辛耘 | `Pilot_Reports/Semiconductors/3583_辛耘.md` | 濕式製程設備、先進封裝設備 |
| 6640 | 均華 | `Pilot_Reports/Semiconductor Equipment & Materials/6640_均華.md` | 固晶 / 封裝設備 |
| 2360 | 致茂 | `Pilot_Reports/Scientific & Technical Instruments/2360_致茂.md` | 測試與量測設備 |
| 2467 | 志聖 | `Pilot_Reports/Specialty Industrial Machinery/2467_志聖.md` | 熱製程設備 |
| 3680 | 家登 | `Pilot_Reports/Semiconductors/3680_家登.md` | Panel FOUP / 先進封裝載具 |
| 3535 | 晶彩科 | `Pilot_Reports/Computer Hardware/3535_晶彩科.md` | AOI / 光學檢測 |
| 3167 | 大量 | `Pilot_Reports/Specialty Industrial Machinery/3167_大量.md` | 精密清洗 / 表面處理設備 |
| 5443 | 均豪 | `Pilot_Reports/Semiconductor Equipment & Materials/5443_均豪.md` | AOI / 封裝設備 |
| 6789 | 采鈺 | `Pilot_Reports/Semiconductors/6789_采鈺.md` | 台積電子公司，CoPoS 實驗線候選角色 |
| 3711 | 日月光投控 | `Pilot_Reports/Semiconductors/3711_日月光投控.md` | 封測 / 先進封裝 |
| 2449 | 京元電子 | `Pilot_Reports/Semiconductors/2449_京元電子.md` | 測試 / 封測 |
| 6239 | 力成 | `Pilot_Reports/Semiconductors/6239_力成.md` | 面板級封裝 / 封測 |
| 6664 | 群翊 | `Pilot_Reports/Specialty Industrial Machinery/6664_群翊.md` | 壓膜 / 烘烤 / 熱製程設備 |

### 中信心候選

這些公司由今周刊等來源點名，或與面板級封裝、玻璃基板、FOPLP / TGV 技術高度相關，但仍需逐家公司補一手來源。

| 代號 | 公司 | Repo 路徑 | 初步角色 |
|---|---|---|---|
| 6187 | 萬潤 | `Pilot_Reports/Specialty Industrial Machinery/6187_萬潤.md` | 自動化 / 點膠 / 貼合設備 |
| 2464 | 盟立 | `Pilot_Reports/Specialty Industrial Machinery/2464_盟立.md` | 自動化系統 |
| 8027 | 鈦昇 | `Pilot_Reports/Specialty Industrial Machinery/8027_鈦昇.md` | 雷射加工 / 玻璃基板 TGV |
| 3595 | 山太士 | `Pilot_Reports/Electronic Components/3595_山太士.md` | 抗翹曲材料 / 暫時接著材料 |
| 3481 | 群創 | `Pilot_Reports/Electronic Components/3481_群創.md` | FOPLP / 面板級封裝 |

## 來源提及但 repo 內未對到

| 公司 / 代號 | 狀態 | 備註 |
|---|---|---|
| 7734 印能科技 | repo 內未收錄 | 來源點名熱製程設備；需確認上市櫃狀態與資料庫是否漏收 |
| 7822 倍利科 | repo 內未收錄 | 來源點名 AOI / 光學檢測；需確認上市櫃狀態與資料庫是否漏收 |
| 佳宸 | repo 內未收錄 | 來源點名，但需確認公司全名、是否上市櫃 |
| 亞智科技 | repo 內未收錄 | 來源點名，但需確認公司全名、是否上市櫃 |
| 力鼎 | repo 內未收錄 | 來源點名，但需確認公司全名、是否上市櫃 |
| 碩正 | repo 內未收錄 | 今周刊提到離型膜；需確認公司全名、ticker 與上市櫃狀態 |
| 晶化科技 | repo 內未收錄 | 今周刊提到膜狀封裝材、抗翹曲材料、雷射解膠膜；需確認上市櫃狀態 |

## 初步供應鏈分層

### 設備 / 製程控制

- 濕式製程：弘塑、辛耘
- 熱製程：志聖、群翊、印能科技
- 自動化 / 搬運 / 載具：家登、盟立、萬潤
- 測試 / 量測 / AOI：致茂、晶彩科、均豪、倍利科
- 清洗 / 表面處理：大量
- 雷射 / 玻璃基板加工：鈦昇

### 封測 / 封裝

- 台積電體系 / 實驗線：采鈺
- 封測：日月光投控、京元電子、力成
- 面板級封裝：群創

### 材料

- 抗翹曲 / 暫時接著 / 離型膜：山太士、碩正、晶化科技

## 建議下一步

1. 逐家公司補強一手來源：法說會、年報、公司公告、投資人簡報。
2. 對高信心候選先建立 enrichment JSON 草稿，但不要直接 apply。
3. 每家公司補入 `CoPoS` 前，先確認目前報告是否已有 `CoWoS`、`FOPLP`、`玻璃基板`、`TGV` 等相鄰脈絡。
4. 先做小批次更新，例如 3131 / 3583 / 6640 / 2360 / 2467，跑 audit 後再擴大。
5. 若候選公司有 5 家以上完成驗證，可考慮把 `CoPoS` 加進 `scripts/build_themes.py` 的 `THEME_DEFINITIONS`，建立主題頁。

## 暫不建議

- 不要只因媒體概念股列表就批次把所有公司加上 `[[CoPoS]]`。
- 不要把未上市或 repo 內未收錄公司硬塞進既有 ticker。
- 不要修改 `## 財務概況`。
