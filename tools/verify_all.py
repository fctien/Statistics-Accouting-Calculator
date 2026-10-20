"""一鍵驗證（one-command verification）：依序執行全部檢查並產生 HTML log。

用法：
    python tools/verify_all.py            完整驗證（含突變測試 mutate，最慢）
    python tools/verify_all.py --quick    略過 mutate（log 會註明「未執行」，不可當作完整驗證）
    python tools/verify_all.py --allow-dirty
        僅供示範（例如故意弄壞程式看驗證會失敗）：略過 git 乾淨檢查，
        log 標題標示「DIRTY — 不可作為實驗紀錄」。正式驗證不要用。

步驟順序：git 乾淨檢查 → check_portable → pytest → build_web --check → check_shell
→ JS 單元測試 → check_worker → test:mpy → test:mpy --self-test → mutate。
git 不乾淨就立刻 exit 1（專案規則：跑之前 git 必須乾淨）；其餘步驟某項失敗仍會繼續跑完，
讓 log 一次呈現全部結果。任何一項失敗 → exit 1。

log 寫到 logs/verify-YYYYMMDD-HHMM.html。乾淨檢查在寫 log「之前」，所以不會被自己弄髒；
log 是要 commit 的產物，使用者把它當作工作流程的一部分一起提交（commit 後再跑下一次）。
"""
import argparse
import glob
import html
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAIL_LINES = 60  # 失敗時 log 保留的輸出行數
TZ = timezone(timedelta(hours=8))  # 台灣時間 +08:00


