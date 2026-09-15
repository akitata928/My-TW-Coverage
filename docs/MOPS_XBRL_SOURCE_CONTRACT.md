# MOPS XBRL 來源契約（Phase 0）

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

## 請求規則與安全界線

1. 下載器必須使用 TLS 憑證驗證，不得使用 `verify=False`。
2. User-Agent、Referer、Cookie 是否必要，需以逐項實測記錄；不能把瀏覽器 session 或帳號資訊寫入 repo。
3. HTTP 403、429、5xx、timeout、空內容與非 XBRL 回應必須分開分類。
4. 不能繞過 CAPTCHA、robots、IP 封鎖或其他 MOPS 存取控制。
5. 原始財報是否保存，需在 Phase 1 另行確認授權、檔案大小與保存期限；Phase 0 不提交原始下載檔。

## 尚未完成、留給 Phase 1 的項目

- `report_id=A` 個別報表 URL 是否可用。
- 損益表與現金流量表的 `functionName`／參數組合。
- session cookie、User-Agent、Referer 的最小必要集合。
- 403 是否由雲端出口 IP、MOPS 政策、rate limit 或 request context 造成。
- 是否存在 CAPTCHA、頻率限制及非交易／未申報季度的回應差異。

## Phase 0 Gate 結論

**通過。** 已有可審查的官方來源契約、Mac mini 實測證據、403 原因分類，以及明確的 Phase 1 驗證步驟。這不代表已完成下載器、Arelle parser 或全量財報支援。
