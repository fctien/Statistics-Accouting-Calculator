"""使用說明影片的單一來源（single source）：SEGMENTS 定義每一段的旁白、錄影動作與預期畫面。

每段欄位：
    id         段落代號（檔名 seg-XX 依順序編號）
    title      字卡標題（段落開始時顯示 2 秒）
    start      錄影開始前先載入的路由（#後面的部分）；載入與引擎就緒的時間會被剪掉
    narration  旁白（給 Yating 語音念，也直接當字幕）；英文縮寫寫成中文讀法，單一字母可保留
    actions    錄影步驟（teaching/video/record.mjs 執行），每步恰一個動詞：
                 goto 路由｜click 選擇器｜fill 選擇器＋value（逐字輸入）｜select 選擇器＋value
                 （option 的 value，找不到時比對 option 文字開頭）｜press 鍵｜wait 毫秒｜
                 highlight 選擇器（框出 1.5 秒）｜card 字卡（title、lines、url）｜uncard｜
                 check 選擇器＋text（中途核對）
    expect     段落錄完後畫面上必須出現的文字：{"selector", "text"}（標 "at": "check" 者在錄影中途由
               同內容的 check 動作核對，因為之後換頁就不在畫面上），
               數值項附 "engine"（bridge 請求＋key）由 tests/test_video_script.py 實算核對；
               純畫面文字（標題、網址、結論字樣）標 "screen": True
選擇器（selector）使用 Playwright 語法（CSS，可加 :text-is()）。
執行 `python teaching/video/script.py out.json` 輸出 JSON 給錄影腳本。
"""
import json
import sys

APP_URL = "https://fctien.github.io/Statistics-Accouting-Calculator/"

# TVM 範例（貸款 10 萬、年利率 6%、30 年月付）：引擎全精度 PMT，供攤還核對
_TVM = {"N": 360, "IY": 6, "PV": 100000, "FV": 0, "PY": 12, "CY": 12, "BGN": False}
_PMT_FULL = -599.5505251527442

# 計算按鈕（工作表內文字為「計算」的主要按鈕）
CALC = "#sheet button:text-is('計算')"
CLEAR = "#sheet button:text-is('清除')"


def _fill_tvm():
    """TVM 範例的輸入步驟（PMT 留空）。"""
    return [{"fill": "#f-tvm-" + k, "value": str(v)}
            for k, v in (("N", 360), ("IY", 6), ("PV", 100000), ("FV", 0), ("PY", 12), ("CY", 12))]


def _key(label):
    """科學計算機的按鍵（以按鍵文字找）。"""
    return {"click": "#sheet button:text-is('%s')" % label}


