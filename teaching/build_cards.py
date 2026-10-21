"""Prompt 卡產生器（generator）：由單一來源 teaching/prompts.py 產生兩份單一 HTML

產出
- teaching/out/Prompt卡_AI.html：AI Agent 版（四段式 Prompt、驗收指令、實際踩過的坑、git tag）
- teaching/out/Prompt卡_EMBA.html：EMBA 版（白話 Prompt、用 Excel／BA II Plus 對答案、起點 tag）

每個步驟一張卡：目標／Prompt 原文（複製按鈕）／預期產出／驗收／常見坑／tag
可列印：@media print 每張卡一頁；顏色用 CSS 變數（token），支援深色與淺色；不載入任何外部網路資源

分層（MVC）
- Model：teaching.prompts（STEPS、USER_CLAUDE_MD、PROJECT_CLAUDE_MD）
- View：本檔的 render_* 函式，只把資料轉成 HTML 字串
- Controller：main()，決定版本與輸出路徑並寫檔

用法：python teaching/build_cards.py（在 BACalc 根目錄執行）
"""
import html
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from teaching import prompts  # noqa: E402  Model：單一來源

OUT_DIR = os.path.join(HERE, "out")
OUTPUTS = {"ai": "Prompt卡_AI.html", "emba": "Prompt卡_EMBA.html"}
TITLES = {
    "ai": "BACalc Prompt 卡（AI Agent 版）",
    "emba": "BACalc Prompt 卡（EMBA 版）",
}
OPTIONAL_NOTE = "選用，作者未實測"

CSS = """
:root {
  --bg: #faf8f5; --card: #ffffff; --ink: #1d1c1a; --muted: #5a5751; --line: #d8d4cc;
  --navy: #1f3a5f; --brick: #c0562f; --soft: #f4f1ec; --code-bg: #262b33; --code-ink: #e8e4dc;
  --ok: #3f6b5c; --warn-bg: #fbeee6;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #15181d; --card: #1e232a; --ink: #ece8e1; --muted: #a9a49b; --line: #3a4049;
    --navy: #9fbadb; --brick: #e8946f; --soft: #262c34; --code-bg: #0f1216; --code-ink: #e8e4dc;
    --ok: #8cc2ad; --warn-bg: #3a2a22;
  }
}
:root[data-theme="dark"] {
  --bg: #15181d; --card: #1e232a; --ink: #ece8e1; --muted: #a9a49b; --line: #3a4049;
  --navy: #9fbadb; --brick: #e8946f; --soft: #262c34; --code-bg: #0f1216; --code-ink: #e8e4dc;
  --ok: #8cc2ad; --warn-bg: #3a2a22;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--ink);
  font-family: "Microsoft JhengHei", "微軟正黑體", "Segoe UI", system-ui, sans-serif;
  font-size: 17px; line-height: 1.6;
}
header.top { max-width: 960px; margin: 0 auto; padding: 24px 16px 8px; }
header.top h1 { color: var(--navy); font-size: 28px; margin: 0 0 4px; }
header.top p { color: var(--muted); margin: 4px 0; }
.toolbar { display: flex; gap: 8px; flex-wrap: wrap; margin: 12px 0; }
nav.toc { display: flex; flex-wrap: wrap; gap: 6px; margin: 8px 0 0; }
nav.toc a { color: var(--navy); border: 1px solid var(--line); border-radius: 6px; padding: 2px 8px;
  text-decoration: none; font-size: 15px; background: var(--card); }
main { max-width: 960px; margin: 0 auto; padding: 0 16px 40px; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 12px;
  padding: 20px 22px; margin: 18px 0; }
.card h2 { color: var(--navy); margin: 0 0 4px; font-size: 24px; }
.eyebrow { color: var(--brick); font-weight: bold; font-size: 15px; letter-spacing: .02em; }
.badge { display: inline-block; border-radius: 6px; padding: 1px 8px; font-size: 14px;
  background: var(--soft); border: 1px solid var(--line); color: var(--muted); margin-left: 6px; }
.badge.optional { background: var(--warn-bg); color: var(--brick); border-color: var(--brick); }
.card h3 { font-size: 17px; color: var(--brick); margin: 16px 0 6px; }
.card p, .card li { margin: 4px 0; }
.card ul, .card ol { padding-left: 22px; margin: 4px 0; }
.prompt-wrap { position: relative; }
pre { background: var(--code-bg); color: var(--code-ink); border-radius: 8px; padding: 14px 16px;
  white-space: pre-wrap; word-break: break-word; font-family: Consolas, "Microsoft JhengHei", monospace;
  font-size: 15px; line-height: 1.55; margin: 6px 0; }
code { font-family: Consolas, monospace; background: var(--soft); border-radius: 4px; padding: 0 4px; }
li code { word-break: break-all; }
button { font: inherit; font-size: 15px; cursor: pointer; border-radius: 8px; padding: 4px 12px;
  border: 1px solid var(--navy); background: var(--card); color: var(--navy); }
button.copy { position: absolute; top: 8px; right: 8px; }
button.copied { background: var(--ok); color: #fff; border-color: var(--ok); }
.compare { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.compare > div { background: var(--soft); border: 1px solid var(--line); border-radius: 8px; padding: 10px 12px; }
.compare .label { font-weight: bold; color: var(--navy); }
.guess { color: var(--brick); font-weight: bold; }
.tagline { margin-top: 14px; padding-top: 10px; border-top: 1px dashed var(--line); color: var(--muted); }
@media (max-width: 640px) {
  .compare { grid-template-columns: 1fr; }
  .card { padding: 16px 14px; }
  button.copy { position: static; margin-bottom: 4px; }
}
@media print {
  :root, :root[data-theme="dark"] {
    --bg: #fff; --card: #fff; --ink: #000; --muted: #333; --line: #999; --navy: #1f3a5f;
    --brick: #a0401f; --soft: #f4f4f4; --code-bg: #f4f4f4; --code-ink: #000; --warn-bg: #fff;
  }
  @page { size: A4; margin: 12mm; }
  body { font-size: 10.5pt; line-height: 1.45; }
  .card h2 { font-size: 16pt; }
  .card h3 { font-size: 11pt; margin: 8px 0 3px; }
  header.top { padding: 0 0 6px; }
  header.top .toolbar, nav.toc, button { display: none !important; }
  .card { break-after: page; page-break-after: always; border: none; margin: 0; padding: 0; }
  .card:last-child { break-after: auto; page-break-after: auto; }
  pre { border: 1px solid #999; font-size: 9.5pt; line-height: 1.4; padding: 8px 10px; }
}
"""

