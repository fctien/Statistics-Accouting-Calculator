"""PWA 殼（app shell）測試：build_web.py 與 check_shell.py。

所有會寫檔的測試都在 tmp_path 的 repo 複本中執行，不動 repo 本身。
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tools import build_web, check_shell

ROOT = Path(__file__).resolve().parent.parent


def _copy_repo(dst):
    """把 build_web 需要的部分複製到 dst（engine、golden、tests/golden、web 不含 py/）。"""
    shutil.copytree(ROOT / "engine", dst / "engine",
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(ROOT / "golden", dst / "golden",
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(ROOT / "tests" / "golden", dst / "tests" / "golden")
    shutil.copytree(ROOT / "web", dst / "web",
                    ignore=shutil.ignore_patterns("py", "__pycache__"))
    return dst


@pytest.fixture
def built(tmp_path):
    """已執行 build_web 的 repo 複本根目錄。"""
    root = _copy_repo(tmp_path / "repo")
    assert build_web.build(root) == []
    return root


def test_check_shell_passes_after_build(built):
    assert check_shell.check(built / "web") == []


def test_check_shell_requires_build(tmp_path):
    root = _copy_repo(tmp_path / "repo")
    msgs = check_shell.check(root / "web")
    assert any("build_web" in m for m in msgs)


def test_check_shell_flags_unlisted_file(built):
    (built / "web" / "js" / "extra.js").write_text("// x\n", encoding="utf-8")
    msgs = check_shell.check(built / "web")
    assert any("js/extra.js" in m for m in msgs)


def test_check_shell_flags_missing_entry(built):
    (built / "web" / "css" / "app.css").unlink()
    msgs = check_shell.check(built / "web")
    assert any("css/app.css" in m for m in msgs)


def test_version_sync():
    cache, app = check_shell.read_versions(ROOT / "web")
    assert cache == "bacalc-v" + app


def test_check_shell_flags_version_mismatch(built):
    app_js = built / "web" / "js" / "app.js"
    text = app_js.read_text(encoding="utf-8")
    app_js.write_text(text.replace('APP_VERSION = "', 'APP_VERSION = "9'),
                      encoding="utf-8")
    msgs = check_shell.check(built / "web")
    assert any("版本" in m for m in msgs)


def test_bump_updates_both_versions(built):
    build_web.bump(built, "1.2.3")
    assert check_shell.read_versions(built / "web") == \
        ("bacalc-v1.2.3", "1.2.3")
    assert check_shell.check(built / "web") == []


def test_bump_rejects_bad_version(built):
    with pytest.raises(ValueError):
        build_web.bump(built, "1.2")


def test_build_check_detects_stale_copy(built):
    assert build_web.build(built, check=True) == []
    (built / "engine" / "tvm.py").write_text(
        (built / "engine" / "tvm.py").read_text(encoding="utf-8") + "\n# 改\n",
        encoding="utf-8")
    stale = build_web.build(built, check=True)
    assert any("engine/tvm.py" in m for m in stale)
    # --check 不寫檔：再查一次仍是過期
    assert build_web.build(built, check=True) != []


def test_build_check_detects_new_engine_file(built):
    (built / "engine" / "newmod.py").write_text("X = 1\n", encoding="utf-8")
    stale = build_web.build(built, check=True)
    assert any("newmod.py" in m for m in stale)


def test_build_check_detects_extra_py_file(built):
    old = built / "web" / "py" / "engine" / "old.py"
    old.write_text("", encoding="utf-8")
    assert any("old.py" in m for m in build_web.build(built, check=True))


def test_manifest_lists_engine_and_runner(built):
    man = json.loads((built / "web" / "py" / "manifest.json")
                     .read_text(encoding="utf-8"))
    assert "engine/bridge.py" in man["modules"]
    assert "golden/runner.py" in man["modules"]
    assert "golden/__init__.py" in man["modules"]
    assert set(man["data"]) == {"data/excel.json", "data/error_cases.json"}
    for rel in man["modules"] + man["data"]:
        assert (built / "web" / "py" / rel).is_file()


def test_app_shell_contains_vendor_and_manifest(built):
    shell = check_shell.read_app_shell(built / "web")
    for need in ("./", "index.html", "selftest.html", "sw.js",
                 "vendor/micropython.js", "vendor/micropython.wasm",
                 "py/manifest.json", "py/engine/bridge.py",
                 "manifest.webmanifest", "icons/icon-192.png",
                 "icons/icon-512.png", "js/py-worker.js"):
        assert need in shell, need


def test_no_absolute_urls_in_web():
    """GitHub Pages 子路徑部署：web/ 的 html／js 不可用以 / 開頭的絕對網址。"""
    bad = []
    for p in list((ROOT / "web").rglob("*.html")) + list(
            (ROOT / "web" / "js").rglob("*.js")) + [ROOT / "web" / "sw.js"]:
        text = p.read_text(encoding="utf-8")
        for token in ('href="/', 'src="/', 'URL("/', 'fetch("/',
                      'register("/', 'from "/', 'import("/'):
            if token in text:
                bad.append("%s: %s" % (p.name, token))
    assert bad == []


def test_vendor_matches_pinned_package():
    pkg = ROOT / "node_modules" / "@micropython" / \
        "micropython-webassembly-pyscript"
    if not pkg.is_dir():
        pytest.skip("node_modules 不存在")
    for name, src in (("micropython.js", "micropython.mjs"),
                      ("micropython.wasm", "micropython.wasm")):
        assert (ROOT / "web" / "vendor" / name).read_bytes() == \
            (pkg / src).read_bytes()


def test_js_syntax_with_node():
    node = shutil.which("node")
    if not node:
        pytest.skip("找不到 node")
    files = sorted((ROOT / "web" / "js").glob("*.js")) + \
        [ROOT / "web" / "sw.js"]
    for f in files:
        r = subprocess.run([node, "--check", str(f)], capture_output=True,
                           text=True)
        assert r.returncode == 0, "%s\n%s" % (f, r.stderr)


def test_check_shell_cli_exit_code(built):
    tool = ROOT / "tools" / "check_shell.py"
    ok = subprocess.run([sys.executable, str(tool), str(built / "web")],
                        capture_output=True)
    assert ok.returncode == 0
    (built / "web" / "stray.txt").write_text("x", encoding="utf-8")
    bad = subprocess.run([sys.executable, str(tool), str(built / "web")],
                         capture_output=True)
    assert bad.returncode == 1


def _node_or_skip():
    node = shutil.which("node")
    if not node:
        pytest.skip("找不到 node")
    return node


def test_worker_client_in_node(built):
    """以真正的 MicroPython 跑 py-worker.js＋py-client.js：佇列、golden、錯誤路徑。"""
    node = _node_or_skip()
    r = subprocess.run([node, str(ROOT / "tools" / "check_worker.mjs"),
                        str(built / "web")], capture_output=True,
                       encoding="utf-8")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "PASS" in r.stdout


def test_worker_client_load_failure_in_node(tmp_path):
    """web/py 不存在：狀態轉 error，排隊中與之後的請求都 reject。"""
    node = _node_or_skip()
    web = tmp_path / "web"
    shutil.copytree(ROOT / "web", web, ignore=shutil.ignore_patterns("py"))
    r = subprocess.run([node, str(ROOT / "tools" / "check_worker.mjs"),
                        str(web), "--broken"], capture_output=True,
                       encoding="utf-8")
    assert r.returncode == 0, r.stdout + r.stderr


def test_shell_hash_changes_with_engine_file(built):
    """改 engine 檔並重新 build：SHELL_HASH 改變，且 check_shell 通過。"""
    before = check_shell.read_shell_hash(built / "web")
    assert before and len(before) == 16
    tvm = built / "engine" / "tvm.py"
    tvm.write_text(tvm.read_text(encoding="utf-8") + "\n# 改\n",
                   encoding="utf-8")
    assert build_web.build(built) == []
    after = check_shell.read_shell_hash(built / "web")
    assert after != before
    assert check_shell.check(built / "web") == []


def test_stale_shell_hash_detected(built):
    """殼檔案改了但沒重新 build：check_shell 與 build --check 都要抓到。"""
    css = built / "web" / "css" / "app.css"
    css.write_text(css.read_text(encoding="utf-8") + "\n/* 改 */\n",
                   encoding="utf-8")
    assert any("SHELL_HASH" in m for m in check_shell.check(built / "web"))
    assert any("sw.js" in m for m in build_web.build(built, check=True))


def test_shell_hash_ignores_sw_itself(built):
    """sw.js 不納入雜湊（否則寫入雜湊會改變雜湊本身）。"""
    web = built / "web"
    shell = check_shell.read_app_shell(web)
    assert check_shell.shell_hash(web, shell) == \
        check_shell.read_shell_hash(web)


def test_bump_validates_both_before_writing(built):
    """app.js 版本宣告壞掉時 --bump 失敗，sw.js 也不能被改。"""
    sw = built / "web" / "sw.js"
    app_js = built / "web" / "js" / "app.js"
    sw_before = sw.read_bytes()
    app_js.write_text(app_js.read_text(encoding="utf-8").replace(
        "export const APP_VERSION", "export const APP_VER"), encoding="utf-8")
    with pytest.raises(ValueError):
        build_web.bump(built, "2.0.0")
    assert sw.read_bytes() == sw_before


def test_sw_precache_bypasses_http_cache():
    text = (ROOT / "web" / "sw.js").read_text(encoding="utf-8")
    assert 'cache: "reload"' in text
    assert "ignoreSearch: true" in text
    assert "cache.addAll" not in text
