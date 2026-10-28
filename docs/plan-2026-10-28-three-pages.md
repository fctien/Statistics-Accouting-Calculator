# BACalc 三大頁面整合與使用說明影片 計畫

- 日期：2026-10-28
- 狀態：**待使用者確認**
- 基準：`impl` 分支 ccba449（v0.1，31 個 Task 完成）

## 目標

1. App 最上層分成三大頁面：**工程**、**統計**、**會計**，每頁有自己的子選單；計算機紙帶、記憶、設定三頁共用
2. 做完後自動產生**實際操作錄影＋中文旁白＋字幕**的使用說明 mp4

## 使用者已決定的範圍（2026-10-28）

| 頁面 | 內容 |
|---|---|
| 工程 | 科學計算機（`engineering-calculator` 既有功能＋三角函數、度／弧度）、單位換算、進位轉換 |
| 統計 | 現有 STAT（單變數、LIN/LN/EXP/PWR 迴歸、預測）、機率分配、信賴區間與檢定、敘述統計擴充 |
| 會計 | 現有 TVM、AMORT、CF、ICONV、BOND、DEPR、毛利、損益兩平、Δ%、稅額、日期 |
| 影片 | 實際操作錄影＋旁白，約 8–12 分鐘 |

## 已確認的環境（2026-10-28 實測）

- MicroPython 1.29.0-6：`math` 有 `erf`、`erfc`、`gamma`、`lgamma`、`sin`、`asin`、`atan2`、`log10`、`log2`、`radians`、`degrees`；**沒有 `cbrt`**（自寫，負數也要支援）
- ffmpeg：Python 套件 `imageio_ffmpeg` 內附 v7.1；`moviepy` 2.1.2；Playwright 在上層資料夾 `node_modules`（已安裝，不新增）
- 中文語音：Windows OneCore Yating（pywin32 SAPI，離線；edge-tts 自 2026-10-13 回 403）

## 原則（沿用 CLAUDE.md）

- MVC；engine 只用可攜子集；**絕不產生看起來正常但錯誤的數字**
- 每個新功能都有 golden 值，出處為 **Excel 公式**（Excel COM 產生，例：`=SIN(...)`、`=CONVERT(...)`、`=DEC2HEX(...)`、`=NORM.S.DIST(...)`、`=T.TEST(...)`），CPython 與 MicroPython 雙執行環境比對
- Subagent-Driven：每個 Task 實作 → 審查 → 修正 → 再審；裁定寫入 ledger
- 不安裝套件；PowerPoint 開著時不碰

## Task 清單

### A. 先修殘留問題

| Task | 內容 | 驗收 |
|---|---|---|
| A0 | 修 v0.1 殘留：選擇性 clearStale 讓過期標記卡住、擋住「帶入攤還」；檔案匯出入去除 gdrive 本機鍵 | 回歸測試＋瀏覽器重現步驟不再發生 |

### B. 工程頁引擎

| Task | 內容 | golden 出處 |
|---|---|---|
| B1 | `engine/calc.py` 擴充：`sin cos tan asin acos atan`、`log`（log₁₀）、`cbrt`（自寫，含負數）、常數 `π`、`e`、角度模式 DEG／RAD（設定值，經 bridge 傳入）；定義域錯誤一律回錯誤（例 `asin(2)`、`tan(90°)`） | `=SIN(RADIANS(30))`、`=DEGREES(ASIN(0.5))`、`=LOG10()`、`=POWER(-27,1/3)` 改用 `=-POWER(27,1/3)` |
| B2 | `engine/units.py` 單位換算：長度、質量、溫度（含仿射換算）、壓力、能量、面積、體積、速度、時間；不同類別互換回錯誤 | `=CONVERT(1,"mi","km")` 等，每類至少 3 筆 |
| B3 | `engine/base.py` 進位轉換：2／8／10／16 進位互換、二補數位寬 8／16／32／64、位元運算 AND OR XOR NOT 與左右移；超出位寬回錯誤 | `=DEC2BIN()`、`=HEX2DEC()`、`=BITAND()`、`=BITLSHIFT()` |

### C. 統計頁引擎

