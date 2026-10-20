"""建置 PWA 的 Python 與執行環境檔案（build web）。

用法：
    python tools/build_web.py
        建置：engine/*.py 等 → web/py/，MicroPython → web/vendor/
    python tools/build_web.py --check
        只檢查 web/py、web/vendor、sw.js 是否為最新，過期 exit 1（不寫檔）
    python tools/build_web.py --bump X.Y.Z
        同步升 sw.js 的 CACHE_VERSION 與 app.js 的 APP_VERSION

web/py/ 版面（git-ignored，部署流程須先執行本工具）：
    engine/*.py、golden/__init__.py、golden/runner.py   寫入 MicroPython VFS 的模組
    data/excel.json、data/error_cases.json   selftest.html 用的 golden 資料
    manifest.json                            {"vendor", "modules", "data"}
web/vendor/（已 commit，鎖定版本）：micropython.js（＝套件的 micropython.mjs，改副檔名）、
    micropython.wasm、VERSION.txt
sw.js 的 APP_SHELL 中 "// @py-begin" 與 "// @py-end" 之間由本工具產生；
sw.js 的 SHELL_HASH 也由本工具依 APP_SHELL 檔案內容計算（check_shell.shell_hash），
殼檔案一改就換快取名稱。--bump 之後會自動重新建置。
"""
import argparse
import json
import re
import sys
from pathlib import Path

try:  # 以模組匯入（pytest：tools.build_web）
    from tools import check_shell
except ImportError:  # 以腳本執行（python tools/build_web.py）
    import check_shell

ROOT = Path(__file__).resolve().parent.parent
# 鎖定的 @micropython/micropython-webassembly-pyscript 版本
VENDOR_VERSION = "1.29.0-6"
VENDOR_PKG = Path("node_modules/@micropython/micropython-webassembly-pyscript")
# {web/vendor 檔名: 套件內檔名}；.mjs 改名為 .js：Windows 的 python -m http.server
# 依登錄檔把 .mjs 當 text/plain，瀏覽器會拒絕載入 module script
VENDOR_FILES = {"micropython.js": "micropython.mjs",
                "micropython.wasm": "micropython.wasm"}
GOLDEN_MODULES = ("__init__.py", "runner.py")
DATA_FILES = {"data/excel.json": "tests/golden/excel.json",
              "data/error_cases.json": "tests/golden/error_cases.json"}
PY_BEGIN = "// @py-begin"
PY_END = "// @py-end"
_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
_CACHE_RE = re.compile(r'(const CACHE_VERSION = ")bacalc-v[^"]*(";)')
_APP_RE = re.compile(r'(export const APP_VERSION = ")[^"]*(";)')


def _py_sources(root):
    """回傳 {web/py 下相對路徑: 來源 Path}（模組）與資料檔對照。"""
    modules = {}
    for p in sorted((root / "engine").glob("*.py")):
        modules["engine/" + p.name] = p
    for name in GOLDEN_MODULES:
        modules["golden/" + name] = root / "golden" / name
    data = {rel: root / src for rel, src in DATA_FILES.items()}
    return modules, data


def _manifest_bytes(modules, data):
    man = {"vendor": VENDOR_VERSION, "modules": sorted(modules),
           "data": sorted(data)}
    text = json.dumps(man, indent=1, ensure_ascii=True) + "\n"
    return text.encode("utf-8")


def _sw_with_py_block(sw_text, py_entries):
    """把 sw.js 中 @py-begin／@py-end 之間換成 py_entries，回傳新文字。"""
    lines = sw_text.splitlines(keepends=True)
    try:
        b = next(i for i, x in enumerate(lines) if PY_BEGIN in x)
        e = next(i for i, x in enumerate(lines) if PY_END in x)
    except StopIteration:
        raise ValueError("sw.js 找不到 %s／%s 標記" % (PY_BEGIN, PY_END))
    indent = lines[b][:len(lines[b]) - len(lines[b].lstrip())]
    nl = "\r\n" if lines[b].endswith("\r\n") else "\n"
    block = ['%s"py/%s",%s' % (indent, rel, nl) for rel in py_entries]
    return "".join(lines[:b + 1] + block + lines[e:])


