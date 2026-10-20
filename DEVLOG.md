# BACalc 開發歷程（DEVLOG）

只追加不改寫；失敗的嘗試也要寫明原因。

---

## 2026-10-19　規劃與規格書

**需求**
- 仿 BA II Plus／Professional 的會計計算 App，Python＋PWA，手機與電腦可用
- 功能：記憶與累加、商業與稅務、統計、利率轉換、現金流、分期攤還、TVM、顯示與位數設定；輸入要更人性化
- 資料存本機，可自行設定 Google Drive 或雲端上傳；每項功能都要自我測試
- 做成教學案例：CLAUDE.md → Prompt → PPT＋Prompt 卡，step by step

**做法**
- 用 brainstorming 流程：先說明理解 → 提三種架構（Pyodide／FastAPI／JS 重寫）→ 使用者選定 → 寫規格書
- 使用者決定：Pyodide 離線、放在 `Tien Research\BACalc`、JSON 匯出入＋Google Drive、教材 AI Agent 與 EMBA 兩版
- 參考既有 MoneyBook PWA 的規則（不產生錯數字、sw.js 快取清單、版本號同步）

**產出**
- `docs/spec-2026-10-19.md`、`docs/spec-2026-10-19.html`
- `CLAUDE.md`、`DEVLOG.md`、`tools/md2html.py`、`.gitignore`

**驗證**
- 規格自我檢查：無 TBD、章節間一致、範圍可拆成 M1–M6
- `tools/md2html.py` 實際轉出 HTML 並檢查表格有渲染

**問題與修正**
- 第一次用 AskUserQuestion 時使用者只回了資料夾路徑，其餘三題重新詢問後才確定

**待辦**
- 等使用者審閱規格書 → 寫實作計畫（writing-plans）→ 再次確認後開始 M1

---

## 2026-10-20　規格修訂：手機首次載入慢

**需求**
- 使用者指出 Pyodide 在手機首次載入慢，要求找解法

**做法**
- 實測 jsDelivr 傳輸大小：Pyodide 0.28.3 約 5.3 MB（原始約 12 MB）；MicroPython 1.29.0 WebAssembly 版約 0.23 MB
- 提三方案（MicroPython／Pyodide 優化／並用），使用者選 A：MicroPython＋共用優化（殼先顯示、Web Worker、安裝時預先快取、啟動計時），M2 先 spike 驗證雙精度，不符退回 Pyodide

**產出**
- 規格書 1.1、1.2、1.3、2.2、2.3、4、5.2、6、7、8 節修訂；CLAUDE.md 加可攜子集原則

**驗證**
- grep 確認規格書中 Pyodide 只剩在比較與退路段落；HTML 重新產生

**問題與修正**
- 第一次回覆時使用者訊息只有「規格書要修改：」沒有內容，請使用者補充後才收到真正需求
- 手機實際啟動秒數仍未量測（不確定），列入 M2
- 自我檢查發現 MicroPython 沒有 `ast`，原「AST 白名單解析算式」不可行 → 改為自寫遞迴下降剖析器

**待辦**
- 使用者審閱修訂版規格書 → 寫實作計畫

---

## 2026-10-20　實作計畫

**需求**
- 使用者同意修訂版規格書，要求寫實作計畫

**做法**
- 用 writing-plans 技能；確認環境：pytest 7.4、pywin32、python-pptx 1.0.2、Node 22、Excel 16、pptxgenjs 都已安裝 → golden 值改由 Excel COM 公式產生（PMT、RATE、IRR、MIRR、PRICE、YIELD、DAYS360…），JSON 進 repo
- 31 個 Task 分 M1～M6，教學 tag step0～step9 對應到 Task

**產出**
- `docs/plan-2026-10-20.md`、`.html`

**驗證**
- 用 Python 核對計畫中手算的測試值：2026-10-20 是星期二、2026-01-01 加 59 天是 03-01、σx=2、含稅 1 元未稅 0.95 元、`%.15g` 對 2.675 輸出 2.675

**問題與修正**
- 自我檢查發現：算式文法讓 `-2^2` 變成 4（改成負號優先序低於 ^）；算式千分位逗號和 nCr 參數逗號衝突（算式不接受千分位）；TVM golden 測試的 unknown 讀法和 bridge 留空格式不一致；Task 19 取得 CPython 結果的方式太模糊 → 都已修正

**待辦**
- 使用者審閱計畫、選擇執行方式；決定 SYD／DBX 部分年度、稅率預設、Playwright 三個縮小範圍項目

---

## 2026-10-20　實作 Task 0＋Task 1（pytest 設定、統一回傳格式、可攜性檢查）

**需求**
- Task 0：pytest 設定與 `tests/conftest.py`（fixture `golden_cases`）；Task 1：`engine/result.py`（`ok`／`err`／`is_finite`）與 `tools/check_portable.py`
- tag `step0`、`step1` 已存在，略過打 tag

