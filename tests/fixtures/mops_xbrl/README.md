# MOPS XBRL Fixture 規範

這個目錄只存放去敏感、最小化、可重跑的 MOPS XBRL 測試 fixture。

## 允許提交

- `metadata.json`：公司代號、年度／季度、報表類型、來源 URL、抓取時間、HTTP 狀態、內容 hash、parser／taxonomy 版本。
- 經授權後保存的最小 fixture，且必須在 PR 說明保存理由、大小與授權邊界。
- 人工建立、不可逆去敏感的欄位樣本；需保留原始欄位名稱與單位語意。

## 禁止提交

- Google／MOPS／任何服務的密碼、API key、Cookie、session state、Authorization header。
- 未確認授權可再分發的完整原始財報。
- `.env`、瀏覽器 profile、下載暫存檔、WAL／lock 檔。
- 直接覆蓋 `Pilot_Reports/` 的輸出。

## 命名與驗證

建議命名：`{ticker}_{year}Q{quarter}_{report_id}_{statement}.json`。

每個 fixture 必須能透過 metadata 回溯到來源 URL 與抓取結果；不可把認證資訊放在 metadata。Phase 1 前，真實下載檔應留在 repo 外的暫存路徑，並在測試後清除或依保存政策處理。