def expected_files(root):
    """回傳 {web/ 下相對路徑: bytes}：本工具應產生或更新的全部檔案。"""
    root = Path(root)
    web = root / "web"
    modules, data = _py_sources(root)
    out = {}
    for rel, src in list(modules.items()) + list(data.items()):
        if not src.is_file():
            raise FileNotFoundError("找不到來源檔 %s" % src)
        out["py/" + rel] = src.read_bytes()
    out["py/manifest.json"] = _manifest_bytes(modules, data)

    # 執行環境：有 node_modules 就以它為準（並核對版本）；沒有就沿用已 commit 的 web/vendor
    pkg = root / VENDOR_PKG
    if pkg.is_dir():
        ver = json.loads((pkg / "package.json").read_text(encoding="utf-8"))
        if ver.get("version") != VENDOR_VERSION:
            raise ValueError("node_modules 的 MicroPython 版本 %s 不是鎖定的 %s"
                             % (ver.get("version"), VENDOR_VERSION))
        for name, src in VENDOR_FILES.items():
            out["vendor/" + name] = (pkg / src).read_bytes()
    else:
        for name in VENDOR_FILES:
            if not (web / "vendor" / name).is_file():
                raise FileNotFoundError(
                    "缺少 web/vendor/%s，且沒有 node_modules 可複製（請先 npm ci）"
                    % name)
    out["vendor/VERSION.txt"] = (
        "@micropython/micropython-webassembly-pyscript %s\n"
        "micropython.js = micropython.mjs"
        " (byte-identical, renamed for MIME type)\n"
        % VENDOR_VERSION).encode("utf-8")

    sw = web / "sw.js"
    py_entries = sorted(k[3:] for k in out if k.startswith("py/"))
    sw_text = _sw_with_py_block(sw.read_bytes().decode("utf-8"), py_entries)
    # SHELL_HASH：殼檔案內容一變，sw.js 位元組就變，瀏覽器才會安裝新 SW
    digest = check_shell.shell_hash(web, check_shell.parse_app_shell(sw_text),
                                    overrides=out)
    sw_text, n = check_shell.SHELL_HASH_RE.subn(
        lambda m: m.group(1) + digest + m.group(3), sw_text)
    if n != 1:
        raise ValueError("sw.js 中 const SHELL_HASH 應恰有 1 處，實有 %d 處" % n)
    out["sw.js"] = sw_text.encode("utf-8")
    return out


def build(root=ROOT, check=False):
    """建置（check=False）或檢查（check=True）。回傳過期／問題清單；建置模式成功回傳 []。"""
    root = Path(root)
    web = root / "web"
    want = expected_files(root)
    py_dir = web / "py"
    extra = []
    if py_dir.is_dir():
        for p in sorted(py_dir.rglob("*")):
            rel = p.relative_to(web).as_posix()
            if p.is_file() and rel not in want:
                extra.append(p)
    if check:
        stale = []
        for rel, data in sorted(want.items()):
            path = web / rel
            if not path.is_file():
                stale.append("缺少 web/%s" % rel)
            elif path.read_bytes() != data:
                stale.append("過期 web/%s" % rel)
        stale += ["多餘 %s" % p.relative_to(root).as_posix() for p in extra]
        return stale
    for rel, data in want.items():
        path = web / rel
        if path.is_file() and path.read_bytes() == data:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    # web/py 是產生的目錄（git-ignored）：移除不再對應來源的舊檔
    for p in extra:
        p.unlink()
    return []


def bump(root, version):
    """同步把 CACHE_VERSION 設為 bacalc-v{version}、APP_VERSION 設為 {version}。"""
    if not _VERSION_RE.match(version or ""):
        raise ValueError("版本號必須是 X.Y.Z：%r" % version)
    web = Path(root) / "web"
    # 先兩個檔案都驗證成功，才一起寫入（避免只改到一個造成版本不同步）
    pending = []
    for path, rx, new in ((web / "sw.js", _CACHE_RE, "bacalc-v" + version),
                          (web / "js" / "app.js", _APP_RE, version)):
        text = path.read_bytes().decode("utf-8")
        out, n = rx.subn(lambda m: m.group(1) + new + m.group(2), text)
        if n != 1:
            raise ValueError("%s 中版本宣告應恰有 1 處，實有 %d 處" % (path, n))
        pending.append((path, out))
    for path, out in pending:
        path.write_bytes(out.encode("utf-8"))
    # app.js 改了 → 重新建置以更新 SHELL_HASH
    build(root)


def main(argv=None):
    ap = argparse.ArgumentParser(description="建置 web/py 與 web/vendor")
    ap.add_argument("--check", action="store_true", help="只檢查是否為最新")
    ap.add_argument("--bump", metavar="X.Y.Z",
                    help="同步升 CACHE_VERSION 與 APP_VERSION")
    ap.add_argument("--root", default=str(ROOT), help="專案根目錄（測試用）")
    args = ap.parse_args(argv)
    root = Path(args.root)
    if args.bump:
        try:
            bump(root, args.bump)
        except ValueError as e:
            print(e)
            return 2
        print("版本已升為 %s（sw.js、app.js）" % args.bump)
    if args.check:
        stale = build(root, check=True)
        for m in stale:
            print(m)
        state = "已過期，請執行 python tools/build_web.py" if stale else "皆為最新"
        print("web/ 建置檔" + state)
        return 1 if stale else 0
    build(root)
    n = len(json.loads((root / "web" / "py" / "manifest.json")
                       .read_text(encoding="utf-8"))["modules"])
    print("已建置 web/py（%d 個模組）與 web/vendor（%s）" % (n, VENDOR_VERSION))
    return 0


if __name__ == "__main__":
    sys.exit(main())