**做法**
- TDD：先寫 `tests/test_result.py`、`tests/test_portable.py`，確認 ImportError（RED），再實作到全綠
- `ok()` 遞迴檢查巢狀 list／tuple／dict 內的 float，非有限數回 `err("計算結果超出範圍（溢位）", field=<鍵>)`
- `check_portable` 用 CPython `ast` 掃 import（禁用清單＋白名單 math／json／engine），正規式掃 `eval(`／`exec(`
- `rel_close(a, b, tol)` 放在 `tests/conftest.py`；`golden_cases` 檔案不存在時 `pytest.skip`

**產出**
- `pytest.ini`、`engine/__init__.py`、`golden/__init__.py`、`tests/__init__.py`、`tools/__init__.py`、`tests/conftest.py`、`engine/result.py`、`tools/check_portable.py`、`tests/test_result.py`、`tests/test_portable.py`

**驗證**
- RED：兩個測試檔收集階段 ModuleNotFoundError；GREEN：`python -m pytest` 13 passed；`tools/check_portable.py engine` exit 0，對含 `import decimal` 的目錄 exit 1

**問題與修正**
- 失敗的嘗試：直接 `python -m pytest` 因本機 site-packages 的 hydra pytest 外掛（與 Python 3.11 dataclass 不相容）載入時崩潰 → 在 `pytest.ini` addopts 加 `-p no:hydra_pytest` 停用該外掛（未安裝／移除任何套件）
- 白名單額外包含 `engine`（本專案內部匯入），計畫只列禁用清單，屬保守擴充

**待辦**
- Task 2 起的引擎模組；golden/excel.json 尚未產生

## 2026-10-20 Task 2：golden 案例與 Excel 產生器

**需求**
- 產生之後所有引擎任務共用的 golden 測試資料（Excel 公式為出處），含 8 張工作表、runner 與檔案測試

**做法**
- `golden/cases.py` 以字面數字定義 51 筆案例（bridge 請求格式 sheet/action/inputs/settings）；amort 的 PMT 由 `pmt_formula` 在同一次 Excel 執行中算出並填入
- `tools/make_golden_excel.py` 用 `DispatchEx` 開新的隱藏 Excel 實例，`Application.Evaluate` 求值（支援陣列常數），不存檔、finally 只 Quit 自己的實例
- `golden/runner.py` 提供 `run`／`dump`／`load`；CLI 放在 `tools/golden_dump.py`（避免 golden/ 出現 `import sys` 違反可攜檢查）

**產出**
- `golden/cases.py`、`golden/runner.py`、`tools/make_golden_excel.py`、`tools/golden_dump.py`、`tests/golden/excel.json`（51 筆）、`tests/test_golden_file.py`

**驗證**
- RED：excel.json 不存在時 5 個測試 FileNotFoundError；GREEN：產生後 `python -m pytest -q` 全過；`check_portable golden` 與 `engine` exit 0

**問題與修正**
- 失敗的嘗試：第一次執行 make_golden_excel 因 `tests/golden/` 目錄不存在而寫檔失敗（Excel 求值本身成功）→ 加 `os.makedirs`
- 計畫要求的 `python -m golden.runner --dump` 未實作為模組 CLI，改為 `python tools/golden_dump.py`
- 未納入 cashflow 的 PB／DPB（Excel 無對應內建函式，不自行發明）

**待辦**
- Task 16 之後 `tools/golden_dump.py` 才能實際執行；PB／DPB、amort 之 TI 符號慣例待與 TI Guidebook 對照

## 2026-10-20 Task 2 修正輪 1
**問題與修正**
- amort BAL 改用 `=-FV(...)`（與 PV 同號、對應 TI BAL 顯示），重產 excel.json：BAL y1=296315.96486317005、y2=292404.7065002685；測試與可攜檢查通過

## 2026-10-20 Task 3＋4 money／dates／solver
**需求**
- 分整數金額（money）、序數日日期（dates）、共用求根器（solver：牛頓＋二分）

**做法**
- TDD：先寫三個測試檔（RED：ModuleNotFoundError），再實作
- days_360 先查本機 Excel DAYS360(FALSE) 實測 2 月底行為，依實測實作
- solver：牛頓法數值微分，發散／出界／微分為 0 時退二分，二分僅限兩端異號

**產出**
- engine/money.py、engine/dates.py、engine/solver.py；tests/test_money.py、test_dates.py、test_solver.py

**驗證**
- 全部 pytest 通過（30 項）；check_portable engine／golden exit 0；golden date 5 筆全符

