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

## 2026-10-20 Task 7 現金流 CF
**需求**
- engine/cashflow.py：NPV、IRR、NFV、MIRR、PB、DPB，含群組次數展開與錯誤處理

**做法**
- 內部 _expand 回傳 (list, err)；公開 expand 回傳 list 或 err 字典；各函式吃單一 inputs 字典
- IRR 用 solver.find_root，範圍 (-0.9999, 10]；MIRR 依 Excel 公式；PB/DPB 在跨零期間線性內插

**產出**
- engine/cashflow.py、tests/test_cashflow.py（10 項）

**驗證**
- golden 6 筆（NPV/IRR/MIRR/NFV/群組）通過；全套 pytest 通過；check_portable exit 0

**問題與修正**
- 失敗的嘗試：無。注意：先寫實作再補測試，事後以暫時移除模組方式確認測試在無實作時失敗（RED）

**待辦**
- bridge 串接（後續 Task）

## 2026-10-20 Task 7 修正輪 1
**需求**
- PB/DPB 在 CF0>=0 回 0.0 屬誤導；9999 期極端利率會擲 OverflowError/ZeroDivisionError；多重根測試過鬆

**做法**
- CF0>=0 回 err；新增 _disc/_grow 溢位轉 inf，公開函式回「數值過大，無法計算」；強化測試

**產出**
- engine/cashflow.py、tests/test_cashflow.py、task-7-report.md 更新

**驗證**
- test_cashflow 12 項、全套 pytest、check_portable 皆通過

**問題與修正**
- 失敗的嘗試：無

**待辦**
- 無

## 2026-10-20 Task 7 修正輪 2
**需求**
- 更正輪 1 的錯誤宣稱：溢位一律回 inf 使合法輸入（長期 IRR、高利率 NPV）得到錯誤結果

**做法**
- _disc/_grow 依數學語意處理溢位與下溢；IRR 端點為 inf 時改掃描格點找異號區間

**產出**
- engine/cashflow.py、tests/test_cashflow.py、task-7-report.md 更新

**驗證**
- test_cashflow 14 項、全套 pytest、check_portable 通過；irr(9999 期)=1.0000%、npv(I=500)=-99.8

**問題與修正**
- 失敗的嘗試：輪 1 的 inf 對應導致 irr 回「無法收斂」、npv 假溢位；測試只檢查「任何 err」故未抓到 → 改為值斷言。另：僅修 _disc 後 irr 仍失敗，因二分法端點 inf，加 _irr_root 掃描

**待辦**
- 無

## 2026-10-20 Task 9 統計 STAT
**需求**
- engine/stats.py：one_var、two_var（LIN/LN/EXP/PWR）、predict

**做法**
- TDD；用離差（centered）計算以維持數值穩定；EXP 為 y=a·b^x，反求 x=ln(y/a)/ln(b)，檢查 b>0、b≠1、y/a>0
- n=1 的 one_var 回 ok、省略 sx 並加警告；常數 X／Y 回 err

**產出**
- engine/stats.py、tests/test_stats.py、golden/cases.py 與 tests/golden/excel.json 修正、task-9-report.md

**驗證**
- test_stats、test_golden_file、全套 pytest、check_portable 通過

**問題與修正**
- 失敗的嘗試：golden stats_exp_b 原公式為 SLOPE(LN(Y),X)（即 ln b），與規格 y=a·b^x 不符，引擎對照失敗（1.4042 vs 0.3395）
- 控制者裁示選項 B：golden 公式改為 EXP(SLOPE(LN(Y),X))，用 make_golden_excel.py 重產；git diff 確認僅 stats_exp_b 的 expected／source 變動

**待辦**
- 無

## 2026-10-20 Task 10 債券 BOND
**需求**
- engine/bond.py：price（YLD→PRI、AI）、yield_（PRI→YLD、AI）；ACT＝Excel basis 1、360＝Excel basis 0

**做法**
- TDD；付息日自到期日往回 12/freq 個月直接推算（非逐次累推），月底規則（到期日月底→付息日月底），非月底則截斷到該月最後一日
- ACT：A、E 實際天數；360：A＝days_360(PCD, SDT)、E＝360/freq；DSC＝E−A
- N=1 用單期貼現公式，N>1 用 Excel PRICE 公式；YLD 用 find_root，區間 (-0.99, 10]（下界 -0.99+1e-9），猜測值＝票面利率
- 驗證：日期合法、SDT<RDT、freq∈{1,2}、basis∈{ACT,360}、CPN≥0、RV>0、PRI>0；溢位／除零 → err

**產出**
- engine/bond.py、tests/test_bond.py（10 項）、task-10-report.md

**驗證**
- 6 筆 bond golden 全過，最大相對誤差 2.8e-12（bond_yld_360），其餘 ≤ 4.6e-16
- 全套 pytest、tools/check_portable.py 通過

**問題與修正**
- 無失敗嘗試；第一次實作即 GREEN

**待辦**
- TI BA II Plus 實機的 30/360 與 Excel basis 0 規則可能有差異，尚未以 TI Guidebook 案例核對

## 2026-10-20 Task 11 折舊 DEPR
**需求**
- engine/depr.py：schedule、year；SL、SYD、DB、DBX；M01≠1 僅 SL、DB

**做法**
- 逐年迴圈產生 [年, DEP, RBV, RDV]；DBX 取 DB 額與直線法較大者並以剩餘可折舊額封頂；SYD/DBX 的 M01≠1 回指定錯誤；輸入全面驗證（有限數、bool、LIF 整數 ≤10000、M01 1..13）

**產出**
- engine/depr.py、tests/test_depr.py（10 項）、task-11-report.md

**驗證**
- 6 筆 depr golden 全過；全套 pytest、tools/check_portable.py 通過

**問題與修正**
- 失敗的嘗試：測試假設 DB%=1e308 會溢位，實際 min 封頂為殘值、結果合法；改測試為「結果有限且封頂」

**待辦**
- DB 在 M01≠1 的最後一年行為尚未以 TI 手冊範例核對

## 2026-10-20 Task 11 修正輪 1（DB 部分年度）
**需求**
- 控制者裁示：DB 在 M01≠1 與 SYD/DBX 一樣拒絕，避免回傳無法驗證的數字

**做法**
- _validate 加 DB 且 M01≠1 → err("DB 部分年度需 TI 手冊範例驗證，目前僅支援 M01=1", "M01")；刪除 DB 部分年度計算

**產出**
- engine/depr.py、tests/test_depr.py（改為拒絕測試，新增 DBX 提前轉直線法測試）

**驗證**
- test_depr 11 項、全套 pytest（99 項）、check_portable 通過

**問題與修正**
- 失敗的嘗試：先前 DB 部分年度第 LIF+1 年為整年 RBV×rate，表尾不到殘值，屬看似合理的錯誤數字，已移除

**待辦**
- 取得 TI 手冊範例後再開放 SYD/DB/DBX 的 M01≠1

## 2026-10-20 Task 12–13（商業與稅務、日期工作表）
**需求**
- engine/business.py：profit、breakeven、pct_change、tax、TAX_PRESETS；engine/dates.py 加 date_sheet

**做法**
- 皆為「留一格 None 求解」，非未知數須為有限數（bool 拒絕）；除以零一律 err，不回 inf
- tax 以 money.to_cents／tax_* 運算，輸出換回元
- date_sheet：ACT 用序數日加減；360 以實際天數估計中心、窗口 |DBD|*0.05+45 天掃描，取最早解，多解加 warning
- 新增公開 days_in_month，保留 _dim 別名（bond.py 仍在用）
- TAX_PRESETS 只收官方頁面查證到者：營業稅 5%（財政部稅務入口網）、補充保費 2.11%（衛福部 110 年公告）

**產出**
- engine/business.py、engine/dates.py、tests/test_business.py、tests/test_dates.py

**驗證**
- 先寫測試並確認 RED（ModuleNotFoundError／ImportError），實作後全套 pytest 通過、check_portable 通過

**問題與修正**
- 失敗的嘗試：profit 用 _check(…, unknown="") 驗證，錯誤地回報 unknown 欄位，改為逐欄檢查
- 失敗的嘗試：原測試誤以為 1/1 起算 89 天有多解；實際 90 天（3/31 與 4/1）才有，修正測試
- 各類所得扣繳率（薪資／執行業務 10%）僅找到大學轉載簡表，未在財政部／國稅局頁面查證到，故未收錄
- 二代健保補充保費：健保署頁面回 403，僅以衛福部 110 年公告為來源，無法確認 2026 年仍未調整

**待辦**
- 取得財政部扣繳率官方頁面後補 TAX_PRESETS；健保署頁面可讀時換成更直接的來源

## 2026-10-20 Task 14（計算機算式與記憶）
**需求**
- engine/calc.py：遞迴下降算式剖析器（AOS／CHAIN），禁止動態執行函式；engine/memory.py：M0–M9 與累加器

