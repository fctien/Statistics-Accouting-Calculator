# BACalc 專案規範

仿 TI BA II Plus Professional 的財務／會計計算 PWA。Python 計算引擎透過 Pyodide 在瀏覽器執行，
純靜態檔、可離線，手機與電腦皆可用。同時是教學案例（`teaching/`）。

規格書：`docs/spec-2026-10-19.md`（HTML 版同名）

## 不可退讓的原則

1. **MVC**：Model 是 `engine/*.py`（純 Python、無 I/O、不依賴瀏覽器）；Controller 是 `engine/bridge.py` 與 `web/js/app.js`；View 是 HTML／CSS
2. **絕不產生看起來正常但錯誤的數字**：算不出來就回 `ok: false` 加原因，不用 0、不用預設值、不回傳未收斂的猜測值
3. **資料只存本機**（IndexedDB）；Google Drive 同步預設關閉，使用者設定後才啟用
4. 計算機算式用 AST 白名單解析，**禁止 `eval`**
5. golden 值必須附出處（TI Guidebook 頁碼或 Excel 公式），對不上就回報，不硬湊

## 常用指令

- 引擎測試：`python -m pytest -q`
- 轉 HTML 文件：`python tools/md2html.py docs/<檔名>.md`

## 工作流程

- 改完程式先跑 `pytest` 再回報
- 每次驗證產生 `logs/verify-*.html`，記錄 commit hash；跑之前確認 git 乾淨
- 每次工作結束前把過程追加到 `DEVLOG.md`（需求／做法／產出／驗證／問題與修正／待辦），只追加不改寫
- 安裝套件、刪除檔案、推送 GitHub 前先問使用者

## 程式風格

- Python、PEP 8；註解用繁體中文，重要名詞附英文
