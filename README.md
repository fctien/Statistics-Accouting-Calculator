# BACalc

仿 TI BA II Plus Professional 的財務／會計計算機，是一個可離線使用的 PWA（Progressive Web App，漸進式網頁應用程式）。
Python 計算引擎透過 MicroPython（WebAssembly，在 Web Worker 中）於瀏覽器執行，純靜態檔，手機與電腦皆可用。
同時是教學案例：每個開發階段都打了 git tag（`step0`～`step9`）。

**線上網址**：<https://fctien.github.io/Statistics-Accouting-Calculator/>（路徑區分大小寫）

**目前版本**：v0.2.0（變更紀錄見 [docs/CHANGELOG.md](docs/CHANGELOG.md)）

## 設計原則

- 絕不產生看起來正常但錯誤的數字：算不出來就回報原因，不用 0 或預設值
- 資料只存本機（IndexedDB）；Google Drive 同步預設關閉，使用者設定後才啟用
- 算式用自寫遞迴下降剖析器（recursive descent parser），不使用 `eval`
- 金額以「分」整數計算，日期用序數日（ordinal day），不依賴 decimal、datetime

## 功能（三大頁面，v0.2.1）

頂端（手機為底部）三個頁籤：工程 ENG｜統計 STAT｜會計 ACCT，另有共用的設定。網址格式 `#<頁>/<項目>`，例：`#acct/tvm`；舊網址自動導向。

| 頁面 | 項目 | 內容 |
|---|---|---|
| 工程 ENG | 科學計算機 CALC | 算式、AOS／Chain、DEG／RAD、三角與對數函式、紙帶 Tape、`ANS`、記憶 M0–M9 |
| | 單位換算 UNITS | 長度、質量、溫度、壓力等類別換算 |
| | 進位轉換 BASE | BIN／OCT／DEC／HEX、位元寬度與有號／無號、位元運算 |
| 統計 STAT | 迴歸與單變數 | 1-V／LIN／Ln／EXP／PWR 統計與迴歸、預測 |
| | 敘述統計 DESC | 平均、中位數、眾數、四分位數、變異數、偏態、峰度 |
| | 機率分配 DIST | 常態、t、卡方、二項、Poisson 的 pdf／cdf／inv 與分配圖 |
| | 信賴區間與檢定 INFER | z／t／比例信賴區間、單樣本／兩樣本／成對 t 檢定、卡方適合度與獨立性 |
| 會計 ACCT | TVM、AMORT、CF、ICONV、BOND、DEPR | 貨幣時間價值、攤還、現金流 NPV／IRR、利率換算、債券、折舊 |
| | PROFIT、BRKEVN、Δ%、TAX、DATE | 毛利與加成、損益兩平、百分比變動、稅額、日期 |
| 設定 FORMAT | | 小數位數、千分位、日期格式、運算順序 AOS／Chain、角度 DEG／RAD、深色模式 |

另有情境儲存、JSON 匯出入、選用的 Google Drive 同步。

## 安裝到手機（PWA）

先在手機瀏覽器開啟上面的線上網址，**第一次需連網**，等畫面顯示 Python 就緒後即可離線使用。

- **Android（Chrome）**：右上角選單 ⋮ → 「安裝應用程式」或「加到主畫面」
- **iPhone／iPad（Safari）**：下方分享鈕 → 「加入主畫面」（建議用 Safari；其他 iOS 瀏覽器未測試）
- **離線**：已在電腦版瀏覽器驗證載入一次後斷網仍可計算；手機實機（含飛航模式）尚未驗證，請自行確認
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

## 重建教材

```
python run_all.py
```

依序執行 `tools/verify_all.py --quick` → `teaching/build_cards.py`（Prompt 卡）→ `teaching/deck/build_deck.py`（簡報 pptx）
→ `teaching/export_pdf.py`（PDF）→ `teaching/make_package.py --zip`（學生版 zip），產生 `logs/run_all-*.html`（含 commit hash 與人工目視清單）。

- git 工作樹必須乾淨（verify_all 的規則）；build_cards、build_deck 的輸出可重現（pptx 固定 zip 時間戳），內容不變時與 commit 逐位元組相同，不會弄髒工作樹
- 每次執行會新增 `logs/verify-*.html` 與 `logs/run_all-*.html`：重跑前先 commit 這些 log（`git add logs/ && git commit -m "log: run_all 紀錄"`），否則下一次會被乾淨檢查擋下；停下或失敗時 run_all 也會印出這段提示
- 簡報依賴 repo 外的 `deck_kit`：預設在上一層資料夾 `../deck_kit/deck_kit.py`，可用環境變數 `DECK_KIT` 指定；
  上一層資料夾還要有肖像 `Tien 肖像.jpg` 與校徽 `Taipei Tech Logo.png`（可用 `DECK_RES` 指定所在資料夾）；需要 `python-pptx`
- PDF 用 PowerPoint COM（pywin32）匯出，需要 Windows＋PowerPoint：**PowerPoint 正在執行時不會匯出**（避免影響開著的檔案），
  `export_pdf.py` 回 2、`run_all.py` 停在這一步；關閉 PowerPoint 後重跑。tasklist 失敗或輸出無法解析時同樣視為「可能在執行」而不匯出；匯出途中失敗會刪掉本次的 PDF
- 學生版 zip（`teaching/out/v0.2/BACalc_AI_student.zip`、`BACalc_EMBA_student.zip`）只放 Prompt 卡、簡報 PDF、
  `docs/google-oauth-setup.html` 與學生說明，不含 pptx 與講稿；沒有 PDF，或 PDF 比 pptx 舊，就不產生 zip
- 課前演練紀錄：`teaching/rehearse.md`

### 使用說明影片（實際操作錄影＋中文旁白＋字幕）

```
python teaching/video/run_video.py
```

`build_web` → 旁白合成（`narrate.py`，Windows OneCore 語音 Microsoft Yating，pywin32 SAPI）→ 錄影（`record.mjs`，Playwright，
App 畫面 1280×640）→ 合成（`build_video.py`，imageio_ffmpeg：下方加 80px 字幕帶，輸出 1280×720，字幕不蓋住 UI）
→ 印出長度／解析度／音軌並抽 5 張影格到 `teaching/video/out/frames/`。

- 本機伺服器（`python -m http.server`，根目錄 `web/`）由程式啟動、結束時一定關閉；port 8765 被占用時不動它，改用系統給的空 port
- 全程約 10 分鐘以上（錄影本身約 9 分鐘）；`record.mjs` 可用 `--only <段落id,…>` 只重錄部分段落（與既有 `build/record.json` 合併），
  再以 `--skip-record` 只重做旁白與合成

- 單一來源 `teaching/video/script.py`：每段旁白、操作步驟與預期畫面；`tests/test_video_script.py` 以引擎實算核對每個數值
- 錄影時每段都核對 expect，不符就失敗、不產生影片
- 輸出 `teaching/video/out/BACalc_使用說明.mp4`（燒入字幕，不進 git）與 `BACalc_使用說明.srt`（外掛字幕）
- 需要上一層資料夾的 `node_modules/playwright`（含 Chromium）、`imageio_ffmpeg`、`pywin32`；`--skip-record` 沿用既有錄影

## 文件

- [變更紀錄 CHANGELOG](docs/CHANGELOG.md)
- [規格書](docs/spec-2026-10-19.md)
- [實作計畫](docs/plan-2026-10-20.md)
- [Google OAuth 申請說明](docs/google-oauth-setup.html)（僅在要用 Google Drive 同步時需要）

## 授權

尚未選定授權條款（license），目前未附 LICENSE 檔，預設保留所有權利。
