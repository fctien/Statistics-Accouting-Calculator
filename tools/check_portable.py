"""可攜性檢查：掃描 engine/ 是否使用 MicroPython 不支援的模組或 eval／exec。

本工具在 CPython 執行，因此可用 ast；被檢查的程式則須符合可攜子集。
用法：python tools/check_portable.py [目錄 ...，預設 engine]
有違規、或指定的目錄不存在（避免什麼都沒掃到就通過 vacuous pass）時 exit code 為 1。
"""
import ast
import os
import re
import sys

# 禁用模組（頂層名稱）
BANNED = ("decimal", "datetime", "ast", "fractions", "dataclasses",
          "typing", "functools")
# 允許的標準模組；其餘第三方套件由是否為本專案模組判斷
ALLOWED = ("math", "json", "engine")
_CALL_RE = re.compile(r"(?<![\w.])(eval|exec)\s*\(")
# 內建基底類別的 __init__（MicroPython 內建型別無 __init__ 屬性，須改用 super()）
_BASE_INIT_RE = re.compile(
    r"(?<![\w.])(object|Exception|BaseException|\w+Error|\w+Exception|dict|list)"
    r"\.__init__\s*\(")


def _check_module(name, path, lineno, out):
    top = name.split(".")[0]
    if top in BANNED:
        out.append("%s:%d 禁用模組 %s" % (path, lineno, top))
    elif top not in ALLOWED:
        out.append("%s:%d 不在可攜白名單的模組 %s" % (path, lineno, top))


def _scan_file(path, out):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    try:
        tree = ast.parse(src, path)
    except SyntaxError as e:
        out.append("%s:%s 語法錯誤 %s" % (path, e.lineno, e.msg))
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                _check_module(a.name, path, node.lineno, out)
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # 相對匯入屬本專案內部
                continue
            _check_module(node.module or "", path, node.lineno, out)
    for i, line in enumerate(src.splitlines(), 1):
        code = line.split("#", 1)[0]
        m = _CALL_RE.search(code)
        if m:
            out.append("%s:%d 禁用 %s()" % (path, i, m.group(1)))
        m = _BASE_INIT_RE.search(code)
        if m:
            out.append("%s:%d 禁用 %s.__init__（MicroPython 不支援，改用 super()）"
                       % (path, i, m.group(1)))


def scan(root):
    """掃描目錄下所有 .py，回傳違規訊息清單。"""
    out = []
    for dirpath, _dirs, files in os.walk(root):
        for name in sorted(files):
            if name.endswith(".py"):
                _scan_file(os.path.join(dirpath, name), out)
    return out


def main(argv):
    roots = argv[1:] or ["engine"]
    missing = [r for r in roots if not os.path.isdir(r)]
    if missing:
        for r in missing:
            print("目錄不存在，無法檢查：%s" % r)
        return 1
    problems = []
    for root in roots:
        problems.extend(scan(root))
    for p in problems:
        print(p)
    if problems:
        return 1
    print("可攜性檢查通過：%s" % " ".join(roots))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
