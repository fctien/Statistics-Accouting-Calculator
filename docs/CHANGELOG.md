# 變更紀錄 CHANGELOG

## v0.2.0（2026-10-28）

- 導覽改為三大頁面：工程 ENG、統計 STAT、會計 ACCT，加上共用的設定；網址 `#<頁>/<項目>`，舊網址自動導向
- 工程頁：科學計算機（三角、對數、DEG／RAD）、單位換算、進位轉換與位元運算
- 統計頁：敘述統計、機率分配（常態、t、卡方、二項、Poisson，含分配圖）、信賴區間與檢定（z／t／比例 CI、t 檢定、卡方檢定）
- 會計頁：沿用 v0.1.0 的 TVM、AMORT、CF、ICONV、BOND、DEPR 與商業工具（毛利、損益兩平、Δ%、稅額、日期）
- 導覽改進：點頁籤回到該頁上次的子頁；頁籤改為純導覽（`aria-current`，不用 `role=tab`）；手機底部頁籤列的鍵盤順序與視覺一致
- Service Worker 快取名稱含殼檔案雜湊（SHELL_HASH），殼檔案一改就換快取、舊快取自動刪除
- 引擎新增 `dist`、`infer`、`describe`、`units`、`base` 模組與 golden 值（附出處）

## v0.1.0

- 仿 TI BA II Plus Professional 的財務／會計計算機 PWA：TVM、攤還、現金流、利率換算、統計、債券、折舊、商業工具、日期
- MicroPython（WebAssembly）於 Web Worker 執行 Python 引擎；可離線；情境儲存、JSON 匯出入、選用 Google Drive 同步
- 部署到 GitHub Pages