def run_cmd(cmd):
    """執行指令；輸出以 UTF-8 解碼（errors="replace"），避免 cp950 主控台崩潰。

    回傳 (結束碼, 合併輸出文字)。
    """
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    try:
        p = subprocess.run(cmd, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except OSError as e:  # 找不到執行檔等
        return 127, "無法執行 %r：%s" % (cmd[0], e)
    return p.returncode, p.stdout.decode("utf-8", errors="replace")


def git(*args):
    """執行 git 並回傳去尾空白的輸出。"""
    return run_cmd(["git"] + list(args))[1].strip()


def build_steps(node, quick):
    """回傳 [(名稱, 指令 list)]；mutate 在 --quick 時不列入。"""
    py = sys.executable
    js_tests = sorted(glob.glob(os.path.join(ROOT, "tests", "js", "*.test.mjs")))
    steps = [
        ("check_portable（engine 可攜性）", [py, "tools/check_portable.py", "engine"]),
        ("pytest（含 golden）", [py, "-m", "pytest"]),
        ("build_web --check", [py, "tools/build_web.py", "--check"]),
        ("check_shell（PWA 殼）", [py, "tools/check_shell.py"]),
        ("JS 單元測試（node --test）", [node, "--test"] + js_tests),
        ("check_worker（Worker 佇列與 golden）", [node, "tools/check_worker.mjs"]),
        ("test:mpy（MicroPython golden）", [node, "tools/run_mpy_golden.mjs"]),
        ("test:mpy --self-test", [node, "tools/run_mpy_golden.mjs", "--self-test"]),
    ]
    if not quick:
        steps.append(("mutate（突變測試）", [py, "tools/mutate.py"]))
    return steps


def mpy_version():
    """MicroPython WebAssembly 套件版本（node_modules 內的 package.json）。"""
    path = os.path.join(ROOT, "node_modules", "@micropython",
                        "micropython-webassembly-pyscript", "package.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("version", "?")
    except (OSError, ValueError):
        return "未安裝"


def shell_hash():
    """sw.js 中的 SHELL_HASH。"""
    try:
        with open(os.path.join(ROOT, "web", "sw.js"), encoding="utf-8") as f:
            m = re.search(r'const SHELL_HASH = "([^"]*)"', f.read())
        return m.group(1) if m else "?"
    except OSError:
        return "?"


CSS = """:root{--bg:#fff;--fg:#1d2330;--line:#d9dee7;--ok:#0a7a3d;--ng:#b3261e;--code:#f3f5f9}
@media (prefers-color-scheme: dark){:root{--bg:#14171c;--fg:#e6e9ef;--line:#2c323c;--ok:#5fd18f;--ng:#ff8a80;--code:#1d2129}}
body{background:var(--bg);color:var(--fg);font:15px/1.6 system-ui,"Microsoft JhengHei",sans-serif;margin:0;padding:16px;max-width:1200px}
table{border-collapse:collapse;width:100%;font-size:13px}td,th{border:1px solid var(--line);padding:4px 6px;vertical-align:top;text-align:left}
code,pre{background:var(--code);font-family:Consolas,monospace}pre{margin:0;white-space:pre-wrap;font-size:12px}
.ok{color:var(--ok);font-weight:600}.ng{color:var(--ng);font-weight:600}"""


def render(meta, results, skipped, summary_ok, title):
    """組出 HTML 字串。results: [(名稱, 指令文字, 結束碼, 秒, 輸出)]。"""
    e = html.escape
    rows = []
    for name, cmd, code, secs, out in results:
        ok = code == 0
        tail = "" if ok else "\n".join(out.splitlines()[-TAIL_LINES:])
        if ok:
            tail = "\n".join(out.splitlines()[-3:])  # 通過時只留末 3 行當佐證
        rows.append(
            "<tr><td>%s</td><td><code>%s</code></td><td class=%s>%s</td>"
            "<td>%.1f 秒</td><td><pre>%s</pre></td></tr>"
            % (e(name), e(cmd), "ok" if ok else "ng",
               "PASS" if ok else "FAIL（exit %d）" % code, secs, e(tail)))
    for name in skipped:
        rows.append("<tr><td>%s</td><td>—</td><td>未執行</td><td>—</td>"
                    "<td>--quick：略過，不是完整驗證</td></tr>" % e(name))
    n_fail = sum(1 for r in results if r[2] != 0)
    if summary_ok:
        line = "總結：PASS（%d 項全過%s）" % (
            len(results), "；mutate 未執行（--quick）" if skipped else "")
    else:
        line = "總結：FAIL（%d 項失敗 / 共執行 %d 項）" % (n_fail, len(results))
    meta_rows = "".join("<tr><th>%s</th><td>%s</td></tr>" % (e(k), e(v))
                        for k, v in meta)
    return (
        '<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>%s</title><style>%s</style></head><body><h1>%s</h1>"
        "<p class=%s>%s</p><table>%s</table><h2>各項結果</h2>"
        "<table><tr><th>項目</th><th>指令</th><th>結果</th><th>耗時</th>"
        "<th>輸出（通過＝末 3 行；失敗＝末 %d 行）</th></tr>%s</table>"
        "</body></html>"
        % (e(title), CSS, e(title), "ok" if summary_ok else "ng", e(line),
           meta_rows, TAIL_LINES, "".join(rows)))


def main(argv=None):
    ap = argparse.ArgumentParser(description="BACalc 一鍵驗證")
    ap.add_argument("--quick", action="store_true", help="略過 mutate")
    ap.add_argument("--allow-dirty", action="store_true",
                    help="僅供示範：略過 git 乾淨檢查，log 標示 DIRTY")
    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):  # cp950 主控台印不出的字元以 ? 取代，不崩潰
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")

    dirty = git("status", "--porcelain")
    if dirty and not args.allow_dirty:
        print("git 不乾淨，拒絕驗證（請先 commit 或還原）：\n" + dirty)
        return 1
    node = shutil.which("node")
    if not node:
        print("找不到 node，無法執行 JS 相關檢查")
        return 1

    started = datetime.now(TZ)
    results = []
    for name, cmd in build_steps(node, args.quick):
        print("==> %s" % name, flush=True)
        t0 = time.time()
        code, out = run_cmd(cmd)
        secs = time.time() - t0
        print("    %s（%.1f 秒）" % ("PASS" if code == 0 else "FAIL", secs),
              flush=True)
        shown = " ".join(os.path.basename(c) if i == 0 else c
                         for i, c in enumerate(cmd))
        if len(shown) > 200:  # JS 測試檔清單很長，縮短顯示
            shown = shown[:120] + " … tests/js/*.test.mjs"
        results.append((name, shown, code, secs, out))

    ok = all(r[2] == 0 for r in results)
    full = git("rev-parse", "HEAD")
    meta = [
        ("時間", started.strftime("%Y-%m-%d %H:%M:%S +08:00")),
        ("commit", "%s（短碼 %s）" % (full, full[:7])),
        ("分支", git("rev-parse", "--abbrev-ref", "HEAD")),
        ("git 狀態", "DIRTY（--allow-dirty，略過乾淨檢查）" if dirty
         else "乾淨（執行前 git status --porcelain 為空）"),
        ("Python", sys.version.split()[0]),
        ("Node", run_cmd([node, "--version"])[1].strip()),
        ("MicroPython 套件", mpy_version()),
        ("SHELL_HASH", shell_hash()),
        ("模式", "quick（略過 mutate）" if args.quick else "完整"),
    ]
    title = "BACalc 一鍵驗證"
    if dirty:
        title += " — DIRTY — 不可作為實驗紀錄"
    skipped = ["mutate（突變測試）"] if args.quick else []
    page = render(meta, results, skipped, ok, title)

    os.makedirs(os.path.join(ROOT, "logs"), exist_ok=True)
    path = os.path.join(ROOT, "logs",
                        "verify-%s.html" % started.strftime("%Y%m%d-%H%M"))
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)
    print("log：%s" % path)
    print("結果：%s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