SEGMENTS = [
    {
        "id": "intro",
        "title": "商用財務計算機 BACalc 使用說明",
        "start": "acct/tvm",
        "narration": (
            "歡迎觀看商用財務計算機的使用說明。這個計算機仿照德州儀器的財務計算機設計，"
            "計算核心用派森語言撰寫，直接在瀏覽器裡執行，不需要安裝任何程式，也可以離線使用。"
            "線上網址顯示在畫面上，網址的大小寫要完全相同。"
            "它的設計原則是：算不出來就說明原因，絕不顯示看起來正常但錯誤的數字。"
            "接下來大約十分鐘，我們會依序介紹工程、統計、會計三大頁面，以及情境儲存和設定。"
        ),
        "actions": [
            {"card": "intro", "title": "BACalc 商用財務計算機", "lines": [
                "仿 TI BA II Plus Professional 的財務／會計／統計計算機",
                "Python 計算引擎在瀏覽器執行（MicroPython WebAssembly）",
                "免安裝、可離線、資料只存本機"], "url": APP_URL},
            {"wait": 6000},
            {"check": "#video-card", "text": "fctien.github.io"},
            {"uncard": True},
            {"highlight": "#page-tabs"},
        ],
        "expect": [
            {"selector": "#py-status", "text": "就緒", "screen": True},
            {"selector": "#page-tabs", "text": "會計", "screen": True},
        ],
    },
    {
        "id": "install",
        "title": "安裝到手機",
        "start": "acct/tvm",
        "narration": (
            "這個計算機是漸進式網頁應用程式，可以安裝到手機的主畫面，像一般應用程式一樣開啟。"
            "第一次請連上網路開啟網址，等右上角的狀態顯示就緒。"
            "安卓手機請用瀏覽器右上角的選單，選擇安裝應用程式，或加到主畫面。"
            "蘋果手機必須使用內建的瀏覽器，按下方的分享按鈕，再選擇加入主畫面。"
            "安裝並載入一次之後，開啟飛航模式也能計算。"
            "資料只存在這台裝置上，重要的資料請定期匯出備份。"
        ),
        "actions": [
            {"highlight": "#py-status"},
            {"card": "install", "title": "安裝到手機（PWA）", "lines": [
                "第一次需連網開啟網址，等右上角顯示「就緒」",
                "Android（Chrome）：右上角選單 ⋮ →「安裝應用程式」或「加到主畫面」",
                "iPhone／iPad（Safari）：分享鈕 →「加入主畫面」",
                "安裝並載入一次後，飛航模式也能使用",
                "資料只存本機（IndexedDB），請定期「匯出 JSON」備份"], "url": APP_URL},
            {"wait": 9000},
            {"check": "#video-card", "text": "加入主畫面"},
            {"uncard": True},
            {"highlight": "#py-status"},
        ],
        "expect": [{"selector": "#py-status", "text": "就緒", "screen": True}],
    },
    {
        "id": "nav",
        "title": "三大頁面導覽",
        "start": "acct/tvm",
        "narration": (
            "畫面上方有三個頁籤，分別是工程、統計和會計，右邊是設定。"
            "左側列出這一頁的功能，工程有三項，統計有四項，會計有十一項。"
            "網址會跟著改變，例如會計頁的貨幣時間價值，可以直接加入書籤。"
            "系統也會記住每一頁上次停留的位置，切換頁籤時直接回到那裡。"
            "在手機上，頁籤列會固定在畫面底部，功能清單則變成上方可以左右滑動的按鈕。"
        ),
        "actions": [
            {"highlight": "#page-tabs"},
            {"goto": "eng/calc"},
            {"highlight": "#side-nav"},
            {"goto": "stat/reg"},
            {"highlight": "#side-nav"},
            {"goto": "acct/tvm"},
            {"highlight": "#side-nav"},
            {"highlight": "#settings-link"},
        ],
        "expect": [
            {"selector": "#sheet-title", "text": "TVM", "screen": True},
            {"selector": "#side-nav", "text": "DATE 日期", "screen": True},
        ],
    },
    {
        "id": "eng-calc",
        "title": "工程｜科學計算機",
        "start": "eng/calc",
        "narration": (
            "先看工程頁的科學計算機。可以直接輸入算式，也可以按畫面上的按鍵。"
            "我們依序按正弦、三、零、右括號，再按等號。在角度模式下，正弦三十度等於零點五。"
            "每次計算都會記在下方的紙帶，點一下就能把算式帶回輸入框。"
            "按角度鍵切換成弧度後，舊的結果會標示是在角度模式算的，提醒你重新計算，避免看錯單位。"
            "右邊還有十個記憶格和累加功能，和實體計算機的用法相同。"
        ),
        "actions": [
            {"highlight": "#calc-expr"},
            _key("sin"), _key("3"), _key("0"), _key(")"),
            {"click": "#calc-eq"},
            {"highlight": "#calc-result"},
            {"highlight": "#calc-tape-list"},
            {"click": "#calc-angle"},
            {"highlight": "#calc-status"},
            {"click": "#calc-angle"},
            {"click": "#calc-eq"},
            {"highlight": "#calc-result"},
        ],
        "expect": [
            {"selector": "#calc-result", "text": "0.50",
             "engine": {"sheet": "calc", "action": "eval", "inputs": {"EXPR": "sin(30)"},
                        "settings": {"angle": "DEG"}, "key": "value"}},
            {"selector": "#calc-mode", "text": "DEG", "screen": True},
        ],
    },
    {
        "id": "eng-units-base",
        "title": "工程｜單位換算與進位轉換",
        "start": "eng/units",
        "narration": (
            "單位換算可以在長度、質量、溫度、壓力等類別之間轉換。"
            "選長度，從英里換到公里，輸入一，立刻得到一點六一公里。"
            "進位轉換頁在八位元無號模式下，十進位輸入兩百五十五，"
            "二進位是八個一，八進位是三七七，十六進位是 F F。"
            "下方的位元運算，輸入十二和十，選擇及運算，結果是八，二進位是零零零零一零零零。"
        ),
        "actions": [
            {"select": "#u-cat", "value": "length"},
            {"select": "#u-from", "value": "mi"},
            {"select": "#u-to", "value": "km"},
            {"fill": "#u-value", "value": "1"},
            {"highlight": "#u-result"},
            {"check": "#u-result", "text": "1.61"},
            {"goto": "eng/base"},
            {"select": "#b-width", "value": "8"},
            {"fill": "#b-DEC", "value": "255"},
            {"highlight": "#b-BIN"},
            {"highlight": "#b-HEX"},
            {"fill": "#b-a", "value": "12"},
            {"select": "#b-op", "value": "AND"},
            {"fill": "#b-b", "value": "10"},
            {"highlight": "#b-r-DEC"},
            {"highlight": "#b-r-BIN"},
        ],
        "expect": [
            {"selector": "#u-result", "text": "1.61", "at": "check",
             "engine": {"sheet": "units", "action": "convert",
                        "inputs": {"VALUE": 1, "FROM": "mi", "TO": "km"}, "key": "value"}},
            {"selector": "#b-HEX", "text": "FF",
             "engine": {"sheet": "base", "action": "convert",
                        "inputs": {"TEXT": "255", "FROM": 10, "WIDTH": 8, "SIGNED": False}, "key": "HEX"}},
            {"selector": "#b-OCT", "text": "377",
             "engine": {"sheet": "base", "action": "convert",
                        "inputs": {"TEXT": "255", "FROM": 10, "WIDTH": 8, "SIGNED": False}, "key": "OCT"}},
            {"selector": "#b-r-DEC", "text": "8",
             "engine": {"sheet": "base", "action": "bitwise",
                        "inputs": {"OP": "AND", "A": "12", "B": "10", "FROM": 10, "WIDTH": 8, "SIGNED": False},
                        "key": "DEC"}},
            {"selector": "#b-r-BIN", "text": "00001000",
             "engine": {"sheet": "base", "action": "bitwise",
                        "inputs": {"OP": "AND", "A": "12", "B": "10", "FROM": 10, "WIDTH": 8, "SIGNED": False},
                        "key": "BIN"}},
        ],
    },
    {
        "id": "stat-desc",
        "title": "統計｜敘述統計",
        "start": "stat/desc",
        "narration": (
            "接著是統計頁。敘述統計可以一次算出平均數、中位數、眾數、四分位數、標準差、偏態和峰度。"
            "在表格輸入八筆資料：二、四、四、四、五、五、七、九，按計算。"
            "平均數是五，中位數四點五，眾數是四，樣本標準差二點一四。"
            "四分位數的算法和試算表的四分位函數相同，方便和試算表對照。"
        ),
        "actions": [
            {"highlight": "#desc-table"},
        ] + [{"fill": "#desc-table-r%dc1" % (i + 1), "value": str(v)}
             for i, v in enumerate([2, 4, 4, 4, 5, 5, 7, 9])] + [
            {"click": CALC},
            {"highlight": "#f-describe-mean"},
            {"highlight": "#f-describe-median"},
            {"highlight": "#desc-modes"},
            {"highlight": "#f-describe-sx"},
            {"highlight": "#f-describe-q1"},
        ],
        "expect": [
            {"selector": "#f-describe-mean", "text": "5.00",
             "engine": {"sheet": "stats", "action": "describe", "inputs": {"X": [2, 4, 4, 4, 5, 5, 7, 9]},
                        "key": "mean"}},
            {"selector": "#f-describe-median", "text": "4.50",
             "engine": {"sheet": "stats", "action": "describe", "inputs": {"X": [2, 4, 4, 4, 5, 5, 7, 9]},
                        "key": "median"}},
            {"selector": "#f-describe-sx", "text": "2.14",
             "engine": {"sheet": "stats", "action": "describe", "inputs": {"X": [2, 4, 4, 4, 5, 5, 7, 9]},
                        "key": "sx"}},
            {"selector": "#f-describe-q1", "text": "4.00",
             "engine": {"sheet": "stats", "action": "describe", "inputs": {"X": [2, 4, 4, 4, 5, 5, 7, 9]},
                        "key": "q1"}},
        ],
    },
    {
        "id": "stat-reg",
        "title": "統計｜迴歸",
        "start": "stat/reg",
        "narration": (
            "迴歸與單變數頁可以做線性、對數、指數和冪次迴歸。"
            "輸入五組資料，X 是一到五，Y 是二、四、五、四、五，選線性模型後按迴歸。"
            "截距是二點二，斜率零點六，相關係數零點七七，平均數和標準差也一起算出來。"
            "在預測欄輸入新的 X 值六，按預測，就得到預測的 Y 值五點八。"
            "如果資料有重複，可以在次數欄填寫出現的次數，不必一筆一筆重複輸入；也可以直接從試算表複製貼上。"
        ),
        "actions": [
            {"fill": "#stat-table-r1c1", "value": "1"}, {"fill": "#stat-table-r1c2", "value": "2"},
            {"fill": "#stat-table-r2c1", "value": "2"}, {"fill": "#stat-table-r2c2", "value": "4"},
            {"fill": "#stat-table-r3c1", "value": "3"}, {"fill": "#stat-table-r3c2", "value": "5"},
            {"fill": "#stat-table-r4c1", "value": "4"}, {"fill": "#stat-table-r4c2", "value": "4"},
            {"fill": "#stat-table-r5c1", "value": "5"}, {"fill": "#stat-table-r5c2", "value": "5"},
            {"select": "#f-stats-model", "value": "LIN"},
            {"click": "#sheet button:text-is('迴歸')"},
            {"highlight": "#f-stats-A"},
            {"highlight": "#f-stats-B"},
            {"highlight": "#f-stats-r"},
            {"fill": "#f-stats-XP", "value": "6"},
            {"click": "#sheet button:text-is('預測')"},
            {"highlight": "#f-stats-YP"},
        ],
        "expect": [
            {"selector": "#f-stats-A", "text": "2.20",
             "engine": {"sheet": "stats", "action": "two_var",
                        "inputs": {"X": [1, 2, 3, 4, 5], "Y": [2, 4, 5, 4, 5], "model": "LIN"}, "key": "a"}},
            {"selector": "#f-stats-B", "text": "0.60",
             "engine": {"sheet": "stats", "action": "two_var",
                        "inputs": {"X": [1, 2, 3, 4, 5], "Y": [2, 4, 5, 4, 5], "model": "LIN"}, "key": "b"}},
            {"selector": "#f-stats-r", "text": "0.77",
             "engine": {"sheet": "stats", "action": "two_var",
                        "inputs": {"X": [1, 2, 3, 4, 5], "Y": [2, 4, 5, 4, 5], "model": "LIN"}, "key": "r"}},
            # 預測用迴歸的全精度 a＝2.2、b＝0.6（engine two_var 的 values）
            {"selector": "#f-stats-YP", "text": "5.80",
             "engine": {"sheet": "stats", "action": "predict",
                        "inputs": {"model": "LIN", "A": 2.2, "B": 0.6, "X": 6}, "key": "y"}},
        ],
    },
    {
        "id": "stat-dist",
        "title": "統計｜機率分配",
        "start": "stat/dist",
        "narration": (
            "機率分配頁支援常態、t、卡方、二項和卜瓦松分配。"
            "選常態分配、累積機率，平均數零、標準差一，x 等於一點九六，按計算。"
            "左尾機率是零點九七五，右尾約百分之二點五，雙尾約百分之五。"
            "機率以十位有效數字顯示，不會被兩位小數吃掉，下方的分配圖用陰影標出左尾的面積。"
            "功能改成反查，輸入機率就能找到臨界值，例如零點九七五對應的就是一點九六。"
        ),
        "actions": [
            {"select": "#f-dist-DIST", "value": "normal"},
            {"select": "#f-dist-FUNC", "value": "cdf"},
            {"fill": "#f-dist-MU", "value": "0"},
            {"fill": "#f-dist-SIGMA", "value": "1"},
            {"fill": "#f-dist-X", "value": "1.96"},
            {"click": CALC},
            {"wait": 1500},
            {"highlight": "#dist-result"},
            {"highlight": "#dist-chart"},
        ],
        "expect": [
            {"selector": "#dist-result", "text": "0.9750021049",
             "engine": {"sheet": "dist", "action": "normal",
                        "inputs": {"FUNC": "cdf", "MU": 0, "SIGMA": 1, "X": 1.96},
                        "settings": {"decimals": None}, "key": "value"}},
            {"selector": "#dist-result", "text": "0.02499789515",
             "engine": {"sheet": "dist", "action": "normal",
                        "inputs": {"FUNC": "cdf", "MU": 0, "SIGMA": 1, "X": 1.96},
                        "settings": {"decimals": None}, "key": "right"}},
            {"selector": "#dist-chart", "text": "陰影", "screen": True},
        ],
    },
    {
        "id": "stat-infer",
        "title": "統計｜信賴區間與檢定",
        "start": "stat/infer",
        "narration": (
            "信賴區間與檢定頁包含 z 與 t 的信賴區間、比例的信賴區間、各種 t 檢定，以及卡方檢定。"
            "選兩樣本 t 檢定，X 組輸入五到九，Y 組輸入三到七，預設不假設兩組變異數相等。"
            "按計算，t 值二點零零，自由度八，p 值零點零八，大於顯著水準零點零五，"
            "所以結論是不拒絕虛無假設。"
        ),
        "actions": [
            {"select": "#f-infer-TYPE", "value": "t2"},
        ] + [a for i in range(5) for a in (
            {"fill": "#infer-table-r%dc1" % (i + 1), "value": str(5 + i)},
            {"fill": "#infer-table-r%dc2" % (i + 1), "value": str(3 + i)})] + [
            {"click": CALC},
            {"highlight": "#infer-hyp"},
            {"highlight": "#infer-result"},
            {"highlight": "#infer-conclusion"},
        ],
        "expect": [
            {"selector": "#infer-result", "text": "2.00",
             "engine": {"sheet": "infer", "action": "t2",
                        "inputs": {"X": [5, 6, 7, 8, 9], "Y": [3, 4, 5, 6, 7], "EQUAL_VAR": False}, "key": "t"}},
            {"selector": "#infer-result", "text": "8.00",
             "engine": {"sheet": "infer", "action": "t2",
                        "inputs": {"X": [5, 6, 7, 8, 9], "Y": [3, 4, 5, 6, 7], "EQUAL_VAR": False}, "key": "df"}},
            {"selector": "#infer-conclusion", "text": "不拒絕 H0", "screen": True},
        ],
    },
    {
        "id": "acct-tvm",
        "title": "會計｜貨幣時間價值與攤還",
        "start": "acct/tvm",
        "narration": (
            "會計頁的貨幣時間價值，可以算房貸、儲蓄和年金。例如貸款十萬元，年利率百分之六，分三十年每月付款。"
            "期數三百六十，每年期數十二，現值十萬元是收到的錢，終值零，每期付款留白，按計算。"
            "每月要付五百九十九點五五元，方向顯示付出。"
            "按帶入攤還，數值會自動帶到攤還頁；再按完整攤還表，列出三百六十期的本金、利息和餘額，"
            "也可以匯出成逗號分隔檔，用試算表開啟。"
        ),
        "actions": _fill_tvm() + [
            {"highlight": "#f-tvm-PMT"},
            {"click": CALC},
            {"highlight": "#f-tvm-PMT"},
            {"check": "#f-tvm-PMT", "text": "599.55"},
            {"click": "#tvm-to-amort"},
            {"highlight": "#f-amort-PMT"},
            {"click": "#sheet button:text-is('完整攤還表')"},
            {"highlight": "#amort-table-box"},
            {"highlight": "#amort-csv"},
            {"click": "#amort-csv"},
        ],
        "expect": [
            {"selector": "#f-tvm-PMT", "text": "599.55", "at": "check",
             "engine": {"sheet": "tvm", "action": "solve", "inputs": _TVM, "key": "PMT"}},
            {"selector": "#f-amort-PMT", "text": "599.55",
             "engine": {"sheet": "tvm", "action": "solve", "inputs": _TVM, "key": "PMT"}},
            {"selector": "#amort-table", "text": "99,900.45",
             "engine": {"sheet": "amort", "action": "range",
                        "inputs": dict(_TVM, PMT=_PMT_FULL, P1=1, P2=1), "key": "BAL"}},
        ],
    },
    {
        "id": "acct-cf",
        "title": "會計｜現金流 NPV 與 IRR",
        "start": "acct/cf",
        "narration": (
            "現金流頁計算淨現值與內部報酬率。期初投入一萬元，方向是付出。"
            "之後四期的現金流分別是三千、四千二、六千八和負一千五，次數都是一。"
            "折現率百分之十，按淨現值，得到兩百八十二點七七元；"
            "再按內部報酬率，得到百分之十一點五二。"
            "同一張表也能算淨終值、修正內部報酬率，以及回收期和折現回收期。"
            "如果現金流的正負號變換超過一次，內部報酬率可能不只一個，系統會提出警告。"
        ),
        "actions": [
            {"fill": "#f-cashflow-CF0", "value": "10000"},
            {"highlight": "#f-cashflow-CF0"},
        ] + [a for i, v in enumerate([3000, 4200, 6800, -1500]) for a in (
            {"fill": "#cf-table-r%dc1" % (i + 1), "value": str(v)},
            {"fill": "#cf-table-r%dc2" % (i + 1), "value": "1"})] + [
            {"fill": "#f-cashflow-I", "value": "10"},
            {"click": "#sheet button:text-is('NPV')"},
            {"highlight": "#f-cashflow-NPV"},
            {"click": "#sheet button:text-is('IRR')"},
            {"highlight": "#f-cashflow-IRR"},
        ],
        "expect": [
            {"selector": "#f-cashflow-NPV", "text": "282.77",
             "engine": {"sheet": "cashflow", "action": "npv",
                        "inputs": {"CF0": -10000, "flows": [[3000, 1], [4200, 1], [6800, 1], [-1500, 1]],
                                   "I": 10}, "key": "NPV"}},
            {"selector": "#f-cashflow-IRR", "text": "11.52",
             "engine": {"sheet": "cashflow", "action": "irr",
                        "inputs": {"CF0": -10000, "flows": [[3000, 1], [4200, 1], [6800, 1], [-1500, 1]],
                                   "I": 10}, "key": "IRR"}},
        ],
    },
    {
        "id": "acct-tax",
        "title": "會計｜稅額",
        "start": "acct/tax",
        "narration": (
            "稅額頁可以從未稅金額算含稅，或從含稅金額反推未稅，也內建營業稅的預設稅率。"
            "金額一千元、稅率百分之五、未稅，按計算，稅額五十元，含稅金額一千零五十元。"
            "如果手上的是含稅金額，把模式改成含稅，就能反推出未稅金額和稅額。"
        ),
        "actions": [
            {"highlight": "#tax-preset"},
            {"fill": "#f-tax-AMOUNT", "value": "1000"},
            {"fill": "#f-tax-RATE", "value": "5"},
            {"select": "#f-tax-MODE", "value": "exclusive"},
            {"click": "#biz-panel-tax button:text-is('計算')"},
            {"highlight": "#f-tax-tax"},
            {"highlight": "#f-tax-gross"},
        ],
        "expect": [
            {"selector": "#f-tax-tax", "text": "50.00",
             "engine": {"sheet": "business", "action": "tax",
                        "inputs": {"AMOUNT": 1000, "RATE": 5, "MODE": "exclusive"}, "key": "tax"}},
            {"selector": "#f-tax-gross", "text": "1,050.00",
             "engine": {"sheet": "business", "action": "tax",
                        "inputs": {"AMOUNT": 1000, "RATE": 5, "MODE": "exclusive"}, "key": "gross"}},
        ],
    },
    {
        "id": "scenario",
        "title": "情境儲存與匯出",
        "start": "acct/tvm",
        "narration": (
            "每個工作表下方都有情境功能。先輸入貸款的數字，把它取名為房貸甲，按儲存情境。"
            "之後就算清除表單，只要選擇這個情境再按載入，所有欄位與收付方向都會還原。"
            "所有資料只存在本機。到設定頁按匯出，就能把情境、紙帶和記憶下載成一個備份檔，"
            "換手機時再匯入即可。匯入時可以選擇和現有資料合併，或整個取代，取代之前會先跟你確認。"
        ),
        "actions": _fill_tvm() + [
            {"fill": "#sc-name", "value": "房貸甲"},
            {"click": "#sc-save"},
            {"highlight": "#sc-status"},
            {"click": CLEAR},
            {"highlight": "#f-tvm-N"},
            {"select": "#sc-select", "value": "房貸甲"},
            {"click": "#sc-load"},
            {"highlight": "#f-tvm-N"},
            {"goto": "settings"},
            {"highlight": "#data-export"},
            {"click": "#data-export"},
            {"highlight": "#data-status"},
        ],
        "expect": [
            {"selector": "#data-status", "text": "情境 1 個", "screen": True},
        ],
    },
    {
        "id": "settings",
        "title": "設定",
        "start": "settings",
        "narration": (
            "設定頁可以調整小數位數、數字格式、日期格式、運算順序和角度單位，改了立刻生效。"
            "數字格式可以選美式的逗號分千位，或歐式的句點分千位，上方的預覽會立刻改變。"
            "把小數位數改成四位，回到貨幣時間價值重新計算，每期付款就顯示到小數第四位。"
            "角度單位也可以在這裡預設為弧度，介面也支援深色模式。"
            "設定同樣只存在這台裝置上，重新整理之後仍會保留。"
        ),
        "actions": [
            {"highlight": "#s-decimals"},
            {"select": "#s-sep", "value": "eu"},
            {"highlight": "#s-preview-number"},
            {"select": "#s-sep", "value": "us"},
            {"select": "#s-decimals", "value": "4"},
            {"highlight": "#s-preview-number"},
            {"goto": "acct/tvm"},
        ] + _fill_tvm() + [
            {"click": CALC},
            {"highlight": "#f-tvm-PMT"},
            {"check": "#f-tvm-PMT", "text": "599.5505"},
            {"goto": "settings"},
            {"highlight": "#s-angle"},
        ],
        "expect": [
            {"selector": "#s-preview-number", "text": "1,234,567.8910", "screen": True},
            {"selector": "#f-tvm-PMT", "text": "599.5505", "at": "check",
             "engine": {"sheet": "tvm", "action": "solve", "inputs": _TVM,
                        "settings": {"decimals": 4}, "key": "PMT"}},
        ],
    },
    {
        "id": "outro",
        "title": "結語",
        "start": "acct/tvm",
        "narration": (
            "以上就是商用財務計算機的基本操作。所有計算都由經過測試的計算引擎完成，"
            "算不出來時會清楚告訴你原因，不會給出看似正常卻錯誤的數字。"
            "歡迎開啟線上網址實際操作，謝謝觀看。"
        ),
        "actions": [
            {"card": "outro", "title": "謝謝觀看", "lines": [
                "工程 ENG｜統計 STAT｜會計 ACCT",
                "算不出來就說明原因，不給看似正常的錯誤數字",
                "說明文件：README.md"], "url": APP_URL},
            {"wait": 4000},
            {"check": "#video-card", "text": "謝謝觀看"},
        ],
        "expect": [{"selector": "#video-card", "text": "fctien.github.io", "screen": True}],
    },
]

_PUNCT = set("，。、；：！？「」（）()　 ,.;:!?\n")


def speech_chars(text):
    """估算念出來的字數（去掉標點與空白）。"""
    return sum(1 for ch in text if ch not in _PUNCT)


def main(argv):
    """輸出 SEGMENTS 為 JSON（給 record.mjs）；不給路徑時印到 stdout。"""
    data = json.dumps(SEGMENTS, ensure_ascii=False, indent=1)
    if len(argv) > 1:
        with open(argv[1], "w", encoding="utf-8") as f:
            f.write(data)
    else:
        sys.stdout.write(data)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
