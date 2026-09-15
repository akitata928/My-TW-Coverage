# MOPS XBRL 來源契約（Phase 0–1）

**查證日期：** 2026-09-15
**查證環境：** Mac mini，台灣網路，`curl`，TLS 憑證驗證開啟
**查證範圍：** 2330 台積電、2026 年第 2 季、合併報表

## 已確認的下載契約

基底 URL：

```text
https://mopsov.twse.com.tw
```

下載端點：

```text
GET /server-java/FileDownLoad
```

必要查詢參數：

| 參數 | 2330 測試值 | 意義 |
|---|---:|---|
| `functionName` | `t164sb01` | 資產負債表下載功能；其他報表 function 尚未在 Phase 0 完整驗證 |
| `step` | `9` | XBRL／iXBRL 下載步驟 |
| `co_id` | `2330` | 公司代號 |
| `year` | `2026` | 西元年；不是民國年 115 |
| `season` | `2` | 第 2 季 |
| `report_id` | `C` | 合併報表（Consolidated） |

可重現 URL：

```text
https://mopsov.twse.com.tw/server-java/FileDownLoad?functionName=t164sb01&step=9&co_id=2330&year=2026&season=2&report_id=C
```

## Mac mini 實測證據

- MOPS 官方基底首頁：HTTP **200**，回應為導向 `/mops/web/index` 的 HTML。
- 上述下載 URL：HTTP **200**。
- `Content-Disposition`：`attachment; filename="tifrs-fr1-m1-ci-cr-2330-2026Q2.html"`。
- 下載大小：**759,227 bytes**。
- `Content-Type` 宣告為 `charset=iso-8859-1`；內容實際以 UTF-8 XML／XHTML 開頭，包含 `tifrs-*` 與 `ifrs-full` namespace。
- 測試使用瀏覽器 User-Agent 與 Referer：`https://mopsov.twse.com.tw/mops/web/t203sb01`。
- 本次未使用 Cookie、未使用 `verify=false`、未繞過 CAPTCHA／IP 封鎖。
- 交接報告中的雲端環境 HTTP 403 **未在本機重現**；因此目前不能把 403 歸因為 MOPS 本身或套件本身，仍需保留「出口網路／雲端 IP／session／rate limit」的待驗證分類。

下載探測器 `scripts/probe_mops_xbrl.py` 將請求區分為：HTTP request、下載內容判定與 parser 執行三層。它固定使用 TLS 憑證驗證、User-Agent、Referer，不主動加入 Cookie；在本次 Mac mini 實測中，無 Cookie 已足以取得 `report_id=C`。暫態 408／425／429／5xx 會以有限次數退避重試，其他錯誤不重試。

## Phase 1 變體實測

| 變體 | HTTP | 內容判定 | 結論 |
|---|---:|---|---|
| `t164sb01`, `report_id=C` | 200 | 759,227 bytes，含 `tifrs-*`／`ifrs-full` | 成功下載候選 |
| `t164sb01`, `report_id=A` | 200 | 281 bytes，一般 HTML `d!!` 錯誤頁 | 不可視為個別報表支援 |
| `t164sb02`, `report_id=C` | 200 | 240 bytes，一般 HTML `d!!` 錯誤頁 | function 未驗證成功 |
| `t164sb03`, `report_id=C` | 200 | 240 bytes，一般 HTML `d!!` 錯誤頁 | function 未驗證成功 |

這些結果證明 HTTP 200 不能單獨代表下載成功；探測器必須檢查內容是否為 iXBRL／ZIP 候選。Phase 1 對 A、損益表與現金流量表只記錄為未驗證，不猜測 endpoint。

## 請求規則與安全界線

1. 下載器必須使用 TLS 憑證驗證，不得使用 `verify=False`。
2. User-Agent、Referer、Cookie 是否必要，需以逐項實測記錄；不能把瀏覽器 session 或帳號資訊寫入 repo。
3. HTTP 403、429、5xx、timeout、空內容與非 XBRL 回應必須分開分類。
4. 不能繞過 CAPTCHA、robots、IP 封鎖或其他 MOPS 存取控制。
5. 原始財報是否保存，需另行確認授權、檔案大小與保存期限；Phase 1 只提交 metadata，不提交原始下載檔。

## 尚未完成、留給 Phase 2 的項目

- Arelle 是否能完整解析已下載的 2330／2026 Q2 iXBRL。
- TIFRS namespace、context、unit、decimals 與 label 的解析契約。
- 損益表與現金流量表在同一 iXBRL package 內的 presentation／role 映射。
- 403 是否由雲端出口 IP、MOPS 政策、rate limit 或 request context 造成。
- 是否存在 CAPTCHA、頻率限制及非交易／未申報季度的回應差異。

## Phase 0–1 Gate 結論

**通過。** 已完成可重跑的下載探測、2330／2026 Q2／C metadata、HTTP 200 錯誤頁分類與退避策略；仍未宣稱 A／其他報表 function 或 Arelle parser 已支援。
