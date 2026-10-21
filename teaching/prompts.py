"""BACalc 教材單一來源（single source）：兩個版本（AI Agent 版、EMBA 版）共用的步驟與 Prompt

Prompt 卡（HTML）與簡報（PPT）都由本檔產生，請只改這裡
匯入本模組沒有副作用（side effect）：只定義常數，不讀寫檔案、不執行指令

結構
- USER_CLAUDE_MD：使用者層級 ~/.claude/CLAUDE.md 範本（五條通用原則）
- PROJECT_CLAUDE_MD：專案層級 CLAUDE.md 範本（五段：常用指令／專案結構／程式風格／工作方式／重要規則）
- STEPS：10 筆 dict，id 為 step0～step9，鍵如下
  - id、title、goal
  - tag：本步完成後的參考答案 git tag；step7 為 None（使用者決定不打，Drive 作者未實測）
    step9 的 tag 要等部署與手機實測後才打
  - optional：只有 step7 為 True（選用，作者未實測）
  - ai：AI Agent 版
    - prompt：四段式【任務】【介面】【限制】【驗收】，【介面】只寫別人會依賴的東西
    - bad_prompt：一句話下法（對照組）
    - bad_result：一句話下法可能的結果，開頭「推測：」（本專案尚未實測一句話版本）
    - bad_evidence：本專案實際發生過的同類問題，開頭「實際踩過：」並附出處
    - expected：預期產出
    - verify：list[str]，在該步 tag 上存在、可執行的驗收指令
    - pitfalls：list[str]，本專案實際踩過的坑（附 DEVLOG 或審查紀錄 progress ledger 出處）
  - emba：EMBA 版（白話、不談程式碼）
    - prompt：白話四段式
    - expected
    - verify：list[str]，拿 Excel 或實體 BA II Plus 對答案的具體操作
    - pitfalls：list[str]，白話版的實際踩坑
    - start_tag：起點 tag（上一步完成的狀態），學生從這裡接手做本步
      step0 以 step0 為起點（只有規格與 CLAUDE.md），step8 以 step6 為起點（step7 沒有 tag）

字串規則（簡報規則）：不用全形句點，以換行或不加結尾標點；Prompt 可以用「你」稱呼 AI
"""

# ---------------------------------------------------------------------------
# 兩層 CLAUDE.md 範本
# ---------------------------------------------------------------------------

USER_CLAUDE_MD = """\
# 我的通用規則（~/.claude/CLAUDE.md，所有專案共用）

- 回答用繁體中文，重要名詞附英文（例如 單元測試 unit test）
- 不確定就直接說「不確定」，不要編造；查資料要附連結與搜尋關鍵字
- 寫完程式要自己測試，貼出實際執行的指令與結果再回報
- 大改動先給我計畫，我同意後再動手
- 安裝套件、刪除檔案、推送 GitHub、關閉我開著的程式之前，先問我
"""

PROJECT_CLAUDE_MD = """\
# BACalc 專案規範（專案層級 CLAUDE.md）

仿 TI BA II Plus 的財務計算 PWA，Python 計算引擎在瀏覽器裡用 MicroPython 執行，手機電腦都能用、可離線
（下面的指令在後面的步驟才會建立，先寫下來讓 AI 知道目標）

## 常用指令

- 引擎測試：`python -m pytest -q`
- 可攜性檢查：`python tools/check_portable.py engine`
- 建置網頁：`python tools/build_web.py`
- 本機預覽：`python -m http.server 8765 -d web`，開 http://localhost:8765/
- 一鍵驗證：`python tools/verify_all.py`（產生 `logs/verify-*.html`）

## 專案結構

- Model：`engine/*.py`，純 Python 計算，沒有 I/O、不碰瀏覽器
- Controller：`engine/bridge.py`（唯一入口）、`web/js/app.js`、`web/js/py-worker.js`
- View：`web/index.html`、`web/css/`、`web/js/views/`
- 測試：`tests/`；golden 值：`tests/golden/excel.json`，每筆附 Excel 公式出處

## 程式風格

- Python、PEP 8；註解用繁體中文，重要名詞附英文
- 金額用「分」整數（`engine/money.py`），日期用序數日（`engine/dates.py`）

## 工作方式

- 先寫會失敗的測試，再寫程式（TDD），RED 與 GREEN 的輸出都要貼
- 改完先跑 `python -m pytest -q`，通過再回報
- 每次工作結束把過程追加到 `DEVLOG.md`：需求／做法／產出／驗證／問題與修正／待辦，只追加不改寫，失敗的嘗試也要寫
- 大改動先給計畫

## 重要規則

- MVC 分層，計算只放在 Model
- 絕不產生看起來正常但錯誤的數字：算不出來回 `{"ok": false, "error": 中文原因}`，不用 0 或預設值
- 禁止 `eval`／`exec`（MicroPython 沒有 `ast`），算式用自寫遞迴下降剖析器
- `engine/` 只能 import `math`、`json`（MicroPython 沒有 decimal、datetime、dataclasses）
- golden 值對不上就停下來回報，不改 golden、不放寬容差
"""

# ---------------------------------------------------------------------------
# 共用的對照答案（Excel 公式與 BA II Plus 按鍵），各步驟引用
# ---------------------------------------------------------------------------

_EXCEL_PMT = "Excel 輸入 =PMT(0.06/12,360,300000)，應得 -1,798.65（可能顯示成貨幣格式）"
_BA_PMT = ("BA II Plus：[2ND][CLR TVM]，確認 [2ND][P/Y] 為 12 後 [2ND][QUIT]，"
           "360 [N]、6 [I/Y]、300000 [PV]、0 [FV]、[CPT][PMT]，應顯示 -1,798.65")
_EXCEL_NPV = "Excel 輸入 =-10000+NPV(0.1,3000,4200,6800,-1500)，應得 282.77"

# ---------------------------------------------------------------------------
# 步驟
# ---------------------------------------------------------------------------

