# BACalc

仿 TI BA II Plus Professional 的財務／會計計算機，是一個可離線使用的 PWA（Progressive Web App，漸進式網頁應用程式）。
Python 計算引擎透過 MicroPython（WebAssembly，在 Web Worker 中）於瀏覽器執行，純靜態檔，手機與電腦皆可用。
同時是教學案例：每個開發階段都打了 git tag（`step0`～`step9`）。

**線上網址**：<https://fctien.github.io/Statistics-Accouting-Calculator/>（路徑區分大小寫）

## 設計原則

- 絕不產生看起來正常但錯誤的數字：算不出來就回報原因，不用 0 或預設值
- 資料只存本機（IndexedDB）；Google Drive 同步預設關閉，使用者設定後才啟用
- 算式用自寫遞迴下降剖析器（recursive descent parser），不使用 `eval`
- 金額以「分」整數計算，日期用序數日（ordinal day），不依賴 decimal、datetime

## 功能（工作表 Worksheet）

| 工作表 | 內容 |
|---|---|
| 計算機 CALC | 算式、AOS／Chain、紙帶 Tape、`ANS` |
| 記憶 MEM | M0–M9、累加 Σ |
| TVM | N、I/Y、PV、PMT、FV、P/Y、C/Y、BGN／END，任一欄可求解 |
| AMORT | 分期攤還（amortization）與完整攤還表，可匯出 CSV |
| CF | 現金流 NPV、IRR、NFV、PB、DPB、MIRR |
| ICONV | 名目利率 NOM 與有效利率 EFF 互換 |
| STAT | 1-V／LIN／Ln／EXP／PWR 統計與迴歸、預測 |
| BOND | 債券價格 PRI、殖利率 YLD、應計利息 AI |
| DEPR | SL／SYD／DB／DBX 折舊表 |
| 商業 | 毛利與加成、損益兩平、百分比變動、日期、稅額 |
| 設定 FORMAT | 小數位數、千分位、日期格式、運算順序、深色模式 |

另有情境儲存、JSON 匯出入、選用的 Google Drive 同步。

## 安裝到手機（PWA）

先在手機瀏覽器開啟上面的線上網址，**第一次需連網**，等畫面顯示 Python 就緒後即可離線使用。

- **Android（Chrome）**：右上角選單 ⋮ → 「安裝應用程式」或「加到主畫面」
- **iPhone／iPad（Safari）**：下方分享鈕 → 「加入主畫面」（必須用 Safari，其他瀏覽器不行）
- **離線**：安裝並載入一次後，開飛航模式也能操作
- **注意**：iOS 在一段時間沒開啟 App 或儲存空間不足時，可能清除本機資料（IndexedDB）。重要資料請定期用「JSON 匯出」備份

## 本機開發

```
npm ci
python tools/build_web.py
python -m http.server 8765 -d web
```

然後開 <http://localhost:8765/>。`web/py/` 由建置工具產生（已被 git 忽略），改過 `engine/` 後要重跑 `build_web.py`。
`selftest.html` 會在瀏覽器內以 MicroPython 重跑全部 golden。

## 測試

```
python tools/verify_all.py          完整驗證（含突變測試，較慢），產生 logs/verify-*.html
python tools/verify_all.py --quick  略過突變測試
python -m pytest -q                 只跑 Python 測試
```

跑 `verify_all.py` 前 git 工作樹必須乾淨。GitHub Actions（`.github/workflows/pages.yml`）在 push 到 `main` 時跑測試並部署；
CI 不跑突變測試（太慢），完整驗證請在本機執行。

## 專案結構（MVC）

| 層 | 位置 | 說明 |
|---|---|---|
| Model | `engine/*.py` | 純 Python 計算引擎，無 I/O，限 CPython 與 MicroPython 共通子集 |
| Controller | `engine/bridge.py`、`web/js/app.js` | 統一入口與 Web Worker 橋接 |
| View | `web/index.html`、`web/css/`、`web/js/views/` | 畫面與表單 |

其他：`golden/`（golden 值驗證）、`tests/`（pytest 與 JS 測試）、`tools/`（建置與驗證）、`web/vendor/`（鎖定版本的 MicroPython）、`e2e/checklist.md`（手動檢查表）、`logs/`（驗證紀錄）。

## 教學步驟（git tag）

| Tag | 內容 |
|---|---|
| `step0` | 兩層 CLAUDE.md |
| `step1` | 用 plan mode 規劃 |
| `step2` | TDD：TVM 引擎 |
| `step3` | 其他工作表引擎與突變測試 |
| `step4` | PWA 殼、MicroPython 與 Web Worker 橋接 |
| `step5` | 人性化 UI |
| `step6` | 本機儲存與 JSON 匯出入 |
| `step7` | Google Drive 同步（選用，未實測） |
| `step8` | 自我驗證 Skill |
| `step9` | 部署到 GitHub Pages、安裝到手機 |

## 文件

- [規格書](docs/spec-2026-10-19.md)
- [實作計畫](docs/plan-2026-10-20.md)
- [Google OAuth 申請說明](docs/google-oauth-setup.html)（僅在要用 Google Drive 同步時需要）

## 授權

尚未選定授權條款（license），目前未附 LICENSE 檔，預設保留所有權利。