**做法**
- 手寫 tokenizer（數字含 .5、1e3、2.5E-3；運算子含 × ÷ √ ² − ，；識別字 ANS、M0–M9、sqrt/ln/exp/inv/nPr/nCr）
- 文法照規格；% 旗標由 postfix 向上傳遞，僅「直接作為 + − 右運算元」時才以 左×b/100 計算
- CHAIN：二元 + − × ÷ ^ 同級左到右；一元負號／後置／函式／括號照常（故 CHAIN 的 -2^2 = 4）
- 未設定的 Mn 視為 0.0；所有錯誤回 err(訊息含 1 起算位置, "expr")；巢狀深度上限 40
- Memory 方法回 ok／err 字典，失敗時記憶不變；from_dict 驗證並忽略未知鍵與不合格值

**產出**
- engine/calc.py、engine/memory.py、tests/test_calc.py、tests/test_memory.py

**驗證**
- 先寫測試確認 RED（ModuleNotFoundError），實作後全套 pytest 通過、check_portable 通過、engine/ 無 "eval("

**問題與修正**
- 失敗的嘗試：tokenizer 用 str.isdigit()，「²」(U+00B2) 的 isdigit 為 True，3² 被當成數字而出錯；改成明確的 "0123456789" 比對
- 失敗的嘗試：測試中位置斷言寫錯（"1+ $" 的 $ 在第 4 字元），修正測試
- 簡報規格的測試寫 evaluate(...)["value"]，實際 ok() 信封是 ["values"]["value"]，測試採後者

**待辦**
- bridge 接線時決定 UI 如何傳 mem／ans；MicroPython 實機驗證 calc（含 math.pow、遞迴深度）

## 2026-10-20 Task 14 修正輪 1（calc 溢位與 mem 型別）
**需求**
- 超大字面值（1e999）被吞成 inf 使 1/1e999 = 0.0；evaluate 傳入非 dict 的 mem 會 raise

**做法**
- tokenizer 數字非有限 → 「數字超出範圍」；新增 _fin()，二元運算、%、²、^、函式結果皆檢查有限並帶位置
- 最終 ok() 失敗改回 err(..., "expr")；mem 非 None 且非 dict → err("expr")，非 M0–M9 的鍵（如 ACC）忽略，M 鍵的值須為有限數

**產出**
- engine/calc.py、tests/test_calc.py（溢位 9 例、錯誤 mem 型別 4 例、額外鍵）

**驗證**
- 新測試先 RED（含 IndexError／TypeError 與 1/1e999 回 ok）、修正後 test_calc 與全套 pytest 通過、check_portable 通過

**問題與修正**
- 失敗的嘗試：修補腳本重複替換同一字串致斷言失敗、尚未寫入，重跑後成功；測試誤列 1e308% 為溢位（實為合法），移除

**待辦**
- 無

## 2026-10-20 Task 15（顯示格式與輸入解析 engine/fmt.py）
**需求**
- format_number（固定 0～9 位／浮動、us／eu 分隔）與 parse_number（千分位、科學記號、全形數字）

**做法**
- 以 '%.15g' 取十進位字串，展開指數形式成（有效數字, 小數點位置），在字串上做 half away from zero 進位；不用 round()／format 規格
- 浮動模式最多 10 位有效數字，指數 >= 10 或 < -9 用科學記號 E 表示，其餘仍分千分位；-0.0 與進位後為零一律無負號；不合法輸入回「錯誤」不拋例外
- parse_number 不用 re，逐字檢查千分位分組（首組 1～3 位、其後每組 3 位）

**產出**
- engine/fmt.py、tests/test_fmt.py

**驗證**
- 先 RED（ModuleNotFoundError），實作後 test_fmt 與全套 pytest 通過、check_portable 通過、engine/ 無 "eval("

**問題與修正**
- 失敗的嘗試：無（首次實作即通過）；測試中誤放一行全形句點的無意義斷言，已刪除
- MicroPython 上 '%.15g' 行為待 M2 spike 驗證

**待辦**
- bridge 接線時決定 sep／decimals 的來源；M2 spike 實機驗證

## 2026-10-20 Task 16（Controller 入口 engine/bridge.py）
**需求**
- call(request_json)->str 統一路由 24 條 (sheet, action)，驗證輸入、留一格空白、格式化 display、永不擲例外

**做法**
- 每條路由一個 handler：先逐欄驗證（有限數、bool 只給 BGN、日期 [y,m,d]、清單），失敗以 _InputError 轉 err；再呼叫引擎；最外層 try/except Exception 包成「內部錯誤：類別名」
- 留一格空白：tvm／date／breakeven／pct_change 恰一格 null；profit 特例（一格，或 CST/SEL 一格＋MAR/MU 一格→求 CST/SEL，或 CST、SEL 已填且 MAR、MU 同空→算兩者）；pct_change 的 PD 與另一格同空時 PD 預設 1
- display：純量格式化（int 固定 0 位）、rows 逐格；日期 list 與字串不放入 display
- amort（range 與 schedule）N、depr LIF 超過 10000 拒絕
- tools/golden_dump.py 改傳 dict 進 dict 出的轉接函式，路徑改為相對 repo 根

**產出**
- engine/bridge.py、tests/test_bridge.py、tools/golden_dump.py 修正

**驗證**
- 先 RED（ModuleNotFoundError）；實作後 test_bridge 7 項、全套 pytest、check_portable 通過；golden_dump 51 案無 null；engine/ 無 "eval("

**問題與修正**
- 失敗的嘗試：第一次用 shell heredoc 寫檔因引號解析失敗、未寫入任何檔案，改用寫檔工具
- golden 全數一次通過，未動 golden 資料

**待辦**
- UI 依 bridge 模組 docstring 的鍵對照表接線；MicroPython 上驗證 json.dumps(allow_nan=False) 行為

## 2026-10-20 Task 16 修正輪 1（bridge 可攜性與比率衝突）
**需求**
- MicroPython 相容：json.dumps 無 allow_nan、無 RecursionError；profit 另給比率與算出值衝突不可默默覆蓋

**做法**
- 回應先用 result._all_finite 遞迴檢查，非有限則改回 err，再用純 json.dumps；解析例外改 (ValueError, TypeError, RuntimeError)；bridge.py 已無其他 CPython 專用名稱
- _r_profit：CST、SEL 皆已知且另一比率有給，算出值差超過 1e-9 相對誤差即回「MAR 與 MU 不一致」

**產出**
- engine/bridge.py、tests/test_bridge.py（新增 inf 回應、比率衝突兩測試）

**驗證**
- test_bridge 9 passed、全套 pytest 通過、check_portable 0、golden_dump 無 null

**問題與修正**
- 失敗的嘗試：無

**待辦**
- 無

## Task 17：突變測試 tools/mutate.py（M1 收尾，tag step3）

**需求**
- 自寫突變測試工具：對 engine/ 逐一植入 ≥15 個刻意錯誤，跑 pytest -x -q，確認每個都被測試擋下

**做法**
- tools/mutate.py：MUTATIONS 為 (檔案, old, new, 說明)；old 須恰好出現一次，否則工具錯誤 exit 1；執行前檢查 engine/ git 乾淨、未突變時 pytest 須通過；以 finally 還原原始位元組，結束後比對 engine/ 位元組一致；逾時 300 秒視為 killed 並標示
- 共 18 個突變；DB 部分年度已被後續裁定移除，故 SL 首年比例 (13-M01)→(12-M01) 改打 depr.SL；另加 DBX max→min、回收期邊界 <=0 改 <0
- 第一次執行 15/18：存活 3 個，補測試（test_cashflow：負 IRR、回收期剛好為 0；test_stats：雙變數 Sx/Sy/sigma）；補完全部被殺

**產出**
- tools/mutate.py、tests/test_cashflow.py（+2）、tests/test_stats.py（+1）

**驗證**
- python tools/mutate.py：18/18 mutants killed；全套 pytest 通過；check_portable 0；補的測試在突變上 RED、在原碼 GREEN

**問題與修正**
- 失敗的嘗試：IRR 範圍下限單改 0 仍存活，原因是 _irr_root 的格點後備掃描（-0.99 起）會找回負根，結果完全相同（等價突變，非測試漏洞）；改為同時拿掉後備掃描的複合突變（old/new 支援 tuple），再由負 IRR 測試殺死
- 首次輸出在 cp950 終端亂碼，改以 PYTHONIOENCODING=utf-8 導向檔案檢視

**待辦**
- 無

## Task 18：spike——MicroPython 雙精度驗證（決策點）

**需求**
- 驗證 engine/ 能否在 MicroPython 1.29 WebAssembly（IEEE-754 double）上執行；不行就退回 Pyodide
- 檢查清單 a～h：雙精度、%g 格式化與 CPython 一致、math/json、RuntimeError／遞迴、大整數比較、isdigit、golden 全集、計時

