"""教材產出（teaching/out/）的自測：Prompt 卡 HTML 與四份簡報

檢查（python-pptx 讀回）
- 字級：每個 run 都 ≥ 14 pt；Prompt／程式碼框（Consolas）以外 ≥ 16 pt
- 投影片文字與備忘稿都沒有全形句點「。」
- 講稿版每一頁都有備忘稿，且同時含【講稿】與【投影片說明】
- 頁數涵蓋 10 個步驟：每個步驟至少一頁、每頁 eyebrow 標示的步驟齊全；step7 頁面標示「選用，作者未實測」
- 每個步驟的 Prompt 原文（逐行）都出現在對應版本的簡報中
- Prompt 卡含每個步驟 id 與 Prompt 原文，且不引用外部網路資源

teaching/out/ 的檔案由 python teaching/build_cards.py 與 python teaching/deck/build_deck.py 產生；
檔案不存在時（例如 CI 不建置簡報）整組略過並說明原因
"""
import html
import os
import re

import pytest

from teaching import prompts

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.environ.get("BACALC_TEACHING_OUT", os.path.join(ROOT, "teaching", "out", "v0.2"))
DECKS = {
    "ai": ["BACalc_AI.pptx", "BACalc_AI_講稿.pptx"],
    "emba": ["BACalc_EMBA.pptx", "BACalc_EMBA_講稿.pptx"],
}
CARDS = {"ai": "Prompt卡_AI.html", "emba": "Prompt卡_EMBA.html"}
CODE_FONT = "Consolas"
STEP_IDS = [s["id"] for s in prompts.STEPS]


def _path(name):
    p = os.path.join(OUT, name)
    if not os.path.exists(p):
        pytest.skip("teaching/out/%s 不存在（CI 不建置教材；本機請先跑 build_cards.py 與 build_deck.py）" % name)
    return p


def _open(name):
    pptx = pytest.importorskip("pptx", reason="需要 python-pptx 讀回簡報")
    return pptx.Presentation(_path(name))


def _runs(prs):
    """逐一產生 (頁碼, run)；含表格儲存格"""
    for i, sl in enumerate(prs.slides, 1):
        for sh in sl.shapes:
            frames = []
            if sh.has_text_frame:
                frames.append(sh.text_frame)
            if getattr(sh, "has_table", False) and sh.has_table:
                frames += [c.text_frame for row in sh.table.rows for c in row.cells]
            for tf in frames:
                for p in tf.paragraphs:
                    for r in p.runs:
                        yield i, r


def _slide_text(sl):
    parts = []
    for sh in sl.shapes:
        if sh.has_text_frame:
            parts.append("\n".join(p.text for p in sh.text_frame.paragraphs))
    return "\n".join(parts)


ALL_DECKS = [n for names in DECKS.values() for n in names]


@pytest.mark.parametrize("name", ALL_DECKS)
def test_font_sizes(name):
    prs = _open(name)
    bad = []
    for i, r in _runs(prs):
        if not r.text.strip():
            continue
        size = r.font.size.pt if r.font.size is not None else None
        floor = 14 if r.font.name == CODE_FONT else 16
        if size is None or size < floor:
            bad.append((i, r.text[:20], size, r.font.name))
    assert not bad, "字級低於下限（Consolas ≥ 14、其他 ≥ 16）：%s" % bad[:10]


@pytest.mark.parametrize("name", ALL_DECKS)
def test_no_full_width_period(name):
    prs = _open(name)
    bad = [i for i, r in _runs(prs) if "。" in r.text]
    for i, sl in enumerate(prs.slides, 1):
        if sl.has_notes_slide and "。" in sl.notes_slide.notes_text_frame.text:
            bad.append(("notes", i))
    assert not bad, "含全形句點「。」的頁：%s" % bad[:10]


@pytest.mark.parametrize("name", [n for n in ALL_DECKS if "講稿" in n])
def test_notes_have_both_sections(name):
    prs = _open(name)
    bad = []
    for i, sl in enumerate(prs.slides, 1):
        text = sl.notes_slide.notes_text_frame.text if sl.has_notes_slide else ""
        if "【講稿】" not in text or "【投影片說明】" not in text:
            bad.append(i)
        elif len(text.replace("【講稿】", "").replace("【投影片說明】", "").strip()) < 20:
            bad.append(i)
    assert not bad, "備忘稿缺【講稿】或【投影片說明】的頁：%s" % bad


@pytest.mark.parametrize("version", list(DECKS))
def test_slides_cover_all_steps(version):
    prs = _open(DECKS[version][0])
    seen = {}
    for i, sl in enumerate(prs.slides, 1):
        m = re.search(r"Step (\d+) · ", _slide_text(sl))
        if m:
            seen.setdefault("step" + m.group(1), []).append(i)
    assert sorted(seen, key=lambda k: int(k[4:])) == STEP_IDS, "缺少步驟頁：%s" % sorted(set(STEP_IDS) - set(seen))
    # 每步至少：概觀、Prompt、驗收、坑 四頁（AI 版另有一句話對照）
    least = 5 if version == "ai" else 4
    few = {k: len(v) for k, v in seen.items() if len(v) < least}
    assert not few, "頁數不足的步驟：%s" % few
    assert len(prs.slides) >= 10 * least + 2
    # step7 每頁都標示選用、未實測
    for i in seen["step7"]:
        assert "選用，作者未實測" in _slide_text(prs.slides[i - 1]), "step7 第 %d 頁未標示" % i


@pytest.mark.parametrize("version", list(DECKS))
def test_each_prompt_in_deck(version):
    prs = _open(DECKS[version][0])
    deck_lines = set()
    for sl in prs.slides:
        for line in _slide_text(sl).splitlines():
            deck_lines.add(line.strip())
    missing = []
    for s in prompts.STEPS:
        for line in s[version]["prompt"].splitlines():
            if line.strip() and line.strip() not in deck_lines:
                missing.append((s["id"], line[:30]))
    assert not missing, "簡報中找不到的 Prompt 行：%s" % missing[:10]


@pytest.mark.parametrize("version", list(DECKS))
def test_notes_version_matches_plain(version):
    """講稿版與一般版頁數、投影片文字相同（只多備忘稿）"""
    plain, noted = _open(DECKS[version][0]), _open(DECKS[version][1])
    assert len(plain.slides) == len(noted.slides)
    for a, b in zip(plain.slides, noted.slides):
        assert _slide_text(a) == _slide_text(b)


@pytest.mark.parametrize("version", list(CARDS))
def test_cards_contain_every_step(version):
    with open(_path(CARDS[version]), encoding="utf-8") as f:
        page = f.read()
    for s in prompts.STEPS:
        assert 'data-step="%s"' % s["id"] in page, s["id"]
        assert html.escape(s[version]["prompt"], quote=True) in page, "%s Prompt 原文" % s["id"]
    assert page.count('class="copy"') >= len(STEP_IDS)
    assert "@media print" in page and "prefers-color-scheme: dark" in page
    # 不載入外部資源：沒有 <script src>、<link href>、<img src> 指向網路
    assert not re.search(r'<(script|img|iframe)[^>]+src=["\']?https?:', page)
    assert not re.search(r'<link[^>]+href=["\']?https?:', page)
    assert "@import" not in page