**問題與修正**
- 失敗的嘗試：稅率分母第一次誤用 1000000（rate_bp 為萬分比，應為 10000），測試 RED 後修正
- 計畫稱 Excel FALSE 模式不特別處理 2 月底，但 Excel 實測：DAYS360(2026-02-28, 2026-03-31)=30、(2028-02-29,2028-03-31)=30、(2028-02-28,2028-03-31)=33、(2026-02-28,2026-02-28)=-2。故起日為 2 月最後一日視為 30，終日不因 2 月底調整；golden 現有 5 筆不涉及 2 月底，不受影響

**待辦**
- 可考慮將 Excel 2 月底案例加入 golden（需使用者同意改 golden 資料）

## 2026-10-20 Task 4 修正輪 1
**需求**
- 二分法須遵守呼叫端的 max_iter 上限

**做法**
- `_bisect` 迴圈由 `max(max_iter, 200)` 改為 `max_iter`；新增 test_max_iter_respected

**產出**
- engine/solver.py、tests/test_solver.py

**驗證**
- test_solver 4 項通過；全套 pytest 31 項通過；check_portable exit 0

**問題與修正**
- 失敗的嘗試：測試第一版用線性函數 x-0.3 且 guess=5，牛頓兩步即收斂，未觸發二分，測試無效 → 改用立方根函數（牛頓必發散）

**待辦**
- 無

## 2026-10-20 Task 5 TVM 貨幣時間價值
**需求**
- 實作 engine/tvm.py：N、I/Y、PV、PMT、FV 求解，含 P/Y、C/Y、BGN/END

**做法**
- TDD：先寫 tests/test_tvm.py（RED：ModuleNotFoundError），再實作（GREEN）
- period_rate／tvm_residual／solve；|i|<1e-12 走線性式；求 N 用對數式；求 I/Y 用 find_root（-0.9999, 10]，猜測 0.01
- 捕捉 OverflowError／ZeroDivisionError 回溢位錯誤；缺 P/Y、C/Y 或必要欄位回錯誤

**產出**
- engine/tvm.py、tests/test_tvm.py

**驗證**
- 全套 pytest 通過（39 項）；check_portable exit 0；golden tvm 案例皆在容差內

**問題與修正**
- 失敗的嘗試：測試 N 無解案例（PV、PMT 同號、i>0）原實作回負的 N（約 -8.3），看似正常實則無意義 → 求出 N <= 0 一律回錯誤

**待辦**
- Task 6（AMORT）使用 tvm_residual／period_rate

## 2026-10-20 Task 6＋8 AMORT 分期攤還、ICONV 利率轉換
**需求**
- 實作 engine/amort.py（amort、schedule）與 engine/iconv.py（nom_to_eff、eff_to_nom）

**做法**
- TDD：先寫 test_amort.py、test_iconv.py（RED：ModuleNotFoundError），再實作（GREEN）
- AMORT 逐期遞推：INT=-(餘額×i)、PRN=PMT-INT、BAL=BAL+PRN；BGN 第 1 期利息 0；不做中途四捨五入
- ICONV：EFF=((1+NOM/CY)^CY-1)，NOM 為其反函數；CY<=0 回 err("CY")

**產出**
- engine/amort.py、engine/iconv.py、tests/test_amort.py、tests/test_iconv.py

**驗證**
- 全套 pytest 46 項通過；golden amort 5 項、iconv 3 項皆在容差內；check_portable exit 0

**問題與修正**
- 無失敗嘗試；schedule 尾差以 BAL+FV 判斷，使 FV 非 0 時不誤報

**待辦**
- 無

## 2026-10-20 Task 6 修正輪 1
**需求**
- 非整數 N、P1/P2 不得被默默取整；None 不得拋 TypeError；錯誤欄位 P1／P2 分開

**做法**
- N、P1、P2 須為整數，否則 err；p1<1 回 P1，p2<p1 或 p2>N 回 P2；補測試

**產出**
- engine/amort.py、tests/test_amort.py 更新

**驗證**
- test_amort 7 項、全套 49 項通過；check_portable exit 0

**問題與修正**
- 失敗的嘗試：初版以 round() 取整 N，會把 24.5 誤算為 24 期而看似正常 → 改為直接拒絕

**待辦**
- 無

## 2026-10-20 Task 6 修正輪 2
**需求**
- int() 遇 inf／nan 會拋例外；N、P1、P2 須先驗證為有限數值

**做法**
- 新增 _is_num（排除 bool、字串、inf、nan），於 int() 之前檢查，失敗回對應欄位 err

**產出**
- engine/amort.py、tests/test_amort.py 更新

**驗證**
- test_amort、全套 pytest 通過；check_portable exit 0

**問題與修正**
- 失敗的嘗試：輪 1 直接 int(p) 比對整數，inf 擲 OverflowError、nan 擲 ValueError → 先判有限性再轉型

**待辦**
- 無
