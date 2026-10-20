"""檢查 PWA 殼（app shell）：web/ 檔案與 sw.js 的 APP_SHELL 一致、版本號同步。

規則：
    1. web/ 下每個檔案（OS 雜檔除外）都必須列在 APP_SHELL
    2. APP_SHELL 每一項都必須存在（"./" 對應 index.html），且為相對網址、不重複
    3. sw.js 的 CACHE_VERSION 必須等於 "bacalc-v" + app.js 的 APP_VERSION
    4. sw.js 的 SHELL_HASH 必須等於 APP_SHELL 檔案內容的雜湊（shell_hash）；
       任何殼檔案改變 → SHELL_HASH 改變 → sw.js 位元組改變 → 瀏覽器安裝新 SW
web/py/ 由 tools/build_web.py 產生；尚未建置時回報「請先執行 build_web.py」，並略過 py/ 項目。
因此請在 build_web.py 之後執行。
用法：python tools/check_shell.py [web 目錄，預設 web]；有違規 exit 1。
"""
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OS_JUNK = {"Thumbs.db", "desktop.ini", ".DS_Store"}
_SHELL_RE = re.compile(r"const APP_SHELL = \[(.*?)\];", re.S)
_CACHE_RE = re.compile(r'const CACHE_VERSION = "([^"]*)";')
_APP_RE = re.compile(r'export const APP_VERSION = "([^"]*)";')
SHELL_HASH_RE = re.compile(r'(const SHELL_HASH = ")([^"]*)(";)')
HASH_LEN = 16  # SHA-256 取前 16 個十六進位字元


def _is_junk(path):
    return path.name in OS_JUNK or path.name.endswith("~") or \
        "__pycache__" in path.parts


def parse_app_shell(text):
    """從 sw.js 文字解析 APP_SHELL，回傳字串 list（去掉 // 註解）。"""
    m = _SHELL_RE.search(text)
    if not m:
        raise ValueError("sw.js 找不到 const APP_SHELL = [...]")
    body = "\n".join(re.sub(r"^\s*//.*$", "", line)
                     for line in m.group(1).splitlines())
    return re.findall(r'"([^"]*)"', body)


def read_app_shell(web_dir):
    """從 web_dir/sw.js 解析 APP_SHELL。"""
    return parse_app_shell(
        (Path(web_dir) / "sw.js").read_text(encoding="utf-8"))


def shell_hash(web_dir, entries, overrides=None):
    """APP_SHELL 檔案內容的 SHA-256（前 HASH_LEN 字元）。

    依路徑排序，每檔雜湊「路徑、NUL、長度、NUL、位元組（CRLF→LF）」；略過 "./"（＝index.html）
    與 sw.js 本身。overrides={相對路徑: bytes} 優先於磁碟（build_web 尚未寫檔時用）；
    不存在的檔案略過（由 check 另行回報）。
    """
    web = Path(web_dir)
    overrides = overrides or {}
    h = hashlib.sha256()
    for rel in sorted(set(entries) - {"./", "sw.js"}):
        if rel in overrides:
            data = overrides[rel]
        elif (web / rel).is_file():
            data = (web / rel).read_bytes()
        else:
            continue
        # 換行正規化：Windows（core.autocrlf，CRLF）與 CI（LF）算出相同雜湊
        data = data.replace(b"\r\n", b"\n")
        h.update(rel.encode("utf-8") + b"\0" + str(len(data)).encode()
                 + b"\0" + data)
    return h.hexdigest()[:HASH_LEN]


def read_shell_hash(web_dir):
    """回傳 sw.js 中的 SHELL_HASH；找不到為 None。"""
    m = SHELL_HASH_RE.search(
        (Path(web_dir) / "sw.js").read_text(encoding="utf-8"))
    return m.group(2) if m else None


def read_versions(web_dir):
    """回傳 (CACHE_VERSION, APP_VERSION)；找不到的為 None。"""
    web = Path(web_dir)
    sw = _CACHE_RE.search((web / "sw.js").read_text(encoding="utf-8"))
    app = _APP_RE.search((web / "js" / "app.js").read_text(encoding="utf-8"))
    return (sw.group(1) if sw else None, app.group(1) if app else None)


def check(web_dir):
    """回傳違規訊息 list（空 list 表示通過）。"""
    web = Path(web_dir)
    msgs = []
    built = (web / "py" / "manifest.json").is_file()
    if not built:
        msgs.append("web/py 尚未建置：請先執行 python tools/build_web.py")
    try:
        shell = read_app_shell(web)
    except (OSError, ValueError) as e:
        return msgs + [str(e)]

    seen = set()
    for entry in shell:
        if entry in seen:
            msgs.append("APP_SHELL 重複：%s" % entry)
        seen.add(entry)
        if entry.startswith("/") or "://" in entry or entry.startswith(".."):
            msgs.append("APP_SHELL 必須是 web/ 內的相對網址：%s" % entry)
            continue
        if entry == "./":
            target = web / "index.html"
        else:
            target = web / entry
        if not built and entry.startswith("py/"):
            continue
        if not target.is_file():
            msgs.append("APP_SHELL 列了但檔案不存在：%s" % entry)

    for p in sorted(web.rglob("*")):
        if not p.is_file() or _is_junk(p):
            continue
        rel = p.relative_to(web).as_posix()
        if rel not in seen:
            msgs.append("web/%s 不在 APP_SHELL 中" % rel)

    if built:
        have = read_shell_hash(web)
        want = shell_hash(web, shell)
        if have != want:
            msgs.append("SHELL_HASH 過期：sw.js 為 %r，實際為 %s"
                        "（請執行 python tools/build_web.py）" % (have, want))

    cache, app = read_versions(web)
    if cache is None or app is None:
        msgs.append("找不到版本宣告：CACHE_VERSION=%r APP_VERSION=%r"
                    % (cache, app))
    elif cache != "bacalc-v" + app:
        msgs.append("版本不同步：CACHE_VERSION=%s，APP_VERSION=%s"
                    % (cache, app))
    return msgs


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    web = Path(argv[0]) if argv else ROOT / "web"
    msgs = check(web)
    for m in msgs:
        print(m)
    print("check_shell：%s" % ("%d 項違規" % len(msgs) if msgs else "通過"))
    return 1 if msgs else 0


if __name__ == "__main__":
    sys.exit(main())