**做法**
- 使用者同意後 `npm install --save-exact @micropython/micropython-webassembly-pyscript@1.29.0-6`
- tools/spike_float.mjs：loadMicroPython() → 用 FS.mkdir/writeFile 把 engine/*.py、golden/*.py、excel.json 寫入 VFS → sys.path 加 /bacalc → 跑檢查 → 以子行程跑 CPython（含 tools/golden_dump.py）取得參考值比對 → 印 JSON
- 額外加的探測：4000 個可重現亂數的 %.15g 與 fmt.format_number 對照、tie 值、business/tax 大金額、calc 錯誤路徑、bridge 輸入驗證錯誤路徑、51 個 golden 的 display 字串逐字比對
- brief 的「1e300*10 == inf」在雙精度下本來就不成立（1e301 有限，CPython 也是 False），改為與 CPython 比對並另加 1e308*10 == inf

**產出**
- tools/spike_float.mjs、package.json、package-lock.json、logs/spike-micropython-20261020.html

**驗證**
- 雙精度全部成立（次正規數、0.1+0.2、2**53+1、溢位 inf、repr 往返）
- golden 51 案例失敗清單為空；與 CPython 最大相對差 1.25e-16；display 字串 51/51 相同
- 計時：載入 MicroPython 約 17 ms、import engine.bridge 約 33 ms、合計約 65 ms；golden 3 輪約 90 ms；1 MB 預設 heap 結果相同
- pytest 全部通過、check_portable 0（engine 未修改）
- 決策：採用 MicroPython

**問題與修正**
- 發現引擎可攜性 bug（依裁定本任務不修，交 controller 另派）：
  - engine/calc.py:28、engine/bridge.py:61 `Exception.__init__(self, msg)` 在 MicroPython 拋 AttributeError（Exception 無 __init__），所有 calc 錯誤與 bridge 輸入驗證錯誤都變成「內部錯誤：AttributeError」、field 為 null（仍是 ok:false，不會產生錯誤數字）
  - engine/money.py:18-21 to_cents：MicroPython 的 '%.6f' 在 |x| ≥ 1e26 輸出指數形式 → split('.') ValueError；1e23～1e25 小數位不足、尾數不精確（差約 1 ulp）
- MicroPython %g/%f 的差異：超過約 16 位有效數字補 0（'%.17g' % 0.1 → '0.1'）；第 15 位剛好是二進位精確中點時採 half-up（CPython half-even），4000 個亂數中 10 個 %.15g、5 個 format_number 末位差 1（皆 ≥1e11 的值）
- 失敗的嘗試：npm install 第一次在 BACalc 沒有 package.json 時，npm 往上找到「Tien Research」根目錄的 package.json 並裝在那裡（該檔多一行相依、lock 與 node_modules/@micropython 被更動）；未刪除，待使用者決定是否還原；之後先建 BACalc/package.json 再重裝
- 腳本開發時以 Python heredoc 寫入 JS 造成跳脫字元錯誤，已手動修正

**待辦**
- controller 派工修正 calc.py:28、bridge.py:61（改 super().__init__ 或不呼叫基底 __init__）與 money.to_cents 大數值
- 決定 %.15g tie-breaking 差異是否接受（或引擎端改用 repr 自行進位）
- 使用者決定是否還原「Tien Research」根目錄 package.json／package-lock.json／node_modules/@micropython
- 繼續 Task 19

## Task 18 修正輪 1：engine MicroPython 可攜性修正

**需求**
- Controller 裁定：採用 MicroPython；%.15g 中點進位與 %.17g 補 0 差異接受
- 修正 spike 發現的可攜性 bug：Exception.__init__、money.to_cents 大數值；spike 的 g4、g5、g6 必須通過，接受項目標 accepted (ruling)

**做法**
- calc.py、bridge.py：Exception.__init__(self, …) → super().__init__(…)；check_portable 新增規則禁止「內建型別.__init__(」
- calc.py：識別字改用 ASCII 字母表判斷（MicroPython 的 isalpha 只認 ASCII，修好 __init__ 後 g5 才露出此差異）
- money.to_cents：改以 '%.15g' 取十進位值、整數運算進位到分（half away from zero）；MAX_AMOUNT = 1e13 元，超過拋 ValueError；business.tax 先驗證回 err（field amount）
- spike：accepted (ruling) 由程式以 CPython Decimal 驗證「差異全是精確中點」才給；all_pass 只計未接受項目；新增 g7 to_cents 跨環境比對（約 18000 值）

**產出**
- engine/calc.py、engine/bridge.py、engine/money.py、engine/business.py、tools/check_portable.py、tools/spike_float.mjs
- tests：test_portable（+2）、test_money（+2）、test_business（+1）、test_calc（+1）
- logs/spike-micropython-20261020.html 新增「修正輪 1」段落與新決策行

**驗證**
- 6 個新測試先 RED 後 GREEN；全套 pytest 通過；check_portable 0；mutate.py 18/18 killed
- spike 重跑（HEAD 0f99f5a，git 乾淨）：all_pass True；通過 29、裁定接受 5、不通過 0；g4/g5/g6 通過
- 決策：採用 MicroPython（雙精度通過；%.15g 中點進位與 %.17g 差異經裁定接受；engine 可攜性問題已修正並重跑通過）

**問題與修正**
- 失敗的嘗試：to_cents 改 '%.15g' 後先用 controller 建議的上限 1e15，重跑 g7 發現 1e13 以上 '%.15g' 只剩 1 位小數，分位被截掉（11579813144864.25 兩端都錯），上限改為 1e13
- 舊 '%.6f' 作法在 CPython 本身對 ~1e9 元以上也會露出二進位誤差（116455781560.185 → 少 1 分），新作法一併修正
- 剩餘差異：g7 18168 值中 1 個 %.15g 精確中點（9992958372198.125：MicroPython …13 分、CPython …12 分），屬裁定接受範圍
- 第一次跑 mutate.py 被拒（engine/ 有未提交變更），先 commit 修正再跑

**待辦**
- 使用者決定是否還原「Tien Research」根目錄 package.json／package-lock.json／node_modules/@micropython
- 繼續 Task 19

## 2026-10-20 Task 19：MicroPython 雙執行環境 golden 測試

**需求**
- tools/run_mpy_golden.mjs：在 Node 的 MicroPython 內跑 golden 與錯誤路徑案例，與 CPython 比對；package.json 加 test:mpy

**做法**
- 共用載入邏輯抽到 tools/mpy_util.mjs（spike_float.mjs 保持不動）
- golden：runner.run 全過，且 dump 與 tools/golden_dump.py 的 CPython 結果相對差 <= 1e-9（max(1,|b|) 為底），只比數值不比顯示字串（裁定）
- 錯誤路徑：新增 tests/golden/error_cases.json（24 案，含 expected），由 tools/error_dump.py 以 CPython bridge 產生；MicroPython 回應須與 expected 的 ok／error／field 完全相同，另即時重算 CPython 防期望值過期
- --self-test：在暫存目錄弄壞 golden 與 error expected 的副本，確認 exit 1，repo 不被修改

**產出**
- tools/run_mpy_golden.mjs、tools/mpy_util.mjs、tools/error_dump.py、tests/golden/error_cases.json、package.json scripts

**驗證**
- npm run test:mpy：51/51 passed, max diff vs CPython 1.25e-16；24/24 error cases identical
- --self-test：未損壞 exit 0、壞 golden exit 1、壞 error expected exit 1
- pytest 全過、check_portable 0

**問題與修正**
- 失敗的嘗試：第一次用 bash heredoc 一次寫多個檔案，shell 因引號解析錯誤整段未執行，改用 Write 工具
- error_dump 初版 amort N 非整數案例缺 PY 欄位，錯誤落在 PY 而非 N，補齊欄位；移除重複的 tvm 案例（24 案）
- error_dump 輸出改 ensure_ascii 以免 Windows cp950 主控台弄壞中文

**待辦**
- 之後納入一鍵驗證（verify）流程

## 2026-10-20 Task 19 審查修正 round 1

**需求**
- 修正 run_mpy_golden.mjs：NaN／非數值比較會空過；空集合或截斷集合仍 exit 0；self-test 強度不足

**做法**
- 數值比較先檢查 typeof number 且有限，失敗才記錄；判斷改為 !(d <= TOL)；CPython 或 MicroPython 為 null 也視為失敗
- 案例數為 0（golden 或 error）即失敗；預設模式檢查 CPython dump 筆數等於案例數且每個 id 兩邊都有
- self-test 擴充為 6 情境：未損壞、壞 golden（輸出須含 FAIL golden）、壞 error expected（須含 FAIL error case）、空 golden、golden expected 為字串、空 error 集合

**產出**
- tools/run_mpy_golden.mjs 修正

**驗證**
- test:mpy 51/51、24/24；--self-test 6 項全 OK；pytest 全過；check_portable 0

**問題與修正**
- 原本 NaN 使 d > TOL 為 false 而空過；已改為 !(d <= TOL)

**待辦**
- 無

## 2026-10-20 Task 20 PWA 殼＋Web Worker（MicroPython 橋接）

**需求**
- 建立 PWA 殼（index.html、css、manifest、sw.js precache＋cache-first、icons）、module Web Worker 載入 MicroPython 1.29 並服務 engine.bridge.call、Promise client（ready 前佇列）、selftest.html、build_web.py／check_shell.py、.claude/launch.json

**做法**
- TDD：先寫 tests/test_shell.py（RED：ImportError，tools.build_web／check_shell 不存在），再實作至 GREEN
- build_web.py：engine/*.py、golden/{__init__,runner}.py → web/py/；tests/golden/{excel,error_cases}.json → web/py/data/；產生 web/py/manifest.json；sw.js APP_SHELL 的 @py-begin／@py-end 區段自動產生；node_modules 的執行環境複製到 web/vendor/（無 node_modules 時沿用已 commit 版本）；--check 只比對不寫檔；--bump 同步 CACHE_VERSION／APP_VERSION
- check_shell.py：web/ 每個檔案都在 APP_SHELL、每項都存在且為相對網址、版本同步；web/py 未建置時回報「請先執行 build_web.py」並略過 py/ 項目（須在 build 之後執行）
- py-worker.js 用 import.meta.url 組相對網址、明確傳 wasm url；單一請求失敗只回 {id, error}
- tools/check_worker.mjs：Node 中以假 Worker 載入真正的 py-worker.js＋py-client.js 驗證佇列、golden、錯誤路徑與載入失敗

**產出**
- web/（index.html、css/app.css、manifest.webmanifest、sw.js、selftest.html、js/app.js、js/py-client.js、js/py-worker.js、icons/、vendor/）
- tools/build_web.py、tools/check_shell.py、tools/check_worker.mjs、tools/make_icons.py、tests/test_shell.py、.claude/launch.json、.gitattributes、package.json（test:worker）
- logs/verify-20261020-1525.html

**驗證**
- pytest 252 passed（test_shell 19 項）；check_portable 0；build_web --check 0；check_shell 通過
- node --check 四個 js 皆過；check_worker.mjs PASS（佇列：送出時 loading，ready 後回應正確；golden 51、錯誤路徑 24 全過）；--broken 模式狀態轉 error、請求 reject
- test:mpy 51/51、24/24；http.server 8765：index、sw.js、selftest、vendor js／wasm、py/manifest 等皆 200 且位元組與本機相同
- 未在真實瀏覽器驗證（selftest PASS、計時、離線重新整理交給 controller）

**問題與修正**
- 失敗的嘗試：Windows 的 python http.server 把 .mjs 回成 text/plain（mimetypes 讀登錄檔），瀏覽器會拒絕 module script → 改以 web/vendor/micropython.js（與套件 micropython.mjs 位元組相同）提供，VERSION.txt 註明
- core.autocrlf=true 會改動鎖定檔案位元組 → 加 .gitattributes `web/vendor/* -text`
- 失敗的嘗試：用 python heredoc 批次字串取代，含 \n 的多行樣式比對不到而中途停止，改用 Edit 工具逐一修改
- flake8 E501 多處（中文註解過長）已折行

**待辦**
- controller 以瀏覽器驗證 selftest.html、shell／py-ready 計時（一般、Slow 4G、離線），寫 logs/verify-*.html 後打 tag step4
- 部署 workflow 須先執行 python tools/build_web.py（web/py 不進 git）

## 2026-10-20 Task 20 審查修正 round 1

**需求**
- SW precache 不可經 HTTP 快取（GitHub Pages max-age=600）；SW 必須隨殼內容自動更新（SHELL_HASH）；導覽請求 ignoreSearch 並可退回 index.html；py-client 單筆送出失敗不可中斷佇列、error 後忽略 ready 並 terminate Worker；--bump 先驗證兩檔再寫

**做法**
- sw.js：逐檔 fetch(new Request(u, {cache: "reload"})) 全部 ok 後 cache.put，失敗則刪快取並讓 install 失敗；快取名 `${CACHE_VERSION}-${SHELL_HASH}`；activate 只刪 bacalc- 開頭的其他快取（github.io 同 origin 可能有其他 App）；導覽請求 cache.match(ignoreSearch) → 網路 → 離線退回 ./index.html
- check_shell.shell_hash：APP_SHELL 檔案（排除 "./" 與 sw.js）依路徑排序做 SHA-256，取前 16 字元；換行 CRLF→LF 正規化；build_web 寫入 SHELL_HASH，check_shell 與 --check 偵測過期
- build_web.bump：兩檔正規式都成功才寫，寫完自動 build 以更新 SHELL_HASH
- py-client：dispatch try/catch、status 為 error 時忽略所有訊息、fail() terminate
- check_worker.mjs：假 Worker 改做 structuredClone、加 terminate；新增佇列中與 ready 後的不可複製請求案例

**產出**
- web/sw.js、web/js/py-client.js、tools/build_web.py、tools/check_shell.py、tools/check_worker.mjs、tests/test_shell.py（+6 測試）
- logs/verify-20261020-1534.html

**驗證**
- pytest 258 passed；check_portable 0；build_web --check 0；check_shell 通過；check_worker PASS；test:mpy 51/51、24/24；node --check 全過；flake8 0
- RED：舊版 py-client 在新 check_worker 下拋 DataCloneError 中斷佇列（exit 1），新版 PASS
- 全新 clone（CRLF 簽出）：build 後 sw.js 不變、git 乾淨、check_shell 通過
- 瀏覽器端（precache reload、SW 更新、離線）待 controller 重新驗證

**問題與修正**
- 失敗的嘗試：雜湊初版未正規化換行，CRLF 簽出的 clone 上 build --check 報 sw.js 過期 → 加 CRLF→LF 正規化與測試
- 失敗的嘗試：bash heredoc 內 python 的 `\0` 被轉成真正的 NUL 寫進檔案，改用 chr 替換修回
- test_bump_updates_both_versions 在加入 SHELL_HASH 後失敗（app.js 改了雜湊過期）→ bump 後自動 build

**待辦**
- controller 瀏覽器重新驗證後打 tag step4

## 2026-10-20 Task 21 工作表表單框架

**需求**
- View 端框架：所有工作表的欄位定義（sheets.js）、通用表單（views/form.js）、導覽（views/nav.js）、純函式輸入解析（input.js）、設定（settings.js），讓 Task 22～24 只需加各表版面
- 欄位 id 必須與 engine/bridge.py 鍵對照表完全一致；Enter 計算、Esc 清除、Tab 換欄；inputmode=decimal；ⓘ 說明；收到↓／付出↑；深色模式與無障礙（label for、aria-describedby）
- 先掛最小示範：index 顯示導覽＋TVM 表單，計算鈕呼叫 callEngine

**做法**
- input.js 逐行移植 engine/fmt.parse_number（US／EU 千分位、全形數字、1e3），不依賴 Python；collect(values, kinds, sep) 空白→null、百分比 5／5% 皆為 5、日期 [y,m,d]、清單、「金額 x 次數」、positive／integer／min 即時驗證；toSigned／fromSigned（收到正、付出負，0 不產生 -0）
- sheets.js：14 張表，欄位 {id, key?, out?, alias?, label, abbr, unit, help, example, kind, options?, output?, initial?}；動作 {id, label, primary, send?, solve?}；STAT 預測的 X'／Y' 與資料清單同名，用 id XP／YP + key X／Y 區分；STAT 回傳 a、b 以 out 對到 A、B 欄
- form.js：產生 label＋abbr、ⓘ 說明（aria-expanded）、單位、方向鈕與「TI 正負號」提示、錯誤訊息（aria-invalid＋aria-describedby）；showResult 只填空白或上次求出的欄位（PROFIT 會回傳全部四格，使用者輸入不覆蓋），求出值保留完整精度（dataset.exact）；中文輸入法組字中的 Enter 不觸發
- 自我審查後新增 input.resolveBlanks：求出 PMT 後改 N 直接按 Enter，沒有空白時把上次求出且未改動的欄位再當未知數
- nav.js：hash 路由（#tvm、#cf…）、< 900px 底部 5 分頁＋更多選單、≥ 900px 左側全部工作表、localStorage 記住上次（try/catch）
- app.js：每張表先用通用表單，動作直接送 callEngine（設定頁改寫 settings 並套用外觀）；app.css 改為色彩變數＋prefers-color-scheme／data-theme 深色模式＋響應式
- sw.js APP_SHELL 加 5 個新檔，build_web 更新 SHELL_HASH；selftest.html 表頭改用色彩變數（深色模式可讀）

**產出**
- web/js/input.js、sheets.js、settings.js、views/form.js、views/nav.js；改 web/js/app.js、index.html、css/app.css、sw.js、selftest.html、package.json（test:js）
- tests/js/input.test.mjs、sheets.test.mjs、settings.test.mjs、helpers/*.mjs；tests/_node.py、test_web_js.py、test_web_input.py、test_web_sheets.py
- logs/verify-20261020-1554.html

**驗證**
- RED：input.test.mjs、sheets.test.mjs 先跑皆因模組不存在失敗；resolveBlanks 測試先因缺 export 失敗
- GREEN：node --test 22 pass；pytest 264 passed（新增 6）；build_web --check、check_shell、check_portable、check_worker、flake8 皆通過
- JS／Python 數字解析 126 案逐一相同；突變測試（關掉全形數字轉換）時該測試失敗
- 欄位範例端到端：每張表每個動作用 example 呼叫 bridge 皆 ok，且回傳值與輸出欄位 example 相符
- 瀏覽器畫面、鍵盤、TVM 示範：待 controller 以瀏覽器驗證

**問題與修正**
- 失敗的嘗試：`node --test tests/js`（目錄）在 Node 22 找不到模組 → 改傳 glob 字串 `tests/js/*.test.mjs`（Node 自行展開，Windows 亦可）
- 自己的測試寫錯：EU 模式 "1.5" 是不合法千分位，改為 "1,5"
- 端到端測試抓到猜錯的說明範例：IRR 13.7→13.78、MIRR 11.9→11.83、F 範例 "1 1 2 1 1" 會讓 n=6 → 改 "1 1 1 1 1"
- pytest.ini 的 addopts 已含 -q，再加 -q 會吃掉最後的 passed 摘要，驗證時改用 -o addopts

**待辦**
- controller 瀏覽器驗證（手機寬／桌面寬、深色模式、Enter／Esc／Tab、TVM 示範、更多選單）
- Task 22～24：各工作表專屬版面（CF 現金流表格、攤還／折舊表、STAT 資料表、CALC 按鍵與紙帶）；目前用通用表單暫代
- Task 25：設定改存 IndexedDB；日期格式（US／EUR）與稅率預設尚未放進設定頁

## 2026-10-20 Task 21 審查修正 round 1

**需求**
- STAT 預測不能重複使用：X'=6 → Y'=5.8 後改 X' 為 7，求出的 Y 和 X 一起送出，bridge 拒絕（須恰好給定 X 或 Y 其一）
- AMORT 說明範例 98,772.00／-1,228.00／-5,966.60 與引擎值不同（畫面上出現錯誤數字違反核心原則）；測試必須要求範例等於引擎的 2 位小數顯示
- 讓「重新求解」的行為看得到：有求出的欄位時顯示提示

**做法**
- sheets.js：predict 加 solve ["X","Y"]（引擎鍵），交給 input.resolveBlanks 處理；AMORT 範例與說明改為 98,771.99／-1,228.01／-5,966.59；ANS 範例改 14，與說明一致
- form.js：有求出的輸入欄位（綠色、非輸出欄）時，表單下方顯示「綠色欄位是上次求出的結果；修改其他欄位後按 計算 會重新求出它」，那一格被改掉後提示自動移除；只有最近一次求出的格子會重算，較早求出的格子降為一般值，但仍保留完整精度；計算失敗時保留綠色標記與提示
- 測試：test_web_sheets 改為範例 == 引擎 display（不再允許誤差）；新增「說明文字必須含範例數字」；新增 STAT 預測兩個方向的「預測 → 修改 → 再預測」迴歸測試（helpers/predict_resolve.mjs 模擬 readInputs 流程，再實際呼叫 bridge）

**產出**
- commit 6f34bbe；web/js/sheets.js、web/js/views/form.js、web/css/app.css（.resolve-hint）、web/sw.js（SHELL_HASH）、tests/test_web_sheets.py、tests/js/sheets.test.mjs、tests/js/helpers/predict_resolve.mjs
- logs/verify-20261020-1607.html

**驗證**
- RED：收緊後的 test_web_sheets 有 4 項失敗（AMORT 三個範例、ANS 說明與範例不符、STAT 預測兩個方向改值後仍送出求出的值）
- GREEN：test_web_sheets 7 passed；pytest 全部 267 passed；node --test 22 pass；build_web --check、check_shell、flake8 都通過
- 瀏覽器上的提示顯示與 STAT 重複預測：待 controller 確認

**問題與修正**
- 新寫的 Python 測試檔透過 heredoc 產生，`"\n"` 在 python 字串中被展開成真正的換行，造成 SyntaxError → 用 Edit 工具修正
- 發現：求出一格後再求另一格時，較早求出的格子還留著「求出」標記，下次可能出現兩格空白 → 只保留最近一次求出的格子
- 驗證腳本執行超過 2 分鐘的工具逾時，改在背景完成；中途因 API 連線錯誤中斷，log 已確認對應 HEAD 6f34bbe 且全部通過

**待辦**
- controller 在瀏覽器確認重新求解提示與 STAT 重複預測
- Task 22～24 各表專屬版面

## 2026-10-20 Task 21 審查修正 round 2

**需求**
- controller 瀏覽器檢查（HEAD 5638a51）發現：STAT 同時填 X' 與 Y' 按「預測」時，bridge 回 field "X"，畫面卻把錯誤標在頁面上方的資料清單 X（f-stats-X），讓使用者以為資料錯了，應標在 X'（f-stats-XP）
- 規則套用到所有工作表：錯誤欄位先在剛執行的動作欄位中找，找不到再全域對應

**做法**
- sheets.js 新增純函式 fieldForKey(sheetId, key, actionId)：先在 sendFields(該動作) 中依 引擎鍵 key ?? id → out → id → alias → 不分大小寫 對應；找不到再用原本的全域順序（out ?? id → id／key → alias → 不分大小寫）；不存在的 actionId 直接走全域
- form.js 移除私有的 findField；showResult(response, sheetId, actionId) 改用 fieldForKey，省略 actionId 時用最近一次 readInputs 記錄的動作（lastAction）；app.js 呼叫時傳入 actionId
- 回傳值的對應也用同一規則（predict 的 y → YP；two_var 的 a、b 不在送出欄位，走全域對到 A、B）

**產出**
- commit fd12839；web/js/sheets.js、web/js/views/form.js、web/js/app.js、web/sw.js（SHELL_HASH）、tests/js/sheets.test.mjs、tests/test_web_sheets.py
- logs/verify-20261020-2212.html

**驗證**
- RED：sheets.test.mjs 的 fieldForKey 測試，因為缺少 export 而失敗（16 pass、1 fail）
- GREEN：node --test 23 pass；pytest 268 passed（新增 bridge 實際回 field "X" → 預測對到 XP、迴歸對到 X）；build_web --check、check_shell、flake8 都通過
- 瀏覽器上的錯誤標示位置：待 controller 確認

**問題與修正**
- 驗證腳本超過 2 分鐘的工具逾時，改在背景執行後再讀結果

**待辦**
- controller 在瀏覽器確認 STAT「X'、Y' 都填」的錯誤標在 X' 欄
- Task 22～24 各表專屬版面

## 2026-10-20 Task 22：TVM／AMORT／ICONV／商業／DATE 專屬畫面

**需求**
- 在 Task 21 通用表單上做五個專屬畫面；TVM「帶入攤還」、AMORT 完整攤還表＋CSV、ICONV 即時雙向、商業四子分頁＋稅率預設值、DATE 星期；任何情況不得留下看起來像目前結果的舊數字

**做法**
- 新增 views/run.js（runEngineAction／markStale／watchStale：失敗或編輯時清輸出欄、已求出欄位標過期 stale）；app.js 的 runAction 改委派給它
- form.js 新增 getFieldState／setFieldState（跨表搬值並保留完整精度）；nav.js 新增 select（子分頁同步網址）
- csv.js（toCSV RFC 4180、CRLF、BOM、download 分開）、util.js（debounce）；tvm／amort／iconv／business／date 各一檔
- 稅率預設值：bridge 沒有路由，鏡射到 sheets.js TAX_PRESETS，pytest 比對與 engine/business.py 相同
- 先寫 csv／util 測試看到失敗（模組不存在）再實作

**產出**
- web/js/csv.js、util.js、views/{run,tvm,amort,iconv,business,date}.js；修改 app.js、sheets.js、form.js、nav.js、sw.js、app.css；tests/js/csv.test.mjs、util.test.mjs、tests/test_web_sheets.py

**驗證**
- node --test 與 pytest 全綠、build_web／check_shell 通過
- 本機靜態伺服器＋瀏覽器冒煙測試：TVM PMT 599.55 → 帶入攤還 → 360 列、末列餘額 0.00、區間 BAL 98,771.99／PRN −1,228.01／INT −5,966.59；改 I/Y 後攤還表與 BAL 立即清除；ICONV 6→6.17、8→7.72；稅額預設值 2.11% → 21.10／1,021.10 並顯示出處；DATE 364 天、星期四、改日期後星期清空且天數標過期；TVM 留多格空白顯示「請只留一格空白」

**問題與修正**
- 第一次載入殘留舊 Service Worker 快取，看不到新按鈕，清除快取後正常（開發環境現象）
- amort.js 起初把 append 的回傳值接著 append（回傳 undefined），寫完立刻修正

**待辦**
- controller 依 brief Step 2～3 做 golden e2e 與截圖；Task 23～24 的 CF／BOND／DEPR／STAT／CALC 專屬畫面

## 2026-10-20 Task 22 修正輪 1：CSV 純數字、清除鈕、請求期間編輯

**需求**
- CSV 儲存格要是 Excel 認得的純數字；清除鈕／Esc 要連攤還表與匯出鈕一起清掉；請求進行中改輸入，舊回應不可顯示

**做法**
- csv.js 新增 exportSettings（sep 固定 us）與 plainNumberRows（去千分位）；AMORT 顯示表用使用者設定，CSV 用同樣輸入再向引擎要一次 sep=us 的 display（捨入仍由引擎做）；刪除鎖定千分位字串的舊測試
- form.js resetValues 送出 bubbling 的 form-reset；run.js watchStale 視同編輯
- 新增 generation.js（純函式世代守衛）；markStale bump，runEngineAction 呼叫前取 token、回來比對不符就丟棄
- ICONV 防抖函式在表單已脫離 DOM 時不送請求；schedule 成功卻沒有列時顯示錯誤訊息

**產出**
- web/js/generation.js、csv.js、views/{run,amort,iconv,form}.js、sw.js；tests/js/generation.test.mjs、csv.test.mjs、tests/test_web_sheets.py（sep us／eu × 小數 0／2／4 的純數字測試）

**驗證**
- node 與 pytest 全綠、build_web／check_shell 通過
- 瀏覽器（sep=eu）：畫面表格 −599,55；CSV 開頭 BOM EF BB BF、360 列全為 /^-?\d+(\.\d+)?$/；按清除後表格消失、匯出鈕停用；N=10000 的 schedule 進行中改 I/Y，回來後沒有表格也沒有結果

**問題與修正**
- 第一次驗證在 eu 設定下輸入 599.55 被判格式錯誤（eu 的點是千分位），改輸入 599,55；進行中請求未回來時按鈕會暫時停用，屬預期

**待辦**
- controller 再審

## 2026-10-20 Task 23：CF／STAT／BOND／DEPR 專屬畫面與貼上解析

**需求**
- CF、STAT 改成可編輯表格（新增／刪除列、從 Excel 貼上）；BOND 留一格空白求 PRI 或 YLD；DEPR 折舊表＋CSV 與 M01 規則提示；任何編輯、錯誤、清除後都不能留下看起來像目前結果的舊數字

**做法**
- 新增純函式 paste.js（parsePastedTable，重用 input.js parseNumber）與 tables.js（applyPaste、readCfTable、readStatTable、MAX_ROWS=500），錯誤一律回 {error, row, col}
- 新增 views/grid.js（CF 與 STAT 共用的表格元件）、cashflow／stats／bond／depr 四個畫面；run.js 的 runEngineAction 新增 extra／onExtraError／mapError 三個掛鉤，讓表格內容併入送出的輸入、讀取錯誤中止計算、引擎錯誤可認領到表格；form.js 新增 showFormMessage
- 設計決定：中間的空白列一律報錯（CF 會讓期別錯位，沒有現金流要輸入 0）；STAT 迴歸時次數欄有值報錯而不是默默忽略；單變數次數欄全有或全無
- BOND 把兩個固定動作鈕換成一顆「計算」，由 YLD／PRI 哪格空白決定求價格或求殖利率，並沿用「上次求出的格子再當未知數」規則
- 警告（IRR 可能有多個解）樣式改為醒目警告框

**產出**
- web/js/paste.js、tables.js、views/{grid,cashflow,stats,bond,depr}.js；修改 app.js、sw.js（APP_SHELL）、views/run.js、views/form.js、css/app.css；tests/js/paste.test.mjs、tables.test.mjs

**驗證**
- node --test 62 pass；pytest 全綠；build_web／check_shell／check_portable 通過
- 瀏覽器：CF（CF0=−10000，3000／4200／6800／−1500，I=10）NPV 282.77、IRR 11.52 並顯示多解警告；全正現金流 IRR 顯示「IRR 無解：現金流沒有正負號變化」；STAT LIN a=−0.02、b=2.02、預測 X'=7 → 14.12；BOND 價格 93.40、AI 3.13，改 CPN 後重算 86.81，兩格都填報錯，清空 YLD 後求出 6.72；DEPR 定率遞減 DB 第 2 年 2,400.00、折舊表 5 列、CSV 鈕啟用

**問題與修正**
- parsePastedTable 第一版把「單欄但行尾有 tab」當成多欄而失敗，改為先去掉行尾 tab、寬度 ≤ 1 時改走單欄路徑
- 用 Bash heredoc 寫含單引號（X'）的檔案時工具解析失敗，改用 Write 工具
- 先寫實作與測試一起，沒有單獨留下測試失敗（RED）的輸出

**待辦**
- controller 的 e2e（元素 id：cf-table、cf-add-row、stat-table、stat-add-row、depr-table、depr-csv、bond-calc、f-<sheet>-<field>）
- DEPR CSV 實際下載內容未在瀏覽器逐格驗證（與 AMORT 同一套 exportSettings／plainNumberRows）

## 2026-10-20 Task 23 修正輪 1：貼上單欄不可誤判兩欄、CF 次數空白視為 1

**需求**
- 審查發現：單欄 Excel 貼上含空白千分位（「1 234」）會被切成兩欄，CF 變成金額 1、次數 234，靜默錯誤資料；controller 另裁定 CF 金額有填、次數空白時次數預設 1

**做法**
- paste.js：沒有 tab 的多行貼上一律單欄（只以換行分隔，每行一格交給 parseNumber，「1 234」報錯並指出列欄）；只有單行才以半形空白或 tab 分隔；NBSP（U+00A0、U+202F）不當分隔符號
- tables.js readCfTable：次數空白 → 1；金額空白但次數有填（非 1）仍報錯；CF 表格提示文字更新

**產出**
- 修改 web/js/paste.js、tables.js、views/grid.js（hint 選項）、views/cashflow.js；tests/js/paste.test.mjs、tables.test.mjs

**驗證**
- node --test 64 pass；pytest 全綠；build_web、check_shell 通過
- 瀏覽器：CF 貼上 NBSP 千分位兩行 → 「第 1 列第 1 欄「1 234」不是數字」，表格不變；貼上兩欄 3000／2、4200／1 正常

**問題與修正**
- 改測試檔時用 Python 三引號字串把 \n 展開成真正換行，造成語法錯誤，改用 raw 字串重寫該段
- 原「沒有 tab 的多行多值視為多欄」測試被改為驗證報錯（行為刻意變更）

**待辦**
- 無

## 2026-10-20 Task 24：計算機、紙帶、記憶、設定（M3 收尾，tag step5）

**需求**
- 計算機畫面（算式輸入、手機按鍵面板、紙帶、M0–M9 記憶面板、Σ 累加）與完整設定畫面（小數位數、千分位、日期格式、AOS／Chain、外觀、稅率預設、「關於」含啟動計時）

**做法**
- 純模型（可 node 測試）：memstore.js 鏡射 engine/memory.py（÷0、溢位不改記憶；toJSON／fromJSON 同 to_dict 形狀）、tape.js（上限 500、歷史瀏覽 walker）、keypad.js（按鍵表＋游標插入／退格）、datefmt.js
- views/calc.js：所有算式與顯示都走 callEngine(calc/eval)，記憶值以 MEM 送出；紙帶存原始值，設定改變時用「把數值當常數算式」交給引擎重新格式化，JS 不自己格式化；錯誤只顯示在輸入框下方不進紙帶；Chain 模式顯示 −2^2 = 4 提示
- views/settings.js：選了立即生效（settings.commit 寫入＋套用外觀＋發 bacalc-settings 事件）；即時預覽由引擎格式化；關於區的 SHELL_HASH 讀 sw.js 文字、MicroPython 套件版本讀 py/manifest.json（避免與 SHELL_HASH 循環），計時取自 app.js 的 timings
- run.js 記錄每張工作表最後一次仍有效的成功計算，bacalc-settings 事件時重新呼叫該畫面的 onAction（含 AMORT／DEPR 表格與 CSV）；頁首加小數位數選單
- 日期顯示格式：date／bond 的日期欄位旁加讀數（輸入欄位仍是 type=date）；稅額分頁開啟時套用設定的稅率預設

**產出**
- web/js/{memstore,tape,keypad,datefmt}.js、views/{calc,settings,datereadout}.js；修改 app.js、settings.js、sheets.js、run.js、form.js、date.js、bond.js、business.js、index.html、app.css、sw.js；tests/js/{memstore,tape,keypad}.test.mjs、settings.test.mjs

**驗證**
- node --test 全綠、pytest 全綠、build_web／check_shell／check_portable 通過
- 瀏覽器：200+10% → 220.00；Chain 下 2+3*4 → 20.00；點紙帶把 200+10% 帶回輸入框；M3=7 後 M÷0 顯示「記憶沒有改變：除以零」且 M3 仍 7.00；TVM 算出 PMT 599.55 後頁首改 4 位 → 即時變 599.5505；歐式千分位切換後紙帶 2.469.135,78 ↔ 2,469,135.7820

**問題與修正**
- memstore.store(i, undefined) 因預設參數 x = 0 被當成 0 存入（測試抓到），改為不給預設值
- 先用 Bash heredoc 寫檔因引號解析失敗，改用 Write 工具
- 測試與實作同時寫，沒有單獨保留 RED 輸出
- 瀏覽器工具輸入欄位後立刻操作頁首選單，會先觸發欄位的 change（blur）使結果標為過期（既有 watchStale 的保守行為，不會顯示錯數字）

**待辦**
- Task 25：紙帶、記憶、設定的持久化（IndexedDB）

## 2026-10-20 Task 24 修正輪 1：紙帶重新格式化的競態

**需求**
- 審查：reformatAll 在 await 前取項目、之後依位置回寫，紙帶變動（裁掉舊項目、清除後再計算）會把顯示字串寫到錯的項目；連續兩次設定變更沒有世代保護；另要求引擎失敗時保留舊字串、計算中要有提示

**做法**
- tape.js：每個項目有唯一 id，setDisplay(index) 改為 setDisplayById(id, …)（項目不在回傳 false，不動其他項目）；toJSON 不含 id
- calc.js：reformatAll 用 createGuard 世代，較舊一輪結果丟棄；以項目物件的 id 回寫；ANS 顯示只在 ANS 未變時更新；formatValue 失敗回 null，紙帶／ANS 保留舊字串，記憶格才顯示 "?"；calculate 忙碌時顯示「計算中…請稍候」

**產出**
- 修改 web/js/tape.js、views/calc.js、tests/js/tape.test.mjs（新增編號與 setDisplayById 測試）

**驗證**
- node --test 85 pass、pytest 全綠、build_web／check_shell 通過
- 瀏覽器：紙帶三筆後連續改小數 5→3→6→1，紙帶全部是 1 位（3.3／0.7／0.3）；改 4 位的同時清除紙帶再算 7/3，只出現 2.3333 一筆且結果正確

**問題與修正**
- 世代保護的純邏輯沿用 generation.js（已有測試），沒有另寫新 helper

**待辦**
- Task 25 持久化

## 2026-10-20 Task 25：IndexedDB 本機儲存與 JSON 匯出入

**需求**
- 設定、具名情境、紙帶、記憶改存 IndexedDB（資料庫 bacalc v1）；JSON 匯出入（合併／取代，驗證 app／schema）；IndexedDB 不可用時不當機並提示一次

**做法**
- storage/idb.js：get／put／all／del／clear 的 Promise 包裝；開啟失敗、逾時（3 秒）、沒有 indexedDB、單次寫入失敗都退回記憶體備援並呼叫 onUnavailable 一次
- storage/backup.js（純函式）：makeExport、validateImport、normalizeData（設定經 sanitize、記憶經 memstore.fromJSON、紙帶經 createTape）、mergeData、importBackup；storage/persist.js：紙帶 debounce 300 ms、記憶、情境、整份讀寫
- settings.js：啟動時 init() 載入記憶體（get() 仍同步）、一次性從 localStorage 搬家（確定寫進 IndexedDB 才移除舊鍵）、新增 replace()
- views/scenarios.js：儲存／載入／重新命名／刪除情境（getFieldState／setFieldState，載入後 markStale）；設定頁「資料」區（匯出、匯入、合併或取代、清除所有資料）；calc.js 新增 replaceState 並在變動後存檔；app.js 啟動時還原

**產出**
- web/js/storage/{idb,backup,persist}.js、web/js/views/scenarios.js；tests/js/{backup,idb}.test.mjs、helpers/fake-idb.mjs；改 settings.test.mjs；sw.js APP_SHELL、index.html、app.css

**驗證**
- node --test 全綠、pytest 全綠、build_web／check_shell 通過
- 瀏覽器 e2e：存兩個情境、重新命名、刪除（confirm 取消不刪）、匯出、清除所有資料、匯入（壞檔四種錯誤訊息、取代會跳確認且可取消、合併保留較新的本機改名）、重新整理後紙帶／記憶／小數位數仍在

**問題與修正**
- 先用 Bash heredoc 寫大檔因引號解析失敗，改用 Write 工具
- 測試與實作同時寫，沒有單獨保留 RED 輸出；合併測試一個時區算術是我算錯（測試錯、實作對），已修測試
- 合併紙帶時額外去除完全相同（ts、算式、值）的項目，避免同一份備份匯入兩次後紙帶加倍

**待辦**
- 表格式輸入（CF 現金流表、STAT 資料）不在情境內，目前情境只存表單欄位
- Task 26 之後：雲端同步（選用）

## 2026-10-20 Task 25 修正輪 1：情境表格、匯入加固、紙帶 flush

**需求**
- 審查：CF、STAT 的情境沒存表格內容，載入後舊表格與新 CF0／I 混在一起；另有匯入加固、關頁前 flush 紙帶、搬家只在 IDB 真的寫入成功時移除舊鍵

**做法**
- grid.js 新增 attachScenarioHooks：form 上的 scenario-capture／scenario-apply 事件，存 inputs.__grid；載入時有表格就還原，沒有（或形狀不符）就重設為空白；CF、STAT 掛上；AMORT／DEPR 的輸出表由載入後送出的 change 事件清掉
- backup.js：sanitizeGrid、sanitizeScenarioInputs（只留該工作表已知輸入欄位、text 字串、direction in/out、exact 有限數）；normalizeData 丟棄未知工作表、名稱截 80 字、情境上限 1000
- idb.put 回傳是否真的寫進 IndexedDB；settings 搬家只在 true 時移除 localStorage 舊鍵
- persist.js：pagehide 與 visibilitychange（hidden）立刻 flush 紙帶

**產出**
- 修改 grid.js、cashflow.js、stats.js、scenarios.js、backup.js、idb.js、settings.js、persist.js；新增測試 sanitizeGrid／sanitizeScenarioInputs／normalizeData 加固／搬家失敗保留舊鍵

**驗證**
- node --test 114 pass、pytest 全綠、build_web／check_shell 通過
- 瀏覽器：CF 存三筆現金流的情境，改表格後載入，三筆還原；先算 NPV=80.4449 再載入，輸出清空；舊情境（無表格）載入後表格重設為空白

**問題與修正**
- 瀏覽器模組快取舊檔，第一次驗證沒載到新程式（結果錯誤是舊 grid.js），以 fetch cache reload 後重載才正確
- 單元測試只涵蓋純函式；attachScenarioHooks 以瀏覽器驗證，STAT 未另行目視（同一個掛鉤）

**待辦**
- 無

## 2026-10-20 Task 26：Google Drive 同步（選用）與 OAuth 申請說明

**需求**
- 選用的 Google Drive 同步（appDataFolder、drive.appdata）：上傳、下載（合併／取代）、衝突詢問、中斷連結；Client ID 由使用者自行申請，另附申請說明

**做法**
- 新增 web/js/storage/gdrive.js：純函式（isValidClientId、buildMultipartBody、parseFileList、decideConflict、localUpdatedAt、stripLocalOnly、describeHttpError）與 createDrive(fetch, getToken)（找／建立 multipart／更新 PATCH media／下載 alt=media）；GIS 只在按「連結」時動態載入，權杖只放記憶體
- settings.js 新增 gdriveClientId、gdriveLastSync（含驗證）；設定頁「資料」下方新增同步區；下載流程為 取得 → JSON.parse → importBackup 驗證 → 通過才 applyData
- 上傳／下載內容不含 gdrive 設定鍵；取代下載後保留本機 Client ID
- docs/google-oauth-setup.md 以 WebFetch 查官方頁面撰寫，轉成 HTML

**產出**
- gdrive.js、tests/js/gdrive.test.mjs（19 項）、views/settings.js 同步區、sw.js 加入 gdrive.js、docs/google-oauth-setup.md／.html

**驗證**
- node --test 132 pass；pytest 全綠；build_web、check_shell、check_portable 通過
- 瀏覽器（localhost:8765）：同步區顯示；無 Client ID 時連結鈕停用；壞格式被拒；存好格式後按鈕啟用；頁面無任何跨源請求、未載入 GIS
- 未做真正的 OAuth（需使用者自己的 Client ID）

**問題與修正**
- 第一次用 bash heredoc 寫檔因引號失敗（無任何檔案寫入），改用 Write 工具
- settings 預設值多了兩個鍵，兩個既有測試的期望值需更新
- 預覽伺服器根目錄就是 web/（網址 /index.html），舊 SW 快取需先註銷才會載入新檔

**待辦**
- Step 3：使用者申請 Client ID 後手動測：上傳 → 改本機 → 下載出現衝突提示 → 選雲端版本
- 本機「是否改過」只由情境 updated_at 與紙帶 ts 判斷，單改設定／記憶不會被視為變動

## 2026-10-20 Task 26 修正輪 1：內容雜湊偵測本機變更、覆蓋前確認

**需求**
- 審查：本機變更只看情境／紙帶時間，下載（預設合併）會無提示覆蓋記憶與設定；衝突對話框的「用雲端版本」其實是合併

**做法**
- gdrive.js：stableStringify、hashData（純 JS cyrb53，鍵順序無關、排除只屬本機的設定）、isLocalEmpty、isLocalChanged（無雜湊時有資料即視為改過）、overwriteSummary；decideConflict 第一參數改為 localChanged 布林；LOCAL_ONLY_KEYS 加 gdriveLastSyncHash
- 每次上傳／下載成功後存 gdriveLastSyncHash；upload／download 接受 expectedModified，雲端在決定動作後被改過就中止（不寫入）
- 設定頁：下載時記憶或設定會被覆蓋則先 confirm（合併與取代皆然）；本機為空時上傳先 confirm；衝突對話框改為「用雲端版本（取代本機）」「合併雲端與本機」「用本機版本（上傳覆蓋雲端）」「取消」

**產出**
- 修改 gdrive.js、views/settings.js、settings.js、兩個測試檔（新增 5 項測試）

**驗證**
- node --test 137 pass、pytest 全綠、build_web／check_shell 通過；瀏覽器載入新模組正常
- 真正的 Google 流程仍未測（需使用者的 Client ID）

**問題與修正**
- 舊審查意見的「兩個時間比較」改為內容雜湊後，localUpdatedAt 只剩顯示用途

**待辦**
- 使用者以自己的 Client ID 手動測：上傳 → 只改記憶 → 下載應出現衝突／覆蓋確認

## 2026-10-20 Task 27 一鍵驗證與 verify-bacalc skill（tag step8）

**需求**
- `python tools/verify_all.py` 一次跑完全部檢查並產生 `logs/verify-YYYYMMDD-HHMM.html`；專案 skill 說明何時與如何使用；e2e 檢查表

**做法**
- verify_all.py：先 `git status --porcelain` 必須為空（否則 exit 1 並列出）；步驟依序 check_portable → pytest → build_web --check → check_shell → node --test → check_worker → test:mpy → test:mpy --self-test → mutate（--quick 略過並在 log 註明）；某項失敗仍繼續，任一失敗 exit 1
- 子程序以 UTF-8（errors="replace"）解碼並設 PYTHONIOENCODING；stdout 也設 errors="replace"；node 測試直接呼叫 node（等同 npm run），測試檔清單由 Python 展開以避免 Windows glob 問題
- log 沿用既有 verify-*.html 風格；含完整與短 commit、分支、+08:00 時間、Python／Node／MicroPython 套件版本、SHELL_HASH；失敗附末 60 行（HTML 跳脫）
- `--allow-dirty` 僅示範：略過乾淨檢查，log 標題標「DIRTY — 不可作為實驗紀錄」
- e2e：使用者尚未同意 Playwright，故只寫 `e2e/checklist.md`（13 張工作表各一個 golden 值、離線、SW 更新、情境、匯出入、設定、Drive 標「需使用者 Client ID」）

**產出**
- tools/verify_all.py、.claude/skills/verify-bacalc/SKILL.md、e2e/checklist.md
- 完整驗證 log：logs/verify-20261020-2339.html（9 項全 PASS，mutate 約 102 秒，全程約 2 分 22 秒）

**驗證**
- 髒樹時 verify_all 拒絕並 exit 1（實測）
- 示範：把 engine/tvm.py 的 `+ pmt * s` 改成 `- pmt * s`，`--allow-dirty --quick` → exit 1，pytest（tvm_iy_loan 等）、build_web --check（web/py 與 engine 不同）、test:mpy 及 --self-test 標 FAIL；以 `git checkout -- engine/tvm.py` 還原，樹乾淨；示範 log 已刪除，避免 DIRTY log 進 repo
- 乾淨樹完整跑一次全 PASS

**問題與修正**
- 示範時 build_web --check 與 test:mpy 也跟著失敗，原因是 web/py 為舊的正確建置，與被改壞的 engine 不一致，屬預期
- Git Bash 直接顯示輸出會亂碼（cp950），log 檔本身為 UTF-8，不影響
- flake8 對 verify_all.py 有 7 處 E501（CSS 字串與一行指令），未處理
- e2e 檢查表的毛利、損益兩平、Δ%、稅額預期值由公式推算，未經瀏覽器實測

**待辦**
- 使用者若同意安裝 Playwright，再把 e2e/checklist.md 自動化為 e2e/test_ui.py
- 跑一次檢查表 A～F 並實測毛利／稅額等顯示格式

## 2026-10-21 Task 28 GitHub Pages 部署與 README（程式部分，未打 step9）

**需求**
- 用 GitHub Actions 測試並部署 web/ 到 GitHub Pages；README；補 Task 27 遺留的 e2e/checklist.md CALC 預期值

**做法**
- `.github/workflows/pages.yml`：push main＋workflow_dispatch；job test（pytest、check_portable engine golden、build_web、check_shell、run_mpy_golden、node --test、check_worker），job deploy（needs test，重新 build_web 後 configure-pages → upload-pages-artifact path web → deploy-pages）；permissions、concurrency group pages（不取消進行中）、environment github-pages
- action 版本經查 GitHub releases 頁：checkout v7、setup-python v7、setup-node v7、configure-pages v6、upload-pages-artifact v5、deploy-pages v5（比指示的 v4/v5/v3 等新，故採用最新大版本）
- CI 不跑 mutate.py（太慢），README 與 workflow 註解都有註明
- README.md 繁中：簡介、網址、功能、手機安裝（Android／iOS、離線、iOS 儲存可能被清除）、本機開發、測試、MVC 結構、step0–step9、文件連結、授權未選定
- e2e/checklist.md CALC 預期值改 14.00

**產出**
- .github/workflows/pages.yml、README.md、e2e/checklist.md（修正）

**驗證**
- 以 `git checkout-index`（autocrlf=false，模擬 Linux LF）匯出暫存區到乾淨目錄，`npm ci` 後依序跑 workflow 全部指令：pytest 全過且 0 skip、check_portable exit 0、build_web、check_shell 通過、MicroPython golden 51/51 與 24/24、node --test 137 pass 0 fail、check_worker PASS；暫存目錄已刪
- YAML 以 PyYAML 解析 OK；`pytest -p no:不存在的外掛` 不會報錯，hydra 旗標在無該外掛的 CI 無害
- tests/ 不呼叫 tools/make_golden_excel.py（Excel COM），無 Windows 限定測試

**問題與修正**
- 無法在本機執行真正的 GitHub Actions（沒有 runner），也未驗證 Linux 大小寫敏感路徑；首次線上執行才是最終驗證
- 版本號依 WebFetch 讀 releases 頁，非本機可驗證

**待辦**
- 使用者設定 Settings → Pages → Source = GitHub Actions；controller 推送、確認線上網址與 selftest.html 全綠
- 手機安裝與飛航模式測試後打 tag step9

## 2026-10-21 Task 29 教學單一來源 teaching/prompts.py

**需求**
- 建立 AI Agent 版與 EMBA 版共用的教學單一來源：STEPS（step0～step9）、USER_CLAUDE_MD、PROJECT_CLAUDE_MD，供 Task 30 產生 Prompt 卡與簡報

**做法**
- 依控制者裁示：每步 AI 版 Prompt 用四段式【任務】【介面】【限制】【驗收】（使用者 Lab 7 v5 風格），【介面】只寫別人依賴的檔名、bridge 格式、元素 id、指令
- 每步加一句話下法 bad_prompt；bad_result 開頭「推測：」（一句話版本未實測），bad_evidence 開頭「實際踩過：」並附 DEVLOG／progress ledger 出處；pitfalls 只放本專案實際發生過的坑
- EMBA 版：白話四段式、verify 用 Excel 公式與 BA II Plus 按鍵對答案（數值取自 tests/golden/excel.json）；start_tag 為上一步完成的 tag（step0 用 step0、step8 用 step6，因 step7 無 tag）
- step7 標 optional、tag None、「選用，作者未實測」；step9 tag 名稱預定為 step9（尚未打）
- 測試先寫（RED：ModuleNotFoundError: No module named 'teaching'），再寫內容

**產出**
- teaching/__init__.py、teaching/prompts.py、tests/test_prompts.py（13 項）

**驗證**
- python -m pytest tests/test_prompts.py -q：13 passed；全套 288 passed
- 驗收指令引用的 32 個路徑／npm script 以 git ls-tree 與 git show <tag>:package.json 在對應 tag 上確認存在；step7／step9 改查工作樹
- 無全形句點、四段標籤順序、兩層 CLAUDE.md 結構皆由測試鎖住

**問題與修正**
- 失敗的嘗試：第一次 GREEN 時 step0 的 `claude -p "engine/ 可以 import decimal 嗎"` 被路徑檢查當成 engine/ 路徑（step0 尚無 engine/）而失敗 → 測試對 claude 指令略過引號內文字
- CI（GitHub Actions 淺層 clone）沒有 step* tag：tag 相關測試在無 tag 時 skip 並說明原因，只在本機檢查
- flake8 有 76 處 E501（多為 Prompt 原文與中文字串），內容字串未折行
- 一句話下法的結果尚未實測，全部標「推測」；Task 31 演練後應以實測結果更新

**待辦**
- Task 30 依本檔產生 Prompt 卡與簡報；Task 31 演練後回寫 pitfalls 與 bad_result
- step9 打 tag 後，test_prompts 會自動改用 tag 檢查 step9 的驗收指令

## 2026-10-21 Task 29 修正輪 1：按鍵標示未驗證、DEPR 順序、白話用語

**需求**
- 審查意見：BA II Plus 按鍵依記憶撰寫卻寫成事實；DEPR 欄位順序可能錯；step0 五段式與 step0 tag 不符；RED/GREEN 指令的 -q 重複；EMBA npm 坑的原因寫錯；EMBA 殘留術語；測試文件未註明不查旗標

**做法**
- 5 處 BA II Plus 按鍵都加「（按鍵依記憶撰寫，未實機驗證）」，新增 test_ba_keystrokes_marked_unverified（含按鍵的 BA II Plus 字串必須含「未實機驗證」）
- DEPR 改為 LIF、M01、CST、SAL、YR、DEP、RBV、RDV（推測順序，同樣標未驗證），拿掉「依序」等暗示按鍵次數確定的字樣
- step0 expected／verify 改對照 PROJECT_CLAUDE_MD 範本，註明 step0 tag 的 CLAUDE.md 早於範本、段落不同
- step2 要貼 RED/GREEN 處改用 python -m pytest（pytest.ini 已含 -q）
- EMBA npm 坑改為「先確認專案資料夾有 package.json」；Service Worker、commit、突變測試改白話，JSON、OAuth Client ID 加括號說明
- tests/test_prompts.py docstring 註明只查路徑與 npm script，不查旗標、不執行指令

**產出**
- teaching/prompts.py、tests/test_prompts.py（14 項）

**驗證**
- python -m pytest tests/test_prompts.py：14 passed；python -m pytest：289 passed；prompts.py 無「。」

**問題與修正**
- 無失敗嘗試；BA II Plus 按鍵（含 DEPR 欄位順序）仍未實機或手冊核對，只是標示清楚

**待辦**
- 上課前用實體 BA II Plus 或 TI Guidebook 核對 5 段按鍵，核對後移除「未實機驗證」並調整測試