JS = """
(function () {
  // 複製按鈕：優先用 Clipboard API，不支援時退回 textarea＋execCommand
  function copyText(text, btn) {
    function done() {
      var old = btn.textContent; btn.textContent = '已複製'; btn.classList.add('copied');
      setTimeout(function () { btn.textContent = old; btn.classList.remove('copied'); }, 1500);
    }
    function fallback() {
      var ta = document.createElement('textarea'); ta.value = text; document.body.appendChild(ta);
      ta.select(); try { document.execCommand('copy'); done(); } catch (e) { btn.textContent = '請手動選取'; }
      document.body.removeChild(ta);
    }
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(done, fallback);
    } else { fallback(); }
  }
  document.querySelectorAll('button.copy').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var pre = document.getElementById(btn.getAttribute('data-target'));
      copyText(pre.textContent, btn);
    });
  });
  // 主題切換：只存在本機 localStorage，讀寫失敗就忽略
  var root = document.documentElement, KEY = 'bacalc.cards.theme';
  try { var t = localStorage.getItem(KEY); if (t) root.setAttribute('data-theme', t); } catch (e) {}
  var tb = document.getElementById('theme-toggle');
  if (tb) tb.addEventListener('click', function () {
    var dark = root.getAttribute('data-theme') === 'dark' ||
      (!root.getAttribute('data-theme') && matchMedia('(prefers-color-scheme: dark)').matches);
    var next = dark ? 'light' : 'dark'; root.setAttribute('data-theme', next);
    try { localStorage.setItem(KEY, next); } catch (e) {}
  });
  var pb = document.getElementById('print-btn');
  if (pb) pb.addEventListener('click', function () { window.print(); });
})();
"""


def esc(text):
    """HTML 跳脫（escape）"""
    return html.escape(text, quote=True)


def render_list(items, code=False):
    """清單；AI 版驗收是指令，用 <code> 包起來"""
    if code:
        lis = "".join("<li><code>%s</code></li>" % esc(x) if _looks_like_command(x)
                      else "<li>%s</li>" % esc(x) for x in items)
    else:
        lis = "".join("<li>%s</li>" % esc(x) for x in items)
    return "<ul>%s</ul>" % lis


def _looks_like_command(text):
    """判斷一行驗收是否為終端機指令（command）"""
    heads = ("python ", "node ", "npm ", "git ", "grep ", "cat ", "claude ", "gh ")
    return text.startswith(heads)


def render_prompt(pre_id, text):
    """Prompt 原文＋複製按鈕"""
    return ('<div class="prompt-wrap"><button type="button" class="copy" data-target="%s">複製 Prompt</button>'
            '<pre id="%s">%s</pre></div>') % (pre_id, pre_id, esc(text))


def existing_tags():
    """讀 repo 現有的 step* tag；讀不到（例如沒有 git）回 None，表示不加註"""
    try:
        p = subprocess.run(["git", "tag", "-l", "step*"], cwd=ROOT, capture_output=True,
                           text=True, encoding="utf-8")
    except OSError:
        return None
    return set(p.stdout.split()) if p.returncode == 0 else None


TAGS = existing_tags()


def tag_note(tag):
    """tag 尚未建立時加註（例如 step9 要等部署與手機實測後才打）"""
    if TAGS is not None and tag not in TAGS:
        return "（此 tag 尚未建立，作者完成實測後才會打）"
    return ""