STEPS = [
    # ------------------------------------------------------------------ step0
    {
        "id": "step0",
        "title": "兩層 CLAUDE.md：先教 AI 規矩",
        "goal": "使用者層級放個人通用習慣，專案層級放這個專案的規則，"
                "AI 每次開工都會先讀到，不用每次重講",
        "tag": "step0",
        "optional": False,
        "ai": {
            "prompt": """\
【任務】
幫我建立這個專案的 CLAUDE.md（專案層級），專案是仿 TI BA II Plus 的財務計算 PWA
我的通用習慣已經寫在 ~/.claude/CLAUDE.md，不要重複寫進專案檔
【介面】
- 專案根目錄：CLAUDE.md、DEVLOG.md（先只有標題）
- CLAUDE.md 固定五段：常用指令／專案結構／程式風格／工作方式／重要規則
【限制】
- 只寫這個專案特有、可以檢查的規則，一條一行
- 一定要有：MVC 分層、算不出來就回錯誤不回假數字、engine/ 只用 math 與 json（之後要在 MicroPython 跑）、禁止 eval
- 這一步不寫程式、不安裝任何東西
【驗收】
- 寫完用三點複述最重要的規則
- 我開新對話問「engine/ 可以用 decimal 嗎」，你要回答不行並說明原因""",
            "bad_prompt": "幫我寫一個 CLAUDE.md",
            "bad_result": "推測：AI 會寫出一份通用的 Python 專案規範，"
                          "很可能建議用 decimal 算金額、datetime 算日期，"
                          "沒有「可攜子集」與「不回假數字」，後面每一步都要重講",
            "bad_evidence": "實際踩過：規劃時原本要用 AST 白名單解析算式，"
                            "自我檢查才發現 MicroPython 沒有 ast 模組，改成自寫遞迴下降剖析器"
                            "（DEVLOG 2026-10-20 規格修訂）；"
                            "執行環境的限制沒寫進 CLAUDE.md，AI 每次都會重新犯",
            "expected": "~/.claude/CLAUDE.md 有五條通用原則；專案根目錄有五段式 CLAUDE.md 與 DEVLOG.md；"
                        "AI 能正確複述規則",
            "verify": [
                'claude -p "用三點複述這個專案 CLAUDE.md 最重要的規則"',
                'claude -p "engine/ 可以 import decimal 嗎？為什麼"',
                "git show step0:CLAUDE.md",
            ],
            "pitfalls": [
                "MicroPython 沒有 ast，原本「AST 白名單解析算式」不可行，"
                "這種限制要一開始就寫進 CLAUDE.md（DEVLOG 2026-10-20 規格修訂）",
                "CLAUDE.md 寫了「安裝套件前先問」，AI 真的在 npm install MicroPython 前停下來等同意"
                "（progress ledger M1 結尾）；沒寫的規則 AI 不會自己遵守",
                "需求只給一半時 AI 會猜：修規格時使用者第一則訊息只有「規格書要修改：」，"
                "請使用者補充後才拿到真正需求（DEVLOG 2026-10-20 規格修訂）",
            ],
        },
        "emba": {
            "prompt": """\
【任務】
我要做一個像 BA II Plus 的財務計算機 App，請先幫我寫一份工作規則檔 CLAUDE.md
【介面】
規則檔放在專案資料夾最上層，分成：常用指令、專案結構、程式風格、工作方式、重要規則
【限制】
- 算不出來時要說明原因，絕對不能顯示看起來正常但錯誤的數字
- 每個結果都要能拿 Excel 或計算機對得起來
- 每次改完要自己測試，再用白話告訴我測了什麼
【驗收】
寫完請用三句白話告訴我，你會遵守哪三條最重要的規則""",
            "expected": "得到一份 CLAUDE.md；AI 能用白話說出「不回假數字」「要能用 Excel 對答案」「改完先測」",
            "verify": [
                "打開 step0 的 CLAUDE.md，找到「絕不產生看起來正常但錯誤的數字」這一條",
                "先在 Excel 輸入 =PMT(0.06/12,360,300000)，得到 -1,798.65，"
                "記下這個房貸數字，之後每一步都用它當對照",
                "開新對話問 AI「如果期數算出 24.5 期，你會怎麼顯示」，"
                "答案應該是回報錯誤，而不是四捨五入成 24 或 25",
            ],
            "pitfalls": [
                "規則沒寫清楚，AI 就會自己決定：本專案的程式曾把 24.5 期直接當成 24 期算，"
                "數字看起來完全正常",
                "規則要寫成可以檢查的句子，例如「算不出來要說原因」，不要只寫「要正確」",
            ],
            "start_tag": "step0",
        },
    },
    # ------------------------------------------------------------------ step1
    {
        "id": "step1",
        "title": "用 plan mode 先規劃再動手",
        "goal": "讓 AI 先寫規格書與實作計畫，確認 MVC、測試方式與每一步怎麼驗收，同意後才寫程式",
        "tag": "step1",
        "optional": False,
        "ai": {
            "prompt": """\
【任務】
用 plan mode 規劃這個財務計算機 PWA：先寫規格書，我同意後再拆成實作計畫
這一步不寫任何程式
【介面】
- 產出 docs/spec-<日期>.md 與 docs/plan-<日期>.md，用 python tools/md2html.py 轉成同名 HTML
- 計畫的每個 Task 寫明：要建立的檔案、對外介面、測試、commit 訊息
- bridge 統一回傳格式
  成功 {"ok": true, "values": {...}, "display": {...}, "warnings": []}
  失敗 {"ok": false, "error": 中文原因, "field": 欄位或 null}
【限制】
- 引擎要在瀏覽器裡跑：先比較 Pyodide 與 MicroPython 的下載大小，附資料來源連結，寫進規格
- 每個工作表至少 3 個 golden 值，每個都附 Excel 公式或 TI 手冊頁碼當出處
- 列出所有要我親自做或同意的事：安裝套件、Google OAuth、推送 GitHub、手機實測
【驗收】
- 計畫包含 MVC 分層、TDD、突變測試、MicroPython 雙執行環境測試
- 寫完自我檢查一次，列出你不確定的地方""",
            "bad_prompt": "幫我做一個 BA II Plus 計算機的網頁 App",
            "bad_result": "推測：AI 直接開始寫 HTML 與 JavaScript，計算寫在畫面程式裡（沒有 MVC），"
                          "沒有 golden 值與出處，也不會先比較執行環境的大小",
            "bad_evidence": "實際踩過：規格第一版用 Pyodide，修訂時實測 jsDelivr 傳輸大小，"
                            "Pyodide 約 5.3 MB、MicroPython 約 0.23 MB，才改成 MicroPython"
                            "（DEVLOG 2026-10-20 規格修訂）；如果先寫程式再換執行環境，要整個重來",
            "expected": "docs/ 下有規格書與實作計畫（md 與 html）；計畫拆成小 Task，每個 Task 有測試與 commit 訊息",
            "verify": [
                "python tools/md2html.py docs/plan-2026-10-20.md",
                'grep -n -E "MVC|突變|golden" docs/plan-2026-10-20.md',
                'claude -p "列出 docs/plan-2026-10-20.md 中需要我親自做的事"',
            ],
            "pitfalls": [
                "計畫本身也會錯，要請 AI 自我檢查：本專案自查發現算式文法讓 -2^2 變成 4、"
                "千分位逗號和 nCr 參數逗號衝突，先改計畫再實作（DEVLOG 實作計畫）",
                "Excel 沒有內建的功能（現金流回收期 PB、DPB）不要硬造 golden，"
                "計畫裡標明改用手算測試（progress ledger Task 2 裁定）",
                "計畫裡寫的工具指令可能和實作不同：計畫寫 python -m golden.runner --dump，"
                "實作改成 python tools/golden_dump.py（DEVLOG Task 2）",
            ],
        },
        "emba": {
            "prompt": """\
【任務】
先不要寫程式，請先規劃這個計算機 App 要有哪些功能、分幾步做、每一步怎麼驗收
【介面】
給我一份看得懂的計畫：每一步寫「做完會看到什麼」和「我要怎麼對答案」
【限制】
- 功能以 BA II Plus 為準：貨幣時間價值、攤還、現金流、利率換算、統計、債券、折舊
- 每個功能至少 3 題可以用 Excel 對答案的例題，附 Excel 公式
- 你不確定的地方要直接說不確定
【驗收】
我會挑兩題例題自己在 Excel 算，數字要一樣""",
            "expected": "一份分步驟的計畫，每個功能都附 Excel 公式例題，並列出需要我做決定的事",
            "verify": [
                _EXCEL_PMT + "（計畫中的房貸例題）",
                "Excel 輸入 =EFFECT(0.12,12)，應得 0.126825，也就是有效年利率 12.68%",
                "逐項對照計畫：每個功能都要有例題與 Excel 公式，缺的請 AI 補上",
            ],
            "pitfalls": [
                "例題的 Excel 公式本身也可能寫錯：本專案統計迴歸有一題公式少了一層 EXP，"
                "程式算 1.4042、公式算 0.3395，對不上才發現是公式錯",
                "有些功能 Excel 沒有內建（例如回收期），這種例題要請 AI 列出逐期累計讓你手算",
            ],
            "start_tag": "step0",
        },
    },
    # ------------------------------------------------------------------ step2
    {
        "id": "step2",
        "title": "TDD：TVM 貨幣時間價值引擎",
        "goal": "先寫會失敗的測試再寫程式，用 Excel 公式當標準答案，"
                "做出可以同時在 CPython 與 MicroPython 執行的 TVM 引擎",
        "tag": "step2",
        "optional": False,
        "ai": {
            "prompt": """\
【任務】
用 TDD 實作 TVM 貨幣時間價值：N、I/Y、PV、PMT、FV 五格留一格空白，算出那一格
先寫會失敗的測試並執行給我看（RED），再寫程式讓它通過（GREEN）
【介面】
- engine/tvm.py 的 solve(inputs, unknown)，inputs 鍵為 N、IY、PV、PMT、FV、PY、CY、BGN，回傳 bridge 統一格式
- golden 放 tests/golden/excel.json，每筆有 id、call、expected、source（Excel 公式字串）、tol
- python tools/check_portable.py engine：有違規 exit 1
【限制】
- engine/ 只能 import math、json 與 engine 內部模組（MicroPython 沒有 decimal、datetime、dataclasses）
- 求 I/Y 用牛頓法加二分法，|f(x)| < 1e-10、最多 200 次，未收斂回錯誤
- 求出 N ≤ 0 或無解時回 {"ok": false}，不回傳看似合理的數字
- golden 對不上就停下來回報，不准改 golden 或放寬容差
【驗收】
- python -m pytest tests/test_tvm.py -q 全過，貼出 RED 與 GREEN 兩次輸出
- 房貸 N=360、I/Y=6、PV=300000、FV=0，PMT 應為 -1798.65（=PMT(0.06/12,360,300000)）""",
            "bad_prompt": "用 Python 寫 TVM 計算，要有測試",
            "bad_result": "推測：AI 先寫程式再補測試，金額可能用 decimal，"
                          "無解時回 0 或負的期數，測試只驗它自己算出來的數字，沒有外部出處",
            "bad_evidence": "實際踩過：PV、PMT 同號的無解案例，初版求 N 回傳約 -8.3 期，"
                            "看起來像數字其實沒有意義，改成 N ≤ 0 一律回錯誤（DEVLOG Task 5）",
            "expected": "engine/tvm.py、money.py、dates.py、solver.py、result.py 與對應測試；"
                        "tests/golden/excel.json 每筆附 Excel 公式；check_portable 通過",
            "verify": [
                "python -m pytest tests/test_tvm.py -q",
                "python -m pytest -q",
                "python tools/check_portable.py engine",
                "python tools/golden_dump.py",
            ],
            "pitfalls": [
                "沒留 RED 輸出就不算 TDD：要求 AI 先跑一次失敗的測試並貼出來"
                "（本專案有幾個 Task 測試與實作同時寫，DEVLOG 都誠實記下「沒有單獨保留 RED」）",
                "測試要真的走到想測的路徑：求根器測試第一版用線性函數，牛頓法兩步就收斂，"
                "二分法根本沒跑到，改用立方根函數（DEVLOG Task 4 修正輪 1）",
                "本機 pytest 外掛干擾：hydra 外掛一載入就崩潰，用 pytest.ini 的 -p no:hydra_pytest 停用，"
                "不必移除套件（DEVLOG Task 0＋1）",
                "萬分比寫錯分母：稅率初版除以 1000000（應為 10000），是測試 RED 才抓到（DEVLOG Task 3＋4）",
                "I/Y 真的是 0% 時牛頓法停在 -1.2e-7%，畫面可能顯示 -0.00（progress ledger Task 5，待改）",
            ],
        },
        "emba": {
            "prompt": """\
【任務】
請做出貨幣時間價值 TVM 的計算：期數、年利率、現值、每期付款、終值五格，空一格就算出那一格
【介面】
欄位名稱和 BA II Plus 一樣：N、I/Y、PV、PMT、FV、P/Y、C/Y、期初 BGN／期末 END
【限制】
- 收到的錢是正數、付出的錢是負數，和計算機一樣
- 算不出來時說明原因，不要給 0 或亂猜的數字
- 每個例題都要附 Excel 公式讓我自己對
【驗收】
房貸例題：30 年、年利率 6%、借 300,000、每月付款，告訴我每月付多少，並說明你怎麼測試""",
            "expected": "AI 回報每月付款 -1,798.65（負號代表付出），並說明測試全部通過",
            "verify": [
                _EXCEL_PMT,
                _BA_PMT,
                "Excel 輸入 =FV(0.03/12,60,-500,0,1)，應得 32,404.16（每月月初存 500、5 年、年利率 3%）",
            ],
            "pitfalls": [
                "PV 填 300,000（收到）時 PMT 是負的，這是對的；本專案在畫面上加了「收到／付出」提示",
                "沒有答案的題目（借錢與還錢同號），程式初版曾回傳 -8.3 期這種沒意義的數字，"
                "後來改成直接報錯；看到奇怪的期數要請 AI 解釋",
            ],
            "start_tag": "step1",
        },
    },
    # ------------------------------------------------------------------ step3
    {
        "id": "step3",
        "title": "其他工作表引擎與突變測試",
        "goal": "照 TVM 的 TDD 方式完成其餘工作表與 bridge，"
                "再用突變測試證明測試真的抓得到錯",
        "tag": "step3",
        "optional": False,
        "ai": {
            "prompt": """\
【任務】
照 step2 的 TDD 方式，一次一個工作表實作其他引擎：AMORT、CF、ICONV、STAT、BOND、DEPR、商業與日期、計算機算式與記憶
最後做 bridge 與突變測試
【介面】
- engine/bridge.py 的 call(request_json) 回傳 JSON 字串，永不擲例外
  request 為 {"sheet": "tvm", "action": "solve", "inputs": {...}, "settings": {...}}
- 每個工作表至少 3 題 golden，放 tests/golden/excel.json，用 tools/make_golden_excel.py 從 Excel 公式產生
- python tools/mutate.py：至少 15 個突變（例如拿掉 BGN 因子），每個都要被測試殺死，結束後 engine/ 要還原
【限制】
- 算式用自寫遞迴下降剖析器，禁止 eval／exec
- 攤還 BAL 與 PV 同號（正數），INT、PRN 為負，和 Excel CUMIPMT／CUMPRINC 一致
- 輸入或結果含 inf、nan 一律回錯誤；期數不是整數直接拒絕，不四捨五入
- golden 對不上就回報我，不改 golden
【驗收】
- python -m pytest -q 全過
- python tools/mutate.py 顯示全部 killed
- python tools/check_portable.py engine 通過""",
            "bad_prompt": "把 BA II Plus 其他功能都做出來",
            "bad_result": "推測：AI 一次寫完全部工作表，測試只確認「有回傳數字」，"
                          "期數 24.5 會被四捨五入、攤還餘額正負號隨便取，也不會有突變測試",
            "bad_evidence": "實際踩過：攤還初版用 round() 取整期數，24.5 期被當成 24 期，"
                            "算出看似正常的錯數字（DEVLOG Task 6 修正輪 1）；"
                            "攤還 BAL 正負號也曾裁定錯，後來改成與 PV 同號（progress ledger Task 2）",
            "expected": "engine/ 下 amort、cashflow、iconv、stats、bond、depr、business、calc、memory、fmt、bridge；"
                        "pytest 全過；mutate.py 全部突變被殺死",
            "verify": [
                "python -m pytest -q",
                "python tools/mutate.py",
                "python tools/check_portable.py engine",
                "python -m pytest tests/test_bridge.py -q",
            ],
            "pitfalls": [
                "golden 公式也會錯：STAT EXP 的 b 原本寫 SLOPE(LN(Y),X)（其實是 ln b），"
                "引擎對照失敗（1.4042 對 0.3395）才發現，改成 EXP(SLOPE(LN(Y),X)) 重產（DEVLOG Task 9）",
                "只測「有錯誤」不夠：CF 溢位改成 inf 後 IRR 回「無法收斂」、NPV 假溢位，"
                "測試只檢查任何 err 所以沒抓到，改成檢查值（DEVLOG Task 7 修正輪 2）",
                "回收期 PB／DPB 在 CF0 ≥ 0 時初版回 0.0，看似合理其實誤導；"
                "9999 期配極端利率會擲 OverflowError（DEVLOG Task 7 修正輪 1）",
                "等價突變：IRR 下限改成 0 仍存活，因為後備掃描會找回同一個根，"
                "要改成複合突變才殺得死（DEVLOG Task 17）",
                "「²」的 str.isdigit() 是 True，3² 被當成數字，改成明確比對 0123456789（DEVLOG Task 14）",
                "DB 折舊部分年度的最後一列整年計算，表尾不到殘值，屬看似合理的錯數字，"
                "改成拒絕 M01≠1（DEVLOG Task 11 修正輪 1）",
                "mutate.py 在 engine/ 有未提交變更時會拒絕執行，先 commit 再跑（DEVLOG Task 18 修正輪 1）",
            ],
        },
        "emba": {
            "prompt": """\
【任務】
請加上現金流的計算：輸入期初投資與各期現金流，算出淨現值 NPV 與內部報酬率 IRR
【介面】
輸入方式和 BA II Plus 一樣：CF0、C01、F01（次數）…，折現率 I
【限制】
- IRR 沒有答案時（例如現金流全是正的）要說明原因，不能顯示 0
- 現金流正負號變化不只一次、可能有多個 IRR 時要提醒我
- 每個結果都附 Excel 公式讓我對
【驗收】
例題：期初投資 -10,000，之後四年 3,000、4,200、6,800、-1,500，折現率 10%，告訴我 NPV 和 IRR""",
            "expected": "NPV 282.77、IRR 11.52%，並提醒現金流有兩次正負號變化",
            "verify": [
                _EXCEL_NPV,
                "Excel 輸入 =IRR({-10000,3000,4200,6800,-1500})，儲存格設成百分比 2 位小數，應得 11.52%",
                "BA II Plus：[CF][2ND][CLR WORK]，CF0 輸入 10000 [+|-] [ENTER]，"
                "[↓] C01=3000 [ENTER] [↓] F01=1，依序輸入 C02=4200、C03=6800、C04=1500 [+|-]，"
                "[NPV] I=10 [ENTER] [↓][CPT] 應得 282.77；[IRR][CPT] 應得 11.52",
            ],
            "pitfalls": [
                "全部是正的現金流沒有 IRR，App 要顯示「IRR 無解：現金流沒有正負號變化」而不是 0",
                "回收期在期初沒有投資時，程式初版回傳 0.0 看似合理，後來改成報錯",
                "Excel 沒有內建回收期函式，這題要請 AI 列出逐期累計現金流讓你手算",
            ],
            "start_tag": "step2",
        },
    },
    # ------------------------------------------------------------------ step4
    {
        "id": "step4",
        "title": "PWA 殼與 MicroPython（Web Worker）橋接",
        "goal": "先用 spike 證明 MicroPython 是雙精度，再讓畫面先顯示、Python 在背景載入，"
                "離線也能用；同一份 golden 在 MicroPython 也要全綠",
        "tag": "step4",
        "optional": False,
        "ai": {
            "prompt": """\
【任務】
先做 spike：在 Node 裡用 MicroPython WebAssembly 版跑 golden，確認浮點數是雙精度，再決定採用 MicroPython 或退回 Pyodide
通過後做 PWA 殼：畫面先顯示，Python 在 Web Worker 背景載入，就緒前的計算請求排隊
【介面】
- npm 套件 @micropython/micropython-webassembly-pyscript 鎖定確切版本，執行環境複製到 web/vendor/，不靠 CDN
- python tools/build_web.py 把 engine/ 複製到 web/py/；--check 只檢查是否過期
- Worker 訊息：送 {id, request}，回 {id, response} 或 {id, error}；載入完成送 {type: "ready", ms}
- 畫面 #py-status 顯示載入中／就緒／錯誤
- npm run test:mpy 在 MicroPython 跑全部 golden 與錯誤案例；web/selftest.html 在瀏覽器重跑
- web/sw.js 的 APP_SHELL 列出所有殼檔案，python tools/check_shell.py 檢查
【限制】
- 安裝 npm 套件前先問我，並先確認專案資料夾有 package.json
- CPython 與 MicroPython 同一題相對誤差 > 1e-9 即失敗；錯誤路徑也要比，不只比成功案例
- 殼檔案改了 Service Worker 要能更新，不能讓使用者卡在舊版
【驗收】
- npm run test:mpy 全綠、node tools/check_worker.mjs 通過
- 瀏覽器開 selftest.html 全部 PASS；停掉伺服器重新整理仍能計算
- 回報 Pyodide 與 MicroPython 的下載大小與殼顯示、Python 就緒時間""",
            "bad_prompt": "把 Python 引擎放到網頁上跑",
            "bad_result": "推測：AI 會選最常見的 Pyodide 從 CDN 載入（約 5.3 MB），在主執行緒載入讓畫面卡住，"
                          "也不會在 MicroPython 重跑測試，CPython 能過的程式到瀏覽器才壞",
            "bad_evidence": "實際踩過：spike 發現 Exception.__init__(self, msg) 在 MicroPython 會擲 AttributeError，"
                            "所有錯誤訊息都變成「內部錯誤」；json.dumps 不支援 allow_nan、也沒有 RecursionError，"
                            "CPython 測試全過也抓不到（DEVLOG Task 18、Task 16 修正輪 1）",
            "expected": "web/ PWA 殼（index.html、manifest、sw.js）、web/vendor/ 鎖定版 MicroPython、"
                        "py-worker.js 與 py-client.js、selftest.html；MicroPython golden 51/51 全綠",
            "verify": [
                "npm ci",
                "python tools/build_web.py",
                "npm run test:mpy",
                "node tools/check_worker.mjs",
                "python tools/check_shell.py",
                "node tools/spike_float.mjs",
                "python -m http.server 8765 -d web",
                "瀏覽器開 http://localhost:8765/selftest.html 應全部 PASS",
            ],
            "pitfalls": [
                "實測下載大小：Pyodide 0.28.3 傳輸約 5.3 MB、MicroPython 1.29.0 約 0.23 MB，約小 23 倍；"
                "本機載入加 import 引擎約 65 ms（DEVLOG 規格修訂、Task 18）",
                "npm 會往上找 package.json：BACalc 還沒有 package.json 時，npm install 裝到上一層 Tien Research 資料夾，"
                "先建 package.json 再裝（DEVLOG Task 18）",
                "Windows 的 python http.server 把 .mjs 回成 text/plain，瀏覽器拒絕載入 module，"
                "改用位元組相同的 micropython.js（DEVLOG Task 20）",
                "core.autocrlf=true 會改動 wasm 等鎖定檔的位元組，加 .gitattributes 的 web/vendor/* -text（DEVLOG Task 20）",
                "Service Worker 快取舊檔：改了程式重新整理還是舊版，改成用殼檔案內容雜湊 SHELL_HASH 觸發更新"
                "（progress ledger Task 20）",
                "計畫的判定式寫錯：1e300*10 在雙精度仍是有限值，改成 1e308*10 == inf（progress ledger Task 18）",
                "MicroPython 的 '%.15g' 遇到精確中點採 half-up（CPython 是 half-even），≥1e11 的值末位偶爾差 1，"
                "所以雙環境比數值不比字串；金額上限因此訂為 1e13 元（progress ledger Task 18）",
            ],
        },
        "emba": {
            "prompt": """\
【任務】
請把計算機做成手機也能用的網頁 App：打開就先看到畫面，計算功能在背景準備，沒網路也能用
【介面】
畫面上方顯示「載入中／就緒」；另外做一個自我測試頁，把所有例題重算一次，顯示通過或失敗
【限制】
- 選手機載入比較快的方案，告訴我兩種方案的下載大小與資料來源
- 要安裝任何東西前先問我
- 還沒準備好就按計算，不能出錯，要等準備好自動算出來
【驗收】
請幫我把 App 在電腦上開起來，告訴我網址，我要自己試算""",
            "expected": "瀏覽器打開 App，狀態顯示就緒；自我測試頁全部通過；"
                        "AI 說明 Pyodide 約 5.3 MB、MicroPython 約 0.23 MB，所以選 MicroPython",
            "verify": [
                "打開自我測試頁 selftest.html，每一題都應顯示 PASS",
                "App 利率換算：名目利率 12、每年複利 12 次，有效利率應為 12.68；"
                "Excel =EFFECT(0.12,12) 得 0.126825",
                "BA II Plus：[2ND][ICONV]，NOM=12 [ENTER]，[↓][↓] C/Y=12 [ENTER]，[↑] 到 EFF 按 [CPT]，應得 12.68",
                "請 AI 停掉伺服器（模擬沒網路）後重新整理，畫面仍在、仍能算出 12.68",
            ],
            "pitfalls": [
                "改了 App 重新整理還是舊畫面：這是瀏覽器快取（Service Worker），本專案開發時遇過多次，"
                "要請 AI 做好自動更新，不是叫你一直清快取",
                "AI 第一次安裝套件時裝錯資料夾（裝到上一層），所以「安裝前先問我」這條規則很重要",
            ],
            "start_tag": "step3",
        },
    },
    # ------------------------------------------------------------------ step5
    {
        "id": "step5",
        "title": "人性化 UI：每張工作表的畫面",
        "goal": "手機與電腦都好操作：留一格空白就算、錯誤標出欄位、說明附真實範例、表格可匯出 CSV",
        "tag": "step5",
        "optional": False,
        "ai": {
            "prompt": """\
【任務】
做全部工作表的人性化畫面：TVM、AMORT、CF、ICONV、STAT、BOND、DEPR、商業、日期、計算機與紙帶、記憶、設定
【介面】
- 欄位 id 固定為 f-<工作表>-<鍵>，例如 f-tvm-PMT；錯誤時用 bridge 回傳的 field 把該欄標紅
- 數字解析放 web/js/input.js（千分位、全形數字、5 或 5%），規則與 engine 的解析一致
- 攤還表、折舊表可匯出 CSV，儲存格是 Excel 能加總的純數字（不含千分位）
- 新增的 web 檔案都列進 web/sw.js 的 APP_SHELL
【限制】
- 留一格空白就算那一格，算完標示「求出」的格子
- 請求進行中改了輸入，舊回應不可顯示（用世代編號 generation 擋）
- 說明文字裡的範例數字必須等於引擎實際算出的 display，用測試鎖住
- 手機 375px 寬單欄加底部分頁列，電腦左側選單
【驗收】
- node --test "tests/js/*.test.mjs" 與 python -m pytest -q 全過
- 在瀏覽器實際操作每張工作表一次，回報 TVM 與 CF 畫面上的數字""",
            "bad_prompt": "幫每個功能做一個好看的畫面",
            "bad_result": "推測：畫面好看，但說明裡的範例數字是 AI 猜的、CSV 匯出畫面上的字串（含千分位）、"
                          "快速連按時舊結果蓋掉新結果",
            "bad_evidence": "實際踩過：說明文字的範例是猜的，e2e 抓到 IRR 寫 13.7 實際 13.78、"
                            "MIRR 寫 11.9 實際 11.83（DEVLOG Task 21）；"
                            "CSV 原本匯出顯示字串，Excel 無法加總，改成純數字（progress ledger Task 22）",
            "expected": "web/js/views/ 下各工作表畫面、input.js、csv.js、tape.js、memstore.js；"
                        "JS 單元測試與 pytest 全過",
            "verify": [
                'node --test "tests/js/*.test.mjs"',
                "npm run test:js",
                "python -m pytest tests/test_web_sheets.py -q",
                "python tools/check_shell.py",
            ],
            "pitfalls": [
                "node --test tests/js（給目錄）在 Node 22 找不到模組，要傳 glob 字串 \"tests/js/*.test.mjs\""
                "（DEVLOG Task 21）",
                "求出一格再求另一格時，舊的「求出」標記沒清，下次出現兩格空白（DEVLOG Task 21 修正輪 1）",
                "STAT 預測錯誤標到資料清單欄而不是 X' 欄：field 對應要以 action 優先（progress ledger Task 21 修正輪 2）",
                "EU 數字格式下 599.55 會判格式錯誤（點是千分位），要輸入 599,55（DEVLOG Task 22 修正輪 1）",
                "貼上表格：單欄但行尾有 tab 被誤判成多欄（DEVLOG Task 23）",
                "memstore.store(i, undefined) 因預設參數 x = 0 被存成 0，測試抓到（DEVLOG Task 24）",
                "CHAIN 模式下 -2^2 = 4（和 AOS 不同），要在畫面與教材說明（progress ledger Task 14）",
            ],
        },
        "emba": {
            "prompt": """\
【任務】
請把每個功能的畫面做得好用：欄位旁有說明和範例，算出來的格子要標出來，錯誤要指出是哪一格
【介面】
- 手機上一欄一欄往下排、下方有分頁；電腦左邊是選單
- 攤還表、折舊表可以下載成 Excel 能開的 CSV
【限制】
- 說明裡的範例數字必須是 App 真的算出來的，不能用猜的
- 下載的 CSV 數字要能在 Excel 直接加總
- 輸入 5 或 5% 都當成 5%；可以打千分位
【驗收】
我會用三題例題在 App 上操作，數字要和 Excel 一樣""",
            "expected": "每張工作表都能操作，錯誤時標紅該欄並說明原因",
            "verify": [
                "App 攤還：房貸例題 P1=1、P2=12，利息 INT 應為 -17,899.78；"
                "Excel =CUMIPMT(0.005,360,300000,1,12,0) 得 -17,899.78",
                "BA II Plus：做完 TVM 房貸後 [2ND][AMORT]，P1=1 [ENTER] [↓] P2=12 [ENTER]，"
                "[↓] BAL=296,315.96、[↓] PRN=-3,684.04、[↓] INT=-17,899.78",
                "App 債券：交割日 2026-06-12、到期日 2036-01-01、票面 7%、殖利率 8%、半年付息、ACT，價格應為 93.40；"
                "Excel =PRICE(DATE(2026,6,12),DATE(2036,1,1),0.07,0.08,100,2,1) 得 93.40",
                "下載攤還表 CSV 用 Excel 開啟，數字欄可以直接 =SUM，不會變成文字（儲存格左上角沒有綠色三角形）",
            ],
            "pitfalls": [
                "說明裡的範例數字曾經是 AI 猜的（IRR 寫 13.7，實際 13.78），所以要求「範例必須真的算出來」",
                "CSV 曾經匯出畫面上帶千分位的文字，Excel 不能加總，後來改成純數字",
                "設定成歐洲數字格式時小數點是逗號（599,55），打 599.55 會被判格式錯誤",
            ],
            "start_tag": "step4",
        },
    },
    # ------------------------------------------------------------------ step6
    {
        "id": "step6",
        "title": "本機儲存與 JSON 匯出入",
        "goal": "設定、紙帶、記憶、情境存在手機本機（IndexedDB），可匯出 JSON 備份並匯入還原",
        "tag": "step6",
        "optional": False,
        "ai": {
            "prompt": """\
【任務】
加上本機儲存與備份：設定、紙帶、記憶、情境存在 IndexedDB；可匯出 JSON 備份，匯入時選擇取代或合併
【介面】
- 匯出檔名 bacalc-backup-YYYYMMDD.json
  內容 {"app", "schema", "exported_at", "data": {"settings", "scenarios", "tape", "memory"}}
- 匯入先驗證格式，錯誤回中文原因，且不寫入任何資料
- 純函式放 web/js/storage/backup.js，IndexedDB 存取放 web/js/storage/idb.js
【限制】
- 資料只存本機，不送到任何伺服器
- 匯入資料要清理（設定值範圍、表格大小、字串長度），壞檔不能弄壞現有資料
- 情境要連表格內容（CF、STAT）一起存
- 關閉頁面前把還沒寫入的紙帶 flush
【驗收】
- node --test tests/js/backup.test.mjs tests/js/idb.test.mjs 全過（用假的 IndexedDB）
- 來回測試：匯出、清空、匯入，所有值相同""",
            "bad_prompt": "加一個存檔功能",
            "bad_result": "推測：AI 可能用 localStorage 只存目前畫面、沒有匯出入；匯入不驗證格式，壞檔直接覆蓋現有資料",
            "bad_evidence": "實際踩過：情境儲存一開始沒存 CF、STAT 的表格內容，載入後舊表格和新的 CF0、I 混在一起，"
                            "看起來像正常結果（progress ledger Task 25 審查、DEVLOG Task 25 修正輪 1）",
            "expected": "web/js/storage/ 下 idb.js、backup.js、persist.js 與情境列；JSON 匯出入來回一致",
            "verify": [
                "node --test tests/js/backup.test.mjs tests/js/idb.test.mjs",
                'node --test "tests/js/*.test.mjs"',
                "python -m pytest -q",
            ],
            "pitfalls": [
                "情境沒存表格內容：CF、STAT 載入後舊表格與新輸入混在一起（DEVLOG Task 25 修正輪 1）",
                "同一份備份匯入兩次紙帶加倍，合併時去除完全相同的項目（DEVLOG Task 25）",
                "瀏覽器模組快取：第一次驗證載到舊的 grid.js，看起來像新程式錯了，強制重新載入才正確"
                "（DEVLOG Task 25 修正輪 1）",
                "測試自己算錯時區（測試錯、實作對）：先懷疑測試再改程式（DEVLOG Task 25）",
                "搬家（舊鍵改存 IndexedDB）要在 IndexedDB 真的寫入成功後才刪舊資料（DEVLOG Task 25 修正輪 1）",
            ],
        },
        "emba": {
            "prompt": """\
【任務】
請讓 App 記住我的資料：關掉再打開，設定、計算紀錄、記憶值都還在；還要能匯出備份檔、再匯入回來
【介面】
設定頁有「匯出 JSON」和「匯入 JSON」兩個按鈕；匯入時讓我選「取代」或「合併」
【限制】
- 資料只存在我的裝置，不上傳
- 匯入壞掉的檔案時要告訴我哪裡不對，不能弄壞現有資料
【驗收】
我會匯出、清空、再匯入，檢查數字一樣""",
            "expected": "匯出得到 bacalc-backup-日期.json；清空後匯入，所有值恢復",
            "verify": [
                "TVM 算出房貸 PMT -1,798.65 後存成情境，匯出 JSON、清空資料、再匯入，"
                "載入情境應仍是 -1,798.65（" + _EXCEL_PMT + "）",
                "記憶 M1 存 1798.65，關掉瀏覽器再打開，M1 仍為 1,798.65",
                "用記事本把備份檔改壞（刪掉一個大括號）再匯入，應出現中文錯誤原因，原有資料不變",
            ],
            "pitfalls": [
                "情境曾經只存上方欄位、沒存現金流表格，載入後新舊資料混在一起；驗收時要整頁比對",
                "同一份備份匯入兩次，紙帶紀錄曾經變兩倍，後來合併時會去掉重複",
            ],
            "start_tag": "step5",
        },
    },
    # ------------------------------------------------------------------ step7
    {
        "id": "step7",
        "title": "Google Drive 同步（選用，作者未實測）",
        "goal": "使用者自己申請 OAuth Client ID 後，可把備份手動上傳到 Drive 的 App 專屬資料夾；預設關閉\n"
                "選用，作者未實測，沒有 step7 tag",
        "tag": None,
        "optional": True,
        "ai": {
            "prompt": """\
【任務】
加上選用的 Google Drive 同步：預設關閉，使用者在設定頁填自己的 OAuth Client ID 後，才能手動上傳／下載備份
【介面】
- web/js/storage/gdrive.js；權限範圍只用 https://www.googleapis.com/auth/drive.appdata（App 專屬隱藏資料夾）
- 上傳內容與 step6 的 JSON 備份格式相同
- 申請步驟寫成 docs/google-oauth-setup.md 並轉成 HTML
【限制】
- Client ID 存本機，不寫死在程式碼
- 雲端比本機新時不自動覆蓋，顯示雙方時間讓使用者選
- 本機有沒有改用內容雜湊判斷，不用時間戳
【驗收】
- node --test tests/js/gdrive.test.mjs 全過（假的 Drive API）
- 手動：用自己的 Client ID 上傳一次，在另一個瀏覽器下載，值相同""",
            "bad_prompt": "幫我把資料同步到 Google Drive",
            "bad_result": "推測：AI 可能要求完整 Drive 權限、把 Client ID 寫死在程式碼、雲端較新時直接覆蓋本機",
            "bad_evidence": "實際踩過：原本用時間戳判斷本機有沒有改，記憶與設定的修改看不出來，"
                            "改成記錄上次同步的內容雜湊（progress ledger Task 26）",
            "expected": "gdrive.js、設定頁同步區、docs/google-oauth-setup.html；預設關閉",
            "verify": [
                "node --test tests/js/gdrive.test.mjs",
                "python tools/md2html.py docs/google-oauth-setup.md",
                "照 docs/google-oauth-setup.html 申請 Client ID 後手動上傳與下載一次",
            ],
            "pitfalls": [
                "作者沒有用真的 Client ID 實測，所以沒打 step7 tag，課堂上當作選用（progress ledger Task 26）",
                "時間戳判斷本機變更會漏掉記憶與設定的修改，改用內容雜湊（progress ledger Task 26）",
                "說明頁連到 GitHub main 分支的檔案，合併到 main 之前會 404（progress ledger Task 26）",
            ],
        },
        "emba": {
            "prompt": """\
【任務】
（選用）如果我想把備份放到 Google Drive，請說明要做哪些設定，並讓 App 可以手動上傳和下載
【介面】
設定頁有「Google Drive 同步」區塊，預設關閉
【限制】
- 只能存取這個 App 自己的資料夾，看不到我其他檔案
- 雲端和手機上的資料不一樣時，先問我要用哪一份
【驗收】
用白話告訴我申請步驟，以及授權時會要求哪些權限""",
            "expected": "AI 說明在 Google Cloud Console 申請 OAuth Client ID 的步驟，"
                        "以及只要求「App 專屬資料」權限；不想申請的人改用 JSON 匯出存到任何雲端資料夾",
            "verify": [
                "照 docs/google-oauth-setup.html 核對 AI 的說明：授權畫面只應要求 App 專屬資料的權限",
                "上傳後在另一台裝置下載，TVM 情境的 PMT 仍為 -1,798.65（" + _EXCEL_PMT + "）",
            ],
            "pitfalls": [
                "作者沒有用真的 Client ID 實測過，這一步請當作延伸閱讀",
                "曾經只看時間判斷有沒有改，改了記憶值卻被當成沒改，後來改成比對內容",
            ],
            "start_tag": "step6",
        },
    },
    # ------------------------------------------------------------------ step8
    {
        "id": "step8",
        "title": "自我驗證 Loop 寫成 Skill",
        "goal": "一個指令跑完全部驗證並產生 HTML log，再寫成 Skill，讓 AI 每次改完都自己跑「改、驗、讀 log、修」",
        "tag": "step8",
        "optional": False,
        "ai": {
            "prompt": """\
【任務】
把所有驗證串成一個指令，再寫成 Claude Code 的 Skill；之後每次改完程式，你都自己跑這個 Loop：改、驗證、讀 log、修
【介面】
- python tools/verify_all.py：依序跑 git 乾淨檢查、check_portable、pytest、build_web --check、check_shell、JS 單元測試、check_worker、test:mpy、mutate
  --quick 略過 mutate；任一項失敗 exit 1
- 產生 logs/verify-YYYYMMDD-HHMM.html：commit hash、每項 PASS/FAIL、耗時、失敗輸出末 60 行
- Skill 放 .claude/skills/verify-bacalc/SKILL.md：何時用、怎麼跑、怎麼看 log、規則
- UI 的手動檢查表放 e2e/checklist.md
【限制】
- git 不乾淨就拒絕執行；--allow-dirty 只供示範，log 標示 DIRTY
- Skill 要寫明：絕不改 golden、不放寬容差、不刪或改弱測試來讓驗證通過
- 單項失敗仍跑完其餘項目
【驗收】
- 故意改壞 engine/tvm.py 的一個符號，用 --allow-dirty 跑，要看到 FAIL；還原後完整跑一次全 PASS
- 開新對話說「我改完了，幫我驗證」，你要自動使用 verify-bacalc skill""",
            "bad_prompt": "寫個腳本跑全部測試",
            "bad_result": "推測：腳本遇到第一個失敗就停、沒有 log 也沒有 commit hash；"
                          "驗證失敗時 AI 可能直接改測試或放寬容差讓它變綠",
            "bad_evidence": "實際踩過：完整驗證約 2 分 22 秒（mutate 約 102 秒），超過工具 2 分鐘逾時，"
                            "要改在背景執行再讀結果（DEVLOG Task 21 修正輪 1、Task 27，logs/verify-20261020-2339.html）",
            "expected": "tools/verify_all.py、.claude/skills/verify-bacalc/SKILL.md、e2e/checklist.md；"
                        "logs/ 下有全 PASS 的驗證 log",
            "verify": [
                "python tools/verify_all.py --quick",
                "python tools/verify_all.py",
                "python tools/verify_all.py --allow-dirty",
                "cat .claude/skills/verify-bacalc/SKILL.md",
                "照 e2e/checklist.md 在瀏覽器逐項勾選",
            ],
            "pitfalls": [
                "pytest.ini 的 addopts 已含 -q，再加 -q 會吃掉最後的 passed 摘要，驗證時改用 -o addopts 覆寫"
                "（DEVLOG Task 21）",
                "示範弄壞 engine 時，build_web --check 與 test:mpy 也會一起失敗（web/py 是舊的正確建置），屬預期"
                "（DEVLOG Task 27）",
                "超過 2 分鐘的工具逾時：完整驗證改在背景跑，跑完再讀 log（DEVLOG Task 21、Task 27）",
                "Git Bash 顯示中文輸出會亂碼（cp950），log 檔本身是 UTF-8；需要時設 PYTHONIOENCODING=utf-8"
                "（DEVLOG Task 17、Task 27）",
                "e2e 檢查表有幾項預期值是公式推算、未經瀏覽器實測，要在表上註明（DEVLOG Task 27）",
            ],
        },
        "emba": {
            "prompt": """\
【任務】
請做一個「一鍵檢查」：一個指令把所有測試跑完，產生我看得懂的報告網頁，並把這個流程存成你以後會自動使用的技能 Skill
【介面】
報告放在 logs 資料夾，最上面寫總結：全部通過，或哪一項失敗
【限制】
- 測試沒過時只能修程式，不能改答案或放寬標準
- 報告要記錄這是哪一個版本
【驗收】
跑一次給我看報告；再故意改壞一個公式跑一次，讓我看到失敗的樣子，然後還原""",
            "expected": "logs/verify-日期時間.html 顯示全部 PASS；故意改壞時對應項目 FAIL",
            "verify": [
                "打開 logs 資料夾裡最新的報告，總結應為全部 PASS，並記錄版本編號 commit",
                "App 折舊：成本 10,000、殘值 1,000、5 年直線法，第 1 年折舊 1,800.00；Excel =SLN(10000,1000,5) 得 1,800",
                "同一題第 2 年改用 200% 定率遞減，App 應得 2,400.00；Excel =DDB(10000,1000,5,2,2) 得 2,400",
                "BA II Plus：[2ND][DEPR] 選 SL，依序輸入 LIF=5、M01=1、YR=1、CST=10000、SAL=1000，[↓] 到 DEP 應為 1,800",
            ],
            "pitfalls": [
                "完整檢查約要 2 分多鐘（故意改壞公式的突變測試最慢），要等它跑完",
                "故意改壞一個公式時不只一項會失敗（網頁版也跟著不一致），這是正常的",
            ],
            "start_tag": "step6",
        },
    },
    # ------------------------------------------------------------------ step9
    {
        "id": "step9",
        "title": "部署到 GitHub Pages、安裝到手機",
        "goal": "push 到 main 時自動測試，全過才部署；手機安裝成 App，飛航模式也能算",
        "tag": "step9",
        "optional": False,
        "ai": {
            "prompt": """\
【任務】
用 GitHub Actions 部署到 GitHub Pages：push 到 main 時先跑測試，全過才部署 web/
部署後在手機安裝，開飛航模式操作
【介面】
- .github/workflows/pages.yml：test job（pytest、check_portable、build_web、check_shell、test:mpy、JS 測試、check_worker），
  通過後 deploy job（upload-pages-artifact 上傳 web/、deploy-pages）
- 線上網址寫進 README.md 與 OAuth 授權來源說明
- README 寫 Android Chrome 與 iPhone Safari 的安裝步驟
【限制】
- 推送 GitHub 前先問我；repo 名稱與 public／private 由我決定
- Actions 版本要查證存在並附查證方式，不憑記憶
- CI 不跑突變測試（太慢），README 註明
- web/py 被 git 忽略，CI 要先跑 build_web.py
【驗收】
- GitHub Actions 兩個 job 都綠，線上 selftest.html 全部 PASS
- 手機安裝後開飛航模式，TVM 與 CF 仍能計算；回報殼顯示與 Python 就緒時間""",
            "bad_prompt": "幫我把網站放上網",
            "bad_result": "推測：AI 可能沒先問就 push、用「從分支部署」把整個 repo 公開，"
                          "沒有測試就上線，web/py 沒建置導致線上無法計算",
            "bad_evidence": "實際踩過：計畫寫的 Actions 版本比實際最新的舊，實作時查 releases 頁才改用 checkout v7、"
                            "deploy-pages v5 等，再用 git ls-remote 確認 tag 存在（DEVLOG Task 28、progress ledger Task 28）",
            "expected": ".github/workflows/pages.yml、README.md 安裝說明；線上網址可開、selftest 全綠；手機飛航模式可用",
            "verify": [
                "python -m pytest -q",
                "python tools/check_portable.py engine",
                "npm run test:mpy",
                "gh run list --workflow pages.yml --limit 1",
                "開啟 https://fctien.github.io/Statistics-Accouting-Calculator/selftest.html 應全部 PASS",
            ],
            "pitfalls": [
                "Pages 網址路徑區分大小寫：本專案是 /Statistics-Accouting-Calculator/（保留使用者的拼法），"
                "大小寫打錯就 404（progress ledger 裁定；作者另一個 PWA 專案實際踩過）",
                "本機無法跑真正的 GitHub Actions：用 git checkout-index 匯出 LF 的乾淨副本，"
                "依序跑 workflow 的指令模擬 CI（DEVLOG Task 28）",
                "手機實機安裝與飛航模式由作者親自測，測完才打 step9 tag（DEVLOG Task 28 待辦）",
            ],
        },
        "emba": {
            "prompt": """\
【任務】
請把 App 放到網路上，讓我用手機打開並安裝到主畫面，沒網路時也能用
【介面】
給我一個網址；說明文件寫 Android 與 iPhone 的安裝步驟
【限制】
- 上傳到 GitHub 之前先問我
- 每次更新都要先自動測試，通過才上線
【驗收】
我會在手機安裝，開飛航模式算一題房貸和一題 NPV""",
            "expected": "得到線上網址；手機安裝後，飛航模式仍可計算",
            "verify": [
                "手機開 https://fctien.github.io/Statistics-Accouting-Calculator/ ，"
                "Android 用 Chrome 選單「安裝應用程式」，iPhone 用 Safari 分享鈕「加入主畫面」",
                "開飛航模式，TVM 房貸 PMT 應為 -1,798.65（" + _EXCEL_PMT + "）",
                "飛航模式下 CF：-10000、3000、4200、6800、-1500、I=10，NPV 應為 282.77（" + _EXCEL_NPV + "）",
                "用 BA II Plus 算同一題 NPV，App、Excel、計算機三者應一致",
            ],
            "pitfalls": [
                "網址大小寫要完全一樣，打錯會出現 404",
                "第一次打開要有網路，等畫面顯示 Python 就緒後再開飛航模式",
                "iPhone 必須用 Safari 才能加入主畫面；太久沒開可能清掉本機資料，記得定期匯出備份",
            ],
            "start_tag": "step8",
        },
    },
]