| Task | 內容 | golden 出處 |
|---|---|---|
| C1 | `engine/describe.py` 敘述統計：中位數、眾數（多眾數全列）、四分位數（與 Excel `QUARTILE.INC` 一致）、IQR、偏態、峰態、全距、變異係數 | `=MEDIAN()`、`=MODE.MULT()`、`=QUARTILE.INC()`、`=SKEW()`、`=KURT()` |
| C2 | `engine/dist.py` 機率分配：常態、t、卡方、二項、Poisson 的機率密度／累積機率／反查（反查以 `solver.find_root`）；不完全 Beta／Gamma 用連分數自寫；參數不合法回錯誤 | `=NORM.DIST()`、`=NORM.INV()`、`=T.DIST()`、`=T.INV()`、`=CHISQ.DIST()`、`=CHISQ.INV()`、`=BINOM.DIST()`、`=POISSON.DIST()` |
| C3 | `engine/infer.py` 信賴區間與檢定：平均數 CI（z、t）、比例 CI、單樣本 t、兩獨立樣本 t（合併變異數與 Welch）、成對 t、卡方適合度、卡方獨立性；回傳統計量、自由度、p 值、結論文字 | `=CONFIDENCE.T()`、`=CONFIDENCE.NORM()`、`=T.TEST(,,2,1/2/3)`、`=CHISQ.TEST()` |

每個 C Task 都要在 MicroPython 上跑同一份 golden；連分數的收斂失敗回錯誤，不回未收斂值。

### D. 介面

| Task | 內容 | 驗收 |
|---|---|---|
| D1 | 導覽改三層：頂端「工程｜統計｜會計」三大頁（手機為底部三分頁），每頁子選單；網址 `#eng/calc`、`#stat/dist`…，舊網址（`#tvm` 等）自動導向新位置；計算機紙帶、記憶、設定共用 | 舊情境、匯出入不受影響；手機與桌面版面截圖 |
| D2 | 工程頁畫面：科學計算機（擴充按鍵：sin cos tan、log、∛、π、e、DEG/RAD 切換）、單位換算（類別→單位→即時換算）、進位轉換（四欄同步＋位寬＋位元運算） | 每頁一個 golden 值在瀏覽器實測 |
| D3 | 統計頁畫面：STAT（搬移）、敘述統計（貼上資料）、機率分配（分配選單＋三種計算）、信賴區間與檢定（選檢定類型→輸入→結果與結論） | 同上 |
| D4 | 整合驗證：`verify_all` 全過、突變測試加入新模組、`e2e/checklist.md` 擴充、SHELL_HASH 更新、版本 0.2.0 | verify_all log PASS |

### E. 使用說明影片

| Task | 內容 | 驗收 |
|---|---|---|
| E1 | `teaching/video/script.py` 單一來源：每段的旁白文字、操作步驟（要點哪個元素、輸入什麼）、預期畫面數值（引用 golden） | 每段數值與引擎一致的測試 |
| E2 | `teaching/video/record.mjs`：用上層既有 Playwright 開本機伺服器上的 App，依腳本逐段自動操作並錄影（1280×720），每段輸出一個 webm；操作時加游標高亮與字卡 | 每段錄影存在、長度合理 |
| E3 | `teaching/video/narrate.py`：OneCore Yating 合成每段旁白 wav；產生 SRT 字幕；用 imageio_ffmpeg 把每段錄影與旁白對齊（影片依旁白長度延長或剪裁）、加片頭片尾，輸出 `BACalc_使用說明.mp4` | 用 ffprobe 檢查長度、音軌、解析度；抽 5 張影格目視 |

影片段落草案：片頭 → 安裝成手機 App → 三大頁面導覽 → 工程（科學計算、單位、進位）→ 統計（敘述、迴歸、分配、檢定）→ 會計（TVM、攤還、現金流、稅額）→ 情境儲存與匯出 → 片尾

## 需要你親自做的事（不變）

- GitHub Settings → Pages → Source 設成 GitHub Actions（目前仍未啟用）
- 關閉 PowerPoint 後才能產生教材 PDF（影片不需要 PowerPoint）

## 風險

| 風險 | 處理 |
|---|---|
| 不完全 Beta／Gamma 自寫的精度 | 以 Excel golden 比對，容差 1e-9；極端參數對不上就回錯誤並記錄限制 |
| Excel `CONVERT` 單位代碼與 App 顯示名稱不同 | 對照表放 `units.py`，測試逐一對應 |
| Yating 語音念英文縮寫不自然 | 旁白稿寫成中文讀法（例「T V M」→「貨幣時間價值」） |
| 錄影時引擎尚未就緒 | 錄影腳本先等「就緒」狀態再操作 |
| 既有教學 tag 與教材（step0–step8）以 v0.1 為準 | 不改舊 tag；新功能另打 tag `v0.2.0`，教材日後另行更新 |

## 預估

約 13 個 Task（A0、B1–B3、C1–C3、D1–D4、E1–E3），沿用 Subagent-Driven 流程。