def tag_line(step, version):
    """tag 說明列"""
    if version == "ai":
        if step["tag"]:
            return "完成後對照參考答案：<code>git checkout %s</code>%s" % (
                esc(step["tag"]), tag_note(step["tag"]))
        return "沒有 git tag（%s）" % OPTIONAL_NOTE
    start = step["emba"]["start_tag"]
    if step["tag"]:
        end = "完成後的參考答案 tag：<code>%s</code>%s" % (esc(step["tag"]), tag_note(step["tag"]))
    else:
        end = "沒有完成 tag（%s）" % OPTIONAL_NOTE
    return "從這裡接手：<code>git checkout %s</code>　·　%s" % (esc(start), end)


def render_step(step, version):
    """一個步驟一張卡"""
    sid = step["id"]
    data = step[version]
    badge = '<span class="badge">%s</span>' % esc(sid)
    if step.get("optional"):
        badge += '<span class="badge optional">%s</span>' % OPTIONAL_NOTE
    parts = [
        '<section class="card" id="%s" data-step="%s">' % (sid, sid),
        '<div class="eyebrow">%s %s</div>' % (esc(sid.upper().replace("STEP", "Step ")), badge),
        "<h2>%s</h2>" % esc(step["title"]),
        "<h3>目標</h3><p>%s</p>" % esc(step["goal"]).replace("\n", "<br>"),
        "<h3>Prompt 原文</h3>",
        render_prompt("prompt-%s" % sid, data["prompt"]),
    ]
    if version == "ai":
        parts.append(
            '<h3>一句話下法對照</h3><div class="compare">'
            '<div><div class="label">一句話下法</div><p><code>%s</code></p>'
            '<p><span class="guess">推測（未實測）</span>%s</p></div>'
            '<div><div class="label">本專案實際發生</div><p>%s</p></div></div>'
            % (esc(data["bad_prompt"]), esc(_strip_prefix(data["bad_result"], "推測：")),
               esc(data["bad_evidence"])))
    parts += [
        "<h3>預期產出</h3><p>%s</p>" % esc(data["expected"]),
        "<h3>驗收</h3>%s" % render_list(data["verify"], code=(version == "ai")),
        "<h3>常見坑（實際踩過）</h3>%s" % render_list(data["pitfalls"]),
        '<p class="tagline">%s</p>' % tag_line(step, version),
        "</section>",
    ]
    return "\n".join(parts)


def _strip_prefix(text, prefix):
    return text[len(prefix):] if text.startswith(prefix) else text


def render_claude_md_card():
    """開頭的兩層 CLAUDE.md 卡"""
    return "\n".join([
        '<section class="card" id="claude-md" data-step="claude-md">',
        '<div class="eyebrow">開始之前</div>',
        "<h2>兩層 CLAUDE.md 範本</h2>",
        "<p>使用者層級（~/.claude/CLAUDE.md）放個人通用習慣，所有專案共用；"
        "專案層級（專案根目錄 CLAUDE.md）放這個專案的規則</p>",
        "<h3>使用者層級 USER_CLAUDE_MD</h3>",
        render_prompt("user-claude-md", prompts.USER_CLAUDE_MD),
        "<h3>專案層級 PROJECT_CLAUDE_MD</h3>",
        render_prompt("project-claude-md", prompts.PROJECT_CLAUDE_MD),
        "</section>",
    ])


def render_page(version):
    """整頁 HTML（單一檔案，CSS 與 JS 內嵌）"""
    title = TITLES[version]
    if version == "ai":
        intro = ("對象：會基本 Python、第一次用 Claude Code 做完整專案；每一步照卡片下 Prompt，"
                 "跑完驗收指令，再用 git tag 對照參考答案")
    else:
        intro = ("對象：商管背景、幾乎不寫程式；每一步從起點 tag 接手，只下該步的關鍵 Prompt，"
                 "再用 Excel 或 BA II Plus 對答案")
    toc = "".join('<a href="#%s">%s</a>' % (s["id"], esc(s["id"])) for s in prompts.STEPS)
    cards = [render_claude_md_card()] + [render_step(s, version) for s in prompts.STEPS]
    return "\n".join([
        "<!doctype html>",
        '<html lang="zh-Hant"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>%s</title>" % esc(title),
        "<style>%s</style></head><body>" % CSS,
        '<header class="top"><h1>%s</h1><p>%s</p>' % (esc(title), esc(intro)),
        "<p>由 teaching/prompts.py 產生（python teaching/build_cards.py），請勿手改本檔</p>",
        '<div class="toolbar"><button type="button" id="print-btn">列印（每張卡一頁）</button>'
        '<button type="button" id="theme-toggle">切換深色／淺色</button></div>',
        '<nav class="toc" aria-label="步驟">%s</nav></header>' % toc,
        "<main>",
        "\n".join(cards),
        "</main>",
        "<script>%s</script>" % JS,
        "</body></html>",
    ])


def main():
    """Controller：產生兩份 Prompt 卡"""
    os.makedirs(OUT_DIR, exist_ok=True)
    paths = []
    for version, name in OUTPUTS.items():
        path = os.path.join(OUT_DIR, name)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(render_page(version))
        paths.append(path)
        print("寫入", path, os.path.getsize(path), "bytes")
    return paths


if __name__ == "__main__":
    main()
