"""教學簡報產生器（generator）：由單一來源 teaching/prompts.py 產生 AI Agent 版與 EMBA 版投影片

版面用使用者的教材格式模組 deck_kit（tien-teaching-deck 技能）：16:9、深藍／磚紅／米白、
封面肖像與校徽、流程圖附說明、每頁出處列、不用句點

產出（只寫 teaching/out/，每次由原始資料重產，不覆蓋任何手改檔）
- BACalc_AI.pptx、BACalc_AI_講稿.pptx
- BACalc_EMBA.pptx、BACalc_EMBA_講稿.pptx
  講稿版每頁備忘稿（notes）都有【講稿】與【投影片說明】兩段

使用者簡報規則
- 字級 ≥ 16 pt；只有 Prompt／程式碼框（Consolas）可用 14 pt
- 不用全形句點；內文行距 1.5 倍；重要名詞附英文；盡量放圖（App 實際截圖在 teaching/assets/）

分層（MVC）
- Model：teaching.prompts（STEPS、USER_CLAUDE_MD、PROJECT_CLAUDE_MD）
- View：本檔的 slide_* 函式（只負責排版）
- Controller：build()／main()（決定版本、是否加備忘稿、輸出路徑）

環境變數
- DECK_KIT：deck_kit.py 所在資料夾（預設 <Tien Research>/deck_kit）
- DECK_RES：肖像與校徽所在資料夾（預設 <Tien Research>/）

用法：python teaching/deck/build_deck.py（在 BACalc 根目錄執行）
"""
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TEACHING = os.path.dirname(HERE)
ROOT = os.path.dirname(TEACHING)
TIEN = os.path.dirname(ROOT)  # 上一層 Tien Research 資料夾
ASSETS = os.path.join(TEACHING, "assets")
OUT_DIR = os.path.join(TEACHING, "out")

