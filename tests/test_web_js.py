"""把 JS 單元測試（node --test tests/js/*.test.mjs）納入 pytest。

Node 22 的 `node --test 目錄` 不會展開目錄，因此傳 glob 字串（由 Node 自行展開，Windows 亦可）。
"""
from tests._node import run_node


def test_node_unit_tests_pass():
    proc = run_node(["--test", "tests/js/*.test.mjs"])
    tail = "\n".join((proc.stdout + proc.stderr).splitlines()[-40:])
    assert proc.returncode == 0, "JS 測試失敗：\n" + tail
    assert "# fail 0" in proc.stdout, tail