# deck_kit 在 import 時讀 DECK_RES／DECK_IMG，所以要先設好
os.environ.setdefault("DECK_RES", TIEN + os.sep)
os.environ.setdefault("DECK_IMG", ASSETS)
KIT_DIR = os.environ.get("DECK_KIT", os.path.join(TIEN, "deck_kit"))
for p in (ROOT, KIT_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from pptx.util import Inches as In, Pt  # noqa: E402
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN  # noqa: E402

from deck_kit import (  # noqa: E402
    Deck, cover, header, footer, refline, flowrow, node, arrow, cards, box, txt, shot,
    closing, ea_font, NAVY, BRICK, GREEN, SOFT, LINE, INK, MUT, C, MSO_SHAPE,
)
from teaching import prompts  # noqa: E402  Model：單一來源
from teaching.build_cards import bad_result_label, tag_note  # noqa: E402  tag 加註、實測／推測標示

CODE_FONT = "Consolas"
CODE_SIZE = 14          # Prompt／程式碼框：使用者規則允許的 14 pt 例外
MIN_TEXT = 16           # 其他文字下限
LINE_SPACING = 1.5      # 使用者規則：1.5–2 倍行距
CONTENT_BOTTOM = 6.45   # deck_kit：內容區下緣（出處列在 6.52）
OPTIONAL_NOTE = "選用，作者未實測"
SHOT_DATE = "2026-10-21"
SHOT_SRC = "BACalc App 實際截圖（%s，本機 localhost:8765）" % SHOT_DATE

VERSIONS = {
    "ai": {"name": "AI Agent 版", "out": "BACalc_AI"},
    "emba": {"name": "EMBA 版", "out": "BACalc_EMBA"},
}

# 截圖：檔名 → (說明, 出處說明)
SHOTS = {
    "tvm_result": "TVM 房貸：PMT 求出 1,798.65（付出）",
    "amort_table": "攤還 AMORT：INT -17,899.78 與攤還表",
    "cf_irr": "現金流 CF：NPV 282.77、IRR 11.52",
    "calc_tape": "計算機 CALC：算式與紙帶 Tape",
    "settings_about": "設定頁「關於」：MicroPython 版本與啟動時間",
    "mobile_tvm": "手機版 375 px：單欄與底部分頁列",
}


# ---------------------------------------------------------------------------
# 文字量估算（沒有 LibreOffice 可轉圖，改用估算確保不超出內容區）
# ---------------------------------------------------------------------------

def text_em(text):
    """估算字串寬度（em）：中文與全形字 1 em，其他 0.56 em"""
    w = 0.0
    for ch in text:
        w += 1.0 if ord(ch) > 0x2E7F or ch in "【】「」（）、，：；" else 0.56
    return w


def est_lines(text, width_in, size_pt):
    """一段文字在指定寬度下的估計行數"""
    per_line = width_in * 72.0 / size_pt
    total = 0
    for para in text.split("\n"):
        total += max(1, math.ceil(text_em(para) * 1.06 / per_line))
    return total


def line_h(size_pt, spacing=LINE_SPACING):
    """單行高度（吋）：PowerPoint 單倍行距約為字級 1.2 倍"""
    return size_pt * 1.2 * spacing / 72.0


def est_height(paras, width_in, size_pt, after_pt=8, spacing=LINE_SPACING):
    """多段文字估計高度（吋）"""
    h = 0.0
    for t in paras:
        h += est_lines(t, width_in, size_pt) * line_h(size_pt, spacing) + after_pt / 72.0
    return h


def check_fit(bottom, what):
    """內容超出內容區就停下（寧可建置失敗，也不交出文字溢出的投影片）"""
    if bottom > CONTENT_BOTTOM + 1e-6:
        raise ValueError("版面超出內容區：%s（下緣 %.2f 吋 > %.2f）" % (what, bottom, CONTENT_BOTTOM))


# ---------------------------------------------------------------------------
# 版面小元件（deck_kit 之外，補上 1.5 倍行距與 Prompt 框）
# ---------------------------------------------------------------------------

def paras(sl, x, y, w, items, size=17, after=8):
    """多段說明文字（1.5 倍行距）；items 中 tuple ('文字',) 為磚紅粗體結論句；回傳估計下緣"""
    tb = sl.shapes.add_textbox(In(x), In(y), In(w), In(0.5))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    texts = []
    for i, it in enumerate(items):
        strong = isinstance(it, tuple)
        text = it[0] if strong else it
        texts.append(text)
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.line_spacing = LINE_SPACING
        p.space_after = Pt(after)
        r = p.add_run()
        r.text = text
        f = r.font
        f.size = Pt(size)
        f.bold = strong
        f.color.rgb = BRICK if strong else INK
        f.name = "Segoe UI"
        ea_font(r)
    return y + est_height(texts, w, size, after)


def bullets(sl, x, y, w, items, size=17, after=8, marker="・"):
    """條列（1.5 倍行距）；回傳估計下緣"""
    return paras(sl, x, y, w, [marker + t for t in items], size=size, after=after)


def code_panel(sl, x, y, w, h, lines, size=CODE_SIZE, label_color=None):
    """深色 Prompt／程式碼框（Consolas、1.5 倍行距）；【…】標籤行用淺磚紅色，# 開頭為綠色註解"""
    b = box(sl, x, y, w, h, C(0x26, 0x2B, 0x33), adj=0.04)
    tf = b.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.TOP
    tf.margin_left = In(.22)
    tf.margin_right = In(.15)
    tf.margin_top = In(.14)
    tf.margin_bottom = In(.08)
    for i, t in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.LEFT
        p.line_spacing = LINE_SPACING
        r = p.add_run()
        r.text = t
        f = r.font
        f.size = Pt(size)
        f.name = CODE_FONT
        ea_font(r)
        if t.startswith("【"):
            f.color.rgb = label_color or C(0xF0, 0xC9, 0xA8)
            f.bold = True
        elif t.lstrip().startswith("#"):
            f.color.rgb = C(0x9F, 0xC5, 0x8F)
        else:
            f.color.rgb = C(0xE8, 0xE4, 0xDC)
    return b


def code_capacity(h, size=CODE_SIZE):
    """Prompt 框可容納的估計行數"""
    return int((h - 0.24) / line_h(size))


def code_lines_needed(lines, w, size=CODE_SIZE):
    inner = w - 0.37
    return sum(est_lines(t, inner, size) for t in lines)


def chunk_prompt(text, w, h, size=CODE_SIZE):
    """把 Prompt 依【…】段落切成多頁，每頁不超過框的容量；單段太長時再依行切"""
    cap = code_capacity(h, size)
    sections, cur = [], []
    for line in text.splitlines():
        if line.startswith("【") and cur:
            sections.append(cur)
            cur = []
        cur.append(line)
    if cur:
        sections.append(cur)
    pages, page = [], []
    for sec in sections:
        need = code_lines_needed(sec, w, size)
        if page and code_lines_needed(page, w, size) + need > cap:
            pages.append(page)
            page = []
        if need > cap:  # 單段太長：逐行切
            for line in sec:
                if page and code_lines_needed(page + [line], w, size) > cap:
                    pages.append(page)
                    page = []
                page.append(line)
        else:
            page.extend(sec)
    if page:
        pages.append(page)
    return pages


def chunk_items(items, w, h, size=17, after=8, marker="・"):
    """條列依估計高度分頁（估算時含項目符號 marker）"""
    pages, page = [], []
    for it in items:
        if page and est_height([marker + t for t in page + [it]], w, size, after) > h:
            pages.append(page)
            page = []
        page.append(it)
    if page:
        pages.append(page)
    return pages


# ---------------------------------------------------------------------------
# Controller 狀態：一份 Deck 加上每頁備忘稿
# ---------------------------------------------------------------------------

class Builder:
    """建置一份簡報；notes 收集每頁的【講稿】與【投影片說明】"""

    def __init__(self, version, with_notes):
        self.version = version
        self.vname = VERSIONS[version]["name"]
        self.with_notes = with_notes
        self.dk = Deck()
        self.notes = []  # (slide, 講稿, 投影片說明)

    def new(self):
        return self.dk.new()

    def done(self, sl, speech, desc, page=True):
        """收尾：頁尾＋登記備忘稿"""
        if page:
            footer(self.dk, sl)
        self.notes.append((sl, speech, desc))

    def save(self, path):
        enforce_fonts(self.dk.prs)
        if self.with_notes:
            for sl, speech, desc in self.notes:
                set_notes(sl, speech, desc)
        return self.dk.save(path)


def no_period(text):
    """備忘稿也不用句點：句末刪除、句中改逗號"""
    text = re.sub(r"。\s*(\n|$)", r"\1", text)
    return text.replace("。", "，")


def set_notes(sl, speech, desc):
    """備忘稿固定兩段：【講稿】與【投影片說明】"""
    tf = sl.notes_slide.notes_text_frame
    tf.text = no_period("【講稿】\n%s\n\n【投影片說明】\n%s" % (speech.strip(), desc.strip()))


def enforce_fonts(prs):
    """字級下限：Consolas（Prompt／程式碼）≥ 14 pt，其餘 ≥ 16 pt
    deck_kit 的頁尾、出處列、eyebrow 預設 14 pt，依使用者規則一律提高到 16 pt"""
    def fix_tf(tf):
        for p in tf.paragraphs:
            for r in p.runs:
                floor = CODE_SIZE if r.font.name == CODE_FONT else MIN_TEXT
                if r.font.size is None or r.font.size < Pt(floor):
                    r.font.size = Pt(floor)

    for sl in prs.slides:
        for sh in sl.shapes:
            if sh.has_text_frame:
                fix_tf(sh.text_frame)
            if getattr(sh, "has_table", False) and sh.has_table:
                for row in sh.table.rows:
                    for cell in row.cells:
                        fix_tf(cell.text_frame)


def asset(name):
    """截圖路徑；檔案不存在時 deck_kit.shot 會畫出「[缺圖]」佔位框，不會捏造圖片"""
    return os.path.join(ASSETS, name + ".png")


def step_no(step):
    return int(step["id"].replace("step", ""))


def eyebrow_of(step, vname):
    """每頁 eyebrow：Step 編號＋標題；step7 一律標「選用，作者未實測」"""
    s = "Step %d · %s · %s" % (step_no(step), step["title"], vname)
    if step.get("optional") and OPTIONAL_NOTE not in step["title"]:
        s += " · " + OPTIONAL_NOTE
    return s


def step_ref(step, field):
    return "teaching/prompts.py　%s %s" % (step["id"], field)


# ---------------------------------------------------------------------------
# View：共用頁面
# ---------------------------------------------------------------------------

def slide_cover(b):

    def right(sl):
        shot(sl, asset("tvm_result"), 7.55, 1.45, 5.18, SHOTS["tvm_result"])
        y = 4.75
        items = [("Python 引擎", "engine/ 純計算"), ("MicroPython", "WebAssembly"),
                 ("離線 PWA", "手機電腦都能用")]
        for i, (t, s) in enumerate(items):
            x = 7.55 + i * 1.78
            node(sl, x, y, 1.62, 1.0, t, s, fill=[GREEN, NAVY, BRICK][i], tsize=16, ssize=14)

    if b.version == "ai":
        eyebrow = "AI Agent 實作課 · Claude Code"
        title = ["BACalc 財務計算機", "用 AI Agent 做完整專案"]
        sub = ["從 CLAUDE.md 到部署的 10 個步驟", "TDD、Skill、自我驗證 Loop、GitHub Pages"]
    else:
        eyebrow = "EMBA · 用 AI 做出自己的工具"
        title = ["BACalc 財務計算機", "描述需求與驗收答案"]
        sub = ["10 個步驟，每步從參考版本接手", "用 Excel 與 BA II Plus 對答案"]
    sl = cover(b.dk, eyebrow, title, sub, right=right, title_size=40)
    refline(sl, SHOT_SRC)
    b.notes.append((sl,
                    "今天用 BACalc 這個仿 BA II Plus 的財務計算機當案例，"
                    + ("示範怎麼用 Claude Code 這類 AI Agent 從規劃、測試、到部署完成一個完整專案"
                       if b.version == "ai" else
                       "示範怎麼把需求講清楚、怎麼拿 Excel 或計算機驗收 AI 做出來的結果、不對時怎麼請 AI 修正"),
                    "封面（cover）：左側為課程名稱與講者，右上為 App 實際截圖，"
                    "右下三個方塊是本案例的三個技術重點；出處列標示截圖日期"))


def slide_agenda(b):
    sl = b.new()
    y = header(sl, "課程架構", "十個步驟與 git tag", "每一步都有 Prompt、驗收方式與參考答案 tag（step0～step9）")
    w, h, gx = 2.25, 1.12, 0.22
    for i, s in enumerate(prompts.STEPS):
        row, col = divmod(i, 5)
        col = col if row == 0 else 4 - col  # 蛇形排列
        x = 0.6 + col * (w + gx)
        yy = y + 0.25 + row * (h + 0.55)
        fill = BRICK if s.get("optional") else (GREEN if i == 0 else NAVY)
        short = s["title"].split("：")[-1] if "：" in s["title"] else s["title"]
        short = re.sub(r"（.*?）", "", short) + ("（選用）" if s.get("optional") else "")
        node(sl, x, yy, w, h, s["id"], short, fill=fill, tsize=17, ssize=14)
        if row == 0 and col < 4:
            arrow(sl, x + w + 0.01, yy + h / 2 - 0.12, gx - 0.02, 0.24)
        if row == 1 and col > 0:
            arrow(sl, x - gx + 0.01, yy + h / 2 - 0.12, gx - 0.02, 0.24, shape=MSO_SHAPE.LEFT_ARROW)
    arrow(sl, 0.6 + 4 * (w + gx) + w / 2 - 0.15, y + 0.25 + h + 0.08, 0.30, 0.40,
          shape=MSO_SHAPE.DOWN_ARROW)
    bottom = paras(sl, 0.6, y + 0.25 + 2 * h + 0.55 + 0.25, 12.13, [
        "上圖為十個步驟的順序：上排由左而右，下排由右而左；磚紅色的 step7 為選用，作者未實測、沒有 tag",
        ("每一步做完都打一個 git tag，教材中的 Prompt 都是實際用過的",),
    ], size=17)
    check_fit(bottom, "課程架構")
    refline(sl, "docs/spec-2026-10-19.md 5.2 節", "teaching/prompts.py STEPS")
    b.done(sl, "整門課分成十步，從兩層 CLAUDE.md 開始，到部署上 GitHub Pages、安裝到手機結束；"
               "每一步完成都有一個 git tag，可以隨時切回參考答案；step7 Google Drive 同步是選用，作者沒有實測，所以沒有 tag",
           "蛇形流程圖（flow diagram）列出 step0～step9；磚紅色方塊為選用步驟；下方文字說明讀圖順序")


def slide_why(b):
    sl = b.new()
    y = header(sl, "為什麼選這個案例", "BACalc：仿 BA II Plus 的財務計算 PWA",
               "答案可以用 Excel 與實體計算機核對，適合練習「怎麼驗收 AI 的產出」")
    cards(sl, y + 0.2, [
        ("BA II Plus 風格", "財務計算機 Financial Calculator",
         "TVM、攤還、現金流、利率換算、統計、債券、折舊，欄位與正負號慣例和計算機一致",
         "每題都有 Excel 公式當標準答案"),
        ("Python 在瀏覽器執行", "MicroPython＋WebAssembly",
         "計算引擎是純 Python，在 Web Worker 背景載入，畫面先顯示",
         "下載約 0.23 MB，比 Pyodide 小約 23 倍"),
        ("離線可用的 PWA", "Progressive Web App",
         "純靜態檔、資料只存本機 IndexedDB，手機安裝後飛航模式也能算",
         "部署在 GitHub Pages"),
    ], h=3.05)
    bottom = paras(sl, 0.6, y + 3.5, 12.13, [
        ("本案例的重點：算不出來就說原因，絕不顯示看起來正常但錯誤的數字",),
    ], size=17)
    check_fit(bottom, "為什麼選這個案例")
    refline(sl, "BACalc CLAUDE.md", "README.md", "DEVLOG 規格修訂（下載大小實測）")
    b.done(sl, "選這個案例有三個理由：第一，財務計算的答案很明確，可以拿 Excel 或 BA II Plus 對；"
               "第二，它是 Python 寫的引擎，卻能在瀏覽器裡用 MicroPython 執行；第三，它是離線可用的 PWA，"
               "手機裝起來就能用；最重要的原則是寧可報錯，也不給看起來正常的錯數字",
           "三張卡片（cards）分別說明案例的三個特點；下方磚紅句是全課反覆出現的原則；"
           "0.23 MB 與 23 倍為 DEVLOG 記錄的實測值")

    # 第二頁：實際畫面（桌面＋手機）
    sl = b.new()
    y = header(sl, "為什麼選這個案例", "App 實際畫面", "桌面版左側選單、手機版單欄加底部分頁列")
    bottom1 = shot(sl, asset("tvm_result"), 0.6, y + 0.1, 7.2, SHOTS["tvm_result"])
    mob = sl.shapes.add_picture(asset("mobile_tvm"), In(8.1), In(y + 0.1), height=In(4.0)) \
        if os.path.exists(asset("mobile_tvm")) else None
    if mob is not None:
        mob.line.color.rgb = LINE
    txt(sl, 8.1, y + 4.16, 2.2, 0.3, [{"text": "手機版 375 px", "size": 16, "color": MUT}])
    paras(sl, 10.3, y + 0.1, 2.43, [
        "求出的格子以綠框標示",
        "收到／付出用按鈕切換，和 TI 正負號一致",
        ("房貸 PMT = -1,798.65",),
    ], size=16)
    check_fit(max(bottom1 + 0.36, y + 4.46), "實際畫面")
    refline(sl, SHOT_SRC)
    b.done(sl, "這是 App 的實際畫面：輸入 30 年、年利率 6%、借 300,000，留 PMT 空白按計算，"
               "求出每月付 1,798.65，紅色「付出」代表負號；右邊是手機版，一欄往下排，底部有分頁列",
           "左為桌面版截圖、中為手機版截圖（Playwright 驅動 Chrome 實際操作後擷取），右側為讀圖重點；"
           "數字與 Excel =PMT(0.06/12,360,300000) 一致")


def slide_mvc(b):
    sl = b.new()
    y = header(sl, "為什麼選這個案例", "MVC 分層與執行環境", "計算只放在 Model，畫面與橋接分開，才能分別測試")
    flowrow(sl, y + 0.3, [
        ("View", "畫面 HTML／CSS", "web/index.html、views/"),
        ("Controller", "app.js、py-worker.js", "排隊、世代編號"),
        ("Controller", "engine/bridge.py", "唯一入口、永不擲例外"),
        ("Model", "engine/*.py", "只 import math、json"),
    ], colors=[GREEN, NAVY, NAVY, BRICK], h=1.7)
    bottom = paras(sl, 0.6, y + 2.3, 12.13, [
        "上圖為一次計算的路徑：畫面把輸入交給 Controller，經 Web Worker 呼叫 bridge.py，再由 Model 計算後原路回傳",
        "Model 同時在 CPython（pytest）與 MicroPython（npm run test:mpy）執行同一份 golden 測試",
        ("回傳格式統一：成功 ok: true＋values，失敗 ok: false＋中文原因與欄位",),
    ], size=17)
    check_fit(bottom, "MVC")
    refline(sl, "teaching/prompts.py PROJECT_CLAUDE_MD", "docs/spec-2026-10-19.md 1.2 節")
    b.done(sl, "架構上採 MVC：Model 是 engine 裡的純 Python，不碰任何 I/O；Controller 是 bridge.py 和前端的 app.js、"
               "py-worker.js；View 是畫面；這樣切的好處是 Model 可以在電腦上用 pytest 測，也可以在 MicroPython 上跑同一份測試",
           "橫向流程圖（flowrow）表示一次計算請求經過的四層；下方三句說明讀圖方式、雙執行環境測試與統一回傳格式")


def slide_four_part(b):
    sl = b.new()
    if b.version == "ai":
        y = header(sl, "方法", "四段式 Prompt", "每一步的 Prompt 都分成任務、介面、限制、驗收四段")
        steps = [("【任務】", "要做什麼", "一句講清楚範圍"),
                 ("【介面】", "別人會依賴的東西", "檔名、函式、格式"),
                 ("【限制】", "不能做什麼", "執行環境、禁止事項"),
                 ("【驗收】", "怎麼證明做對", "可執行的指令")]
        lines = ["上圖為四段式 Prompt 的結構：【介面】只寫別人會依賴的東西，其餘細節交給 AI 決定",
                 "【限制】寫明執行環境（例如 MicroPython 沒有 decimal、ast），AI 才不會用錯工具",
                 ("【驗收】一定要能執行：AI 要貼出實際跑過的指令與結果",)]
    else:
        y = header(sl, "方法", "四段式需求描述", "用白話寫，也分成任務、介面、限制、驗收四段")
        steps = [("【任務】", "要做什麼", "例如算房貸月付"),
                 ("【介面】", "長什麼樣子", "欄位名稱、按鈕"),
                 ("【限制】", "不能怎樣", "不能顯示假數字"),
                 ("【驗收】", "怎麼對答案", "Excel 或計算機")]
        lines = ["上圖為四段式需求描述：不需要懂程式，只要講清楚要什麼、長什麼樣、不能怎樣、怎麼對答案",
                 "【驗收】寫出一題具體例題與標準答案，AI 做完就能立刻核對",
                 ("答案對不上時，把例題、App 的數字與 Excel 的數字一起貼給 AI，請它修正",)]
    flowrow(sl, y + 0.3, steps, colors=[GREEN, NAVY, NAVY, BRICK], h=1.7)
    bottom = paras(sl, 0.6, y + 2.3, 12.13, lines, size=17)
    check_fit(bottom, "四段式")
    refline(sl, "teaching/prompts.py 說明（四段式 Prompt）")
    b.done(sl, "接下來每一步都用同一個格式下 Prompt：任務、介面、限制、驗收；"
               + ("介面只寫別人會依賴的東西，例如檔名、函式簽名、回傳格式；限制寫執行環境與禁止事項；"
                  "驗收寫成可以執行的指令，AI 做完要把實際輸出貼出來"
                  if b.version == "ai" else
                  "不需要會寫程式，重點是把例題和標準答案寫進驗收，這樣 AI 做完就能馬上核對"),
           "四個方塊依序為四段式的四個段落，下方說明各段寫法；最後一句為本方法的重點")


def slide_claude_md(b):
    sl = b.new()
    y = header(sl, "兩層 CLAUDE.md", "使用者層級與專案層級", "AI 每次開工都會先讀 CLAUDE.md，規則寫一次就好")
    flowrow(sl, y + 0.3, [
        ("第 1 層", "使用者層級", "~/.claude/CLAUDE.md"),
        ("第 2 層", "專案層級", "專案根目錄 CLAUDE.md"),
        ("開工", "AI 先讀兩層規則", "每次對話自動載入"),
    ], colors=[GREEN, NAVY, BRICK], h=1.7)
    bottom = paras(sl, 0.6, y + 2.3, 12.13, [
        "上圖為兩層規則的關係：使用者層級放個人通用習慣（所有專案共用），專案層級放這個專案特有、可以檢查的規則",
        "專案層級不重複寫使用者層級的內容，一條規則一行",
        ("沒寫進 CLAUDE.md 的規則，AI 不會自己遵守",),
    ], size=17)
    check_fit(bottom, "兩層 CLAUDE.md")
    refline(sl, "teaching/prompts.py USER_CLAUDE_MD、PROJECT_CLAUDE_MD")
    b.done(sl, "CLAUDE.md 是寫給 AI 看的工作規則；第一層在自己的家目錄，放個人習慣，例如用繁體中文回答、"
               "不確定就說不確定；第二層在專案資料夾，放這個專案的規則，例如 MVC、不回假數字；"
               "本專案實際看到 AI 在安裝套件前停下來等同意，就是因為規則有寫",
           "流程圖表示兩層 CLAUDE.md 與 AI 開工的關係；接下來兩頁是兩層的完整範本，可從 Prompt 卡複製")

    # 使用者層級範本
    _code_slides(b, "兩層 CLAUDE.md", "使用者層級範本", "~/.claude/CLAUDE.md，所有專案共用",
                 prompts.USER_CLAUDE_MD.rstrip("\n"), "teaching/prompts.py USER_CLAUDE_MD",
                 "這是使用者層級的範本，只有五條：繁體中文、不確定就說、自己測試、大改動先給計畫、"
                 "危險動作先問；這五條和專案無關，寫在家目錄，所有專案共用",
                 "深色框為 USER_CLAUDE_MD 範本原文（Consolas 14 pt，原文密集的例外）")
    _code_slides(b, "兩層 CLAUDE.md", "專案層級範本", "專案根目錄 CLAUDE.md：常用指令／專案結構／程式風格／工作方式／重要規則",
                 prompts.PROJECT_CLAUDE_MD.rstrip("\n"), "teaching/prompts.py PROJECT_CLAUDE_MD",
                 "這是專案層級的範本，固定五段；請注意重要規則那段：MVC、不回假數字、禁止 eval、"
                 "engine 只能用 math 和 json，這些都是本專案實際踩過才寫進來的",
                 "深色框為 PROJECT_CLAUDE_MD 範本原文，依段落分頁；step0 tag 的 CLAUDE.md 早於範本，段落不同，只當參考")


def _code_slides(b, eyebrow, title, sub, text, ref, speech, desc, step=None):
    """把一段原文放進 Prompt 框，必要時分頁；回傳頁數"""
    y0 = 1.84
    w, h = 12.13, CONTENT_BOTTOM - (y0 + 0.08)
    pages = chunk_prompt(text, w, h)
    for i, lines in enumerate(pages):
        sl = b.new()
        t = title if len(pages) == 1 else "%s（%d／%d）" % (title, i + 1, len(pages))
        header(sl, eyebrow, t, sub)
        need = code_lines_needed(lines, w) * line_h(CODE_SIZE) + 0.24
        ph = min(h, max(1.2, need + 0.1))
        code_panel(sl, 0.6, y0 + 0.08, w, ph, lines)
        check_fit(y0 + 0.08 + need, "%s 第 %d 頁" % (title, i + 1))
        refline(sl, ref)
        part = "" if len(pages) == 1 else "（第 %d 頁，共 %d 頁）" % (i + 1, len(pages))
        b.done(sl, speech + part, desc)
    return len(pages)


def slide_emba_method(b):
    sl = b.new()
    y = header(sl, "方法", "每一步的進行方式", "從參考版本接手，只做這一步的關鍵 Prompt 與驗收")
    flowrow(sl, y + 0.3, [
        ("1", "切到起點版本", "git checkout 起點 tag"),
        ("2", "下四段式 Prompt", "照 Prompt 卡複製"),
        ("3", "對答案", "Excel 或 BA II Plus"),
        ("4", "請 AI 修正", "附例題與兩邊數字"),
    ], colors=[GREEN, NAVY, NAVY, BRICK], h=1.7)
    bottom = paras(sl, 0.6, y + 2.3, 12.13, [
        "上圖為 EMBA 版每一步的流程：起點版本（git tag）由助教或 AI 幫忙切換，學員專心在描述需求與驗收",
        "對不上時不要只說「錯了」，要附上例題、App 顯示的數字、Excel 公式與結果",
        ("驗收通過才進下一步；每一步都可以切回參考版本重來",),
    ], size=17)
    check_fit(bottom, "EMBA 方法")
    refline(sl, "docs/spec-2026-10-19.md 5.1 節（EMBA 版）")
    b.done(sl, "EMBA 版不需要自己寫程式：每一步先切到起點版本，也就是上一步做好的狀態，"
               "接著下這一步的 Prompt，再拿 Excel 或計算機對答案；對不上時，把例題和兩邊的數字一起貼給 AI，請它找原因並修正",
           "四步流程圖為 EMBA 版的固定節奏；下方說明請 AI 修正時要附的資訊")


# ---------------------------------------------------------------------------
# View：每個步驟
# ---------------------------------------------------------------------------

def slide_step_overview(b, step):
    data = step[b.version]
    sl = b.new()
    n = step_no(step)
    if b.version == "ai":
        done_tag = (step["tag"] + tag_note(step["tag"])) if step["tag"] else "沒有 tag（%s）" % OPTIONAL_NOTE
        sub = "完成後對照 tag：%s" % done_tag
        flow = [("1", "下 Prompt", "四段式原文"),
                ("2", "AI 實作", "程式與測試"),
                ("3", "驗收", "%d 項驗收" % len(data["verify"])),
                ("4", "對照 tag", step["tag"] or "無 tag")]
    else:
        sub = "起點 tag：%s　·　完成 tag：%s" % (
            data["start_tag"], (step["tag"] + tag_note(step["tag"])) if step["tag"] else "沒有（%s）" % OPTIONAL_NOTE)
        flow = [("1", "切到起點", data["start_tag"]),
                ("2", "下 Prompt", "白話四段式"),
                ("3", "對答案", "%d 項驗收" % len(data["verify"])),
                ("4", "請 AI 修正", "附例題與數字")]
    title = "Step %d　%s" % (n, step["title"])
    header(sl, eyebrow_of(step, b.vname), title, sub)
    y = 1.84
    flowrow(sl, y + 0.25, flow, colors=[GREEN, NAVY, NAVY, BRICK], h=1.45)
    lines = ["上圖為本步驟的進行順序", "目標：" + step["goal"].replace("\n", "；")]
    lines.append(("預期產出：" + data["expected"],))
    bottom = paras(sl, 0.6, y + 1.95, 12.13, lines, size=17)
    check_fit(bottom, "%s 概觀" % step["id"])
    refline(sl, step_ref(step, "goal、expected"))
    opt = "這一步是選用，作者沒有用真的 Client ID 實測，所以沒有 tag，課堂上當延伸閱讀；" if step.get("optional") else ""
    if b.version == "ai":
        speech = "%s第 %d 步是「%s」；目標是%s；做法是先下四段式 Prompt，讓 AI 實作，跑完 %d 項驗收，%s" % (
            opt, n, step["title"], step["goal"].replace("\n", "，"), len(data["verify"]),
            ("最後用 git checkout %s 對照參考答案" % step["tag"]) if step["tag"] else "這一步沒有參考答案 tag")
    else:
        speech = "%s第 %d 步是「%s」；先切到起點版本 %s，再下這一步的 Prompt，然後用 %d 項驗收對答案；預期看到的是：%s" % (
            opt, n, step["title"], data["start_tag"], len(data["verify"]), data["expected"])
    b.done(sl, speech, "上方流程圖為本步驟的四個動作，副標註明 git tag；下方為目標與預期產出（磚紅字）")


def slide_step_prompt(b, step):
    data = step[b.version]
    kind = "四段式 Prompt 原文" if b.version == "ai" else "白話四段式 Prompt 原文"
    _code_slides(
        b, eyebrow_of(step, b.vname), "Prompt 原文", kind + "，可從 Prompt 卡一鍵複製",
        data["prompt"], step_ref(step, "%s.prompt" % b.version),
        "這是第 %d 步實際使用的 Prompt；%s" % (
            step_no(step),
            "請注意【介面】只寫別人會依賴的檔名、函式與格式，【限制】寫執行環境與禁止事項，【驗收】寫可以執行的指令"
            if b.version == "ai" else
            "請注意【驗收】寫明了怎麼核對結果，AI 做完就能用 Excel、計算機或白話複述來確認"),
        "深色框為 Prompt 原文（Consolas 14 pt，原文密集的例外），【…】為四段式標籤；太長時依段落分頁",
        step)


def slide_step_compare(b, step):
    """AI 版：一句話下法 vs 四段式 Prompt（step0～2 為替身演練實測，其餘為推測）"""
    data = step["ai"]
    sl = b.new()
    label, guess = bad_result_label(data["bad_result"])
    measured = label.startswith("實測")
    sub = ("左邊為課前替身演練的實測結果（teaching/rehearse.md）" if measured
           else "左邊的結果為推測（未實測）") + "；實際發生的同類問題見「實際踩過的坑」第一條"
    header(sl, eyebrow_of(step, b.vname), "一句話下法與四段式對照", sub)
    y = 1.84 + 0.15
    colw, gap = 5.97, 0.19
    left = [("一句話下法", 20, True, NAVY), (data["bad_prompt"], 17, False, INK),
            (label, 16, True, BRICK), (guess, 16, False, INK)]
    right = [("四段式 Prompt（見前頁原文）", 20, True, NAVY),
             ("預期產出", 16, True, BRICK), (data["expected"], 16, False, INK)]

    def est(items):
        return 0.4 + sum(est_lines(t, colw - 0.36, s) * line_h(s) + 6 / 72 for t, s, _, _ in items)

    h = max(est(left), est(right))
    for i, items in enumerate((left, right)):
        x = 0.6 + i * (colw + gap)
        bx = box(sl, x, y, colw, h, SOFT, LINE, adj=0.05)
        tf = bx.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = MSO_ANCHOR.TOP
        tf.margin_left = tf.margin_right = In(.18)
        tf.margin_top = In(.16)
        for j, (t, s, bold, col) in enumerate(items):
            p = tf.paragraphs[0] if j == 0 else tf.add_paragraph()
            p.alignment = PP_ALIGN.LEFT
            p.line_spacing = LINE_SPACING
            p.space_after = Pt(6)
            r = p.add_run()
            r.text = t
            r.font.size = Pt(s)
            r.font.bold = bold
            r.font.color.rgb = col
            r.font.name = "Segoe UI"
            ea_font(r)
    check_fit(y + h, "%s 對照" % step["id"])
    refline(sl, step_ref(step, "ai.bad_prompt、bad_result、expected"))
    if measured:
        talk = ("對照組是一句話下法「%s」；左邊是課前演練實際跑出來的結果，由實作者在全新資料夾扮演學生與 AI，"
                "不是獨立的 AI 工作階段，細節見 teaching/rehearse.md；" % data["bad_prompt"])
        note = "左右兩張卡片對照一句話下法與四段式 Prompt；左卡「實測（替身演練）」標示該結果來自課前演練"
    else:
        talk = ("對照組是一句話下法「%s」；左邊寫的是推測的結果，本專案沒有真的用一句話版本跑過，所以不能當成實測；"
                % data["bad_prompt"])
        note = "左右兩張卡片對照一句話下法與四段式 Prompt；左卡「推測（未實測）」標示該結果不是實測"
    b.done(sl, talk + "右邊是四段式 Prompt 的預期產出；本專案實際踩過的同類問題放在後面「實際踩過的坑」第一條", note)


def slide_step_verify(b, step):
    data = step[b.version]
    eb = eyebrow_of(step, b.vname)
    ref = step_ref(step, "%s.verify" % b.version)
    if b.version == "ai":
        lines = [("$ " + v) if _is_command(v) else ("# " + v) for v in data["verify"]]
        y0, w = 1.84, 12.13
        h = CONTENT_BOTTOM - 0.75 - (y0 + 0.08)
        pages = chunk_prompt("\n".join(lines), w, h, size=16)
        for i, pg in enumerate(pages):
            sl = b.new()
            t = "驗收方式" if len(pages) == 1 else "驗收方式（%d／%d）" % (i + 1, len(pages))
            header(sl, eb, t, "在該步 tag 上存在、可執行的驗收指令；# 開頭為手動操作")
            need = code_lines_needed(pg, w, 16) * line_h(16) + 0.24
            code_panel(sl, 0.6, y0 + 0.08, w, need + 0.08, pg, size=16)
            bottom = paras(sl, 0.6, y0 + 0.08 + need + 0.25, 12.13,
                           [("AI 要貼出實際執行的指令與輸出，全部通過才算完成",)], size=17)
            check_fit(bottom, "%s 驗收" % step["id"])
            refline(sl, ref)
            b.done(sl, "驗收是這一步最重要的部分；這 %d 項指令在 %s 上都存在、可以執行%s；"
                       "請 AI 把實際輸出貼出來，不要只說「測試通過」" % (
                           len(data["verify"]), step["tag"] or "目前的版本",
                           "" if len(pages) == 1 else "（第 %d 頁，共 %d 頁）" % (i + 1, len(pages))),
                   "深色框列出驗收指令（$ 為終端機指令、# 為手動操作，Consolas 16 pt）；下方磚紅字為完成條件")
    else:
        pages = chunk_items(data["verify"], 12.13, CONTENT_BOTTOM - 0.7 - 1.94, size=17)
        for i, pg in enumerate(pages):
            sl = b.new()
            t = "怎麼對答案" if len(pages) == 1 else "怎麼對答案（%d／%d）" % (i + 1, len(pages))
            header(sl, eb, t, "拿 Excel 或實體 BA II Plus 核對；按鍵依記憶撰寫者已標示未實機驗證")
            bottom = bullets(sl, 0.6, 1.94, 12.13, pg, size=17)
            bottom = paras(sl, 0.6, bottom + 0.1, 12.13,
                           [("App、Excel、計算機三者一致才算通過；對不上就把三個數字一起貼給 AI",)], size=17)
            check_fit(bottom, "%s 對答案" % step["id"])
            refline(sl, ref)
            b.done(sl, "這一步用 %d 個方法對答案；先用 Excel 公式算出標準答案，再看 App 顯示的數字是否一樣；"
                       "BA II Plus 的按鍵是作者依記憶寫的，還沒有用實機驗證，上課時以 Excel 為準%s" % (
                           len(data["verify"]), "" if len(pages) == 1 else "（第 %d 頁，共 %d 頁）" % (i + 1, len(pages))),
                   "條列為驗收操作與預期數字（附 Excel 公式）；下方磚紅字為通過條件")


def _is_command(text):
    heads = ("python ", "node ", "npm ", "git ", "grep ", "cat ", "claude ", "gh ")
    return text.startswith(heads)


def slide_step_pitfalls(b, step):
    data = step[b.version]
    eb = eyebrow_of(step, b.vname)
    items = list(data["pitfalls"])
    if b.version == "ai":
        items.insert(0, data["bad_evidence"])  # 一句話對照的實際同類問題
    pages = chunk_items(items, 12.13, CONTENT_BOTTOM - 1.94, size=17)
    for i, pg in enumerate(pages):
        sl = b.new()
        t = "實際踩過的坑" if len(pages) == 1 else "實際踩過的坑（%d／%d）" % (i + 1, len(pages))
        header(sl, eb, t, "本專案開發時真的發生過的問題，括號內為紀錄出處" if b.version == "ai"
               else "本專案開發時真的發生過的問題")
        bottom = bullets(sl, 0.6, 1.94, 12.13, pg, size=17)
        check_fit(bottom, "%s 坑" % step["id"])
        refline(sl, step_ref(step, ("ai.bad_evidence、pitfalls" if b.version == "ai" else "emba.pitfalls"))
                + ("（DEVLOG／progress ledger）" if b.version == "ai" else ""))
        first = pg[0].split("（")[0]
        b.done(sl, "這些都是本專案實際踩過的坑，不是假設；例如第一條：%s%s" % (
            first, "" if len(pages) == 1 else "（第 %d 頁，共 %d 頁）" % (i + 1, len(pages))),
            "條列為實際踩過的坑%s；內容取自 teaching/prompts.py 的 pitfalls 欄位" % (
                "，括號為 DEVLOG 或審查紀錄出處" if b.version == "ai" else ""))


def slide_step_shot(b, step, names, notes, speech):
    """App 實際截圖頁"""
    sl = b.new()
    header(sl, eyebrow_of(step, b.vname), "實際畫面", "本機預覽伺服器上實際操作後擷取")
    y = 1.84 + 0.1
    if len(names) == 2:
        w, gap = 5.25, 0.4
        x0 = (13.333 - 2 * w - gap) / 2
        b1 = shot(sl, asset(names[0]), x0, y, w, SHOTS[names[0]])
        if names[1] == "mobile_tvm":  # 直式手機截圖：同高度放右側
            b2 = _portrait(sl, asset(names[1]), x0 + w + gap, y, b1 - y, SHOTS[names[1]])
        else:
            b2 = shot(sl, asset(names[1]), x0 + w + gap, y, w, SHOTS[names[1]])
        bottom = paras(sl, 0.6, max(b1, b2) + 0.45, 12.13, notes, size=17)
    else:
        w = 7.2
        b1 = shot(sl, asset(names[0]), 0.6, y, w, SHOTS[names[0]])
        nb = paras(sl, 0.6 + w + 0.3, y, 12.73 - (0.6 + w + 0.3), notes, size=16)
        bottom = max(b1 + 0.36, nb)
    check_fit(bottom, "%s 截圖" % step["id"])
    refline(sl, SHOT_SRC)
    b.done(sl, speech, "App 實際截圖（Playwright 驅動 Chrome，在 localhost:8765 實際輸入後擷取）；"
                       "圖下為說明，旁邊或下方為讀圖重點")


def _portrait(sl, path, x, y, h, cap):
    """直式截圖（手機）：指定高度，回傳底部 y"""
    if os.path.exists(path):
        pic = sl.shapes.add_picture(path, In(x), In(y), height=In(h))
        pic.line.color.rgb = LINE
    else:
        shot(sl, path, x, y, h * 0.46, None, ratio=1 / 0.46)
    txt(sl, x, y + h + 0.06, 4.0, 0.3, [{"text": cap, "size": 16, "color": MUT}])
    return y + h


# 各步驟的截圖頁：step id → (截圖, 讀圖重點, 講稿)
STEP_SHOTS = {
    "step2": (["tvm_result"],
              ["N=360、I/Y=6、PV=300000、FV=0，PMT 留空", "按「計算」求出 1,798.65（付出）",
               ("與 Excel =PMT(0.06/12,360,300000) 一致",)],
              "這是 TVM 引擎接上畫面後的實際結果：房貸例題求出每月付款 1,798.65，紅色付出代表負號，"
              "和 Excel 的 PMT 一樣是 -1,798.65"),
    "step3": (["amort_table", "cf_irr"],
              ["攤還第 1～12 期利息 -17,899.78（=CUMIPMT）；現金流 NPV 282.77、IRR 11.52",
               ("IRR 有兩次正負號變化時，App 會提醒可能有多個解",)],
              "左邊是攤還，第一年利息 -17,899.78，和 Excel CUMIPMT 一樣；右邊是現金流，NPV 282.77、IRR 11.52%，"
              "因為現金流正負號變了兩次，App 會提醒 IRR 可能有多個解"),
    "step4": (["settings_about"],
              ["MicroPython 套件 1.29.0-6", "殼顯示約 0.5 秒、Python 就緒約 0.7 秒（本機）",
               ("數字隨機器而異，以實際畫面為準",)],
              "設定頁的「關於」區會顯示 MicroPython 版本與啟動時間；這次截圖時殼約 0.5 秒出現，Python 約 0.7 秒就緒，"
              "這是本機的數字，手機上會比較慢"),
    "step5": (["calc_tape", "mobile_tvm"],
              ["計算機的每一筆算式都進紙帶 Tape，點一下可帶回輸入框；手機版改成單欄與底部分頁列",
               ("說明裡的範例數字都由引擎實際算出，用測試鎖住",)],
              "左邊是計算機與紙帶，每算一次就留一筆紀錄；右邊是手機版，一欄往下排、底部有分頁列"),
    "step6": (["settings_about"],
              ["設定頁的匯出 JSON、匯入 JSON（合併／取代）", "Google Drive 同步區預設關閉",
               ("資料只存在本機 IndexedDB",)],
              "設定頁上方是匯出與匯入 JSON 的按鈕，匯入時可以選合併或取代；下方 Google Drive 同步預設是關閉的"),
    "step9": (["mobile_tvm"],
              ["手機寬度 375 px 的版面", "安裝到主畫面後可離線使用",
               ("此圖為桌面瀏覽器模擬手機寬度，手機實機與飛航模式由作者另行實測",)],
              "這張是用瀏覽器模擬手機寬度的截圖，不是手機實機；手機安裝與飛航模式要由作者親自測過才打 step9 tag"),
}


def slide_step_mobile(b, step, shot_spec):
    """手機直式截圖：左圖右文"""
    names, notes, speech = shot_spec
    sl = b.new()
    header(sl, eyebrow_of(step, b.vname), "實際畫面", "瀏覽器模擬手機寬度 375 px 後擷取")
    y = 1.94
    if os.path.exists(asset(names[0])):
        pic = sl.shapes.add_picture(asset(names[0]), In(0.9), In(y), height=In(4.1))
        pic.line.color.rgb = LINE
        pw = pic.width / 914400
    else:
        shot(sl, asset(names[0]), 0.9, y, 1.9, None, ratio=4.1 / 1.9)
        pw = 1.9
    txt(sl, 0.9, y + 4.15, 4.0, 0.3, [{"text": SHOTS[names[0]], "size": 16, "color": MUT}])
    nx = 0.9 + pw + 0.6
    bottom = paras(sl, nx, y, 12.73 - nx, notes, size=17)
    check_fit(max(bottom, y + 4.47), "%s 手機截圖" % step["id"])
    refline(sl, SHOT_SRC)
    b.done(sl, speech, "左為手機寬度截圖（Playwright 以 375×812 行動裝置模擬），右為讀圖重點")


def slides_for_step(b, step):
    slide_step_overview(b, step)
    slide_step_prompt(b, step)
    if b.version == "ai":
        slide_step_compare(b, step)
    slide_step_verify(b, step)
    spec = STEP_SHOTS.get(step["id"])
    if spec:
        if spec[0] == ["mobile_tvm"]:
            slide_step_mobile(b, step, spec)
        else:
            slide_step_shot(b, step, *spec)
    slide_step_pitfalls(b, step)


def slide_closing(b):
    if b.version == "ai":
        sl = closing(
            b.dk,
            "規則寫進 CLAUDE.md、Prompt 寫清楚四段、驗收要能執行",
            "課後練習",
            ["照 Prompt 卡重做任一步，貼出 RED 與 GREEN", "故意改壞一個公式，用 verify_all 抓出來",
             "把自己的通用習慣寫成 ~/.claude/CLAUDE.md"],
            "參考資料",
            ["Prompt卡_AI.html（teaching/out/）", "docs/spec-2026-10-19.md 第 5 節",
             "DEVLOG.md 每個 Task 的問題與修正"],
            "下一步：用同樣的方法做自己的專案，先寫 CLAUDE.md 與計畫")
    else:
        sl = closing(
            b.dk,
            "需求講清楚、例題附標準答案、對不上就附數字請 AI 修正",
            "課後練習",
            ["用 Excel 核對房貸、NPV、債券三題", "手機安裝 App，開飛航模式算一題",
             "替自己工作上的計算寫一份四段式需求"],
            "參考資料",
            ["Prompt卡_EMBA.html（teaching/out/）", "README.md 手機安裝步驟",
             "Excel：PMT、NPV、IRR、PRICE、SLN"],
            "下一步：挑一個工作上常算的公式，請 AI 做成自己的小工具")
    refline(sl, "teaching/prompts.py", "docs/spec-2026-10-19.md 第 5 節")
    footer_done = True  # closing() 已加頁尾
    b.notes.append((sl,
                    "最後總結：%s；課後練習請挑一項做，參考資料都在 teaching/out 的 Prompt 卡" % (
                        "規則寫進 CLAUDE.md、Prompt 分四段、驗收能執行，這三件事讓 AI 的產出可以被檢查"
                        if b.version == "ai" else
                        "把需求講清楚、例題附標準答案、對不上就附數字請 AI 修正，這三件事不需要會寫程式"),
                    "結論頁（closing）：上方深藍框為本課重點句，左為課後練習，右為參考資料，下方為下一步"))
    return footer_done


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------

def build(version, with_notes):
    """建置一份簡報，回傳 (路徑, 大小, 頁數, 清除句點數)"""
    b = Builder(version, with_notes)
    slide_cover(b)
    slide_agenda(b)
    slide_why(b)
    if version == "ai":
        slide_mvc(b)
    slide_four_part(b)
    if version == "emba":
        slide_emba_method(b)
    slide_claude_md(b)
    for step in prompts.STEPS:
        slides_for_step(b, step)
    slide_closing(b)
    name = VERSIONS[version]["out"] + ("_講稿" if with_notes else "") + ".pptx"
    path = os.path.join(OUT_DIR, name)
    size, total, n_strip = b.save(path)
    return path, size, total, n_strip


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    missing = [n for n in SHOTS if not os.path.exists(asset(n))]
    if missing:
        print("缺少截圖（以「[缺圖]」佔位框代替）：", ", ".join(missing))
    results = []
    for version in VERSIONS:
        for with_notes in (False, True):
            r = build(version, with_notes)
            results.append(r)
            print("寫入 %s（%d bytes，%d 頁，清除句點 %d 處）" % r)
    return results


if __name__ == "__main__":
    main()
