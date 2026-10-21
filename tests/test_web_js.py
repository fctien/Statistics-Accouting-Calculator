"""把 JS 單元測試（node --test tests/js/*.test.mjs）納入 pytest。

Node 22 的 `node --test 目錄` 不會展開目錄，因此傳 glob 字串（由 Node 自行展開，Windows 亦可）。
另檢查 TAP 摘要「# tests N」N > 0：glob 對不到任何檔案時 node 也會 exit 0（vacuous pass）。
"""
from tests._node import run_node, tap_test_count
from tools.verify_all import node_tap_guard


def test_node_unit_tests_pass():
    proc = run_node(["--test", "tests/js/*.test.mjs"])
    tail = "\n".join((proc.stdout + proc.stderr).splitlines()[-40:])
    assert proc.returncode == 0, "JS 測試失敗：\n" + tail
    assert "# fail 0" in proc.stdout, tail
    n = tap_test_count(proc.stdout)
    assert n is not None and n > 0, "node 沒有跑到任何測試：\n" + tail


def test_tap_test_count_parses_summary():
    assert tap_test_count("ok 1 - a\n# tests 12\n# pass 12\n# fail 0\n") == 12
    assert tap_test_count("# tests 0\n# pass 0\n# fail 0\n") == 0
    assert tap_test_count("no summary here") is None


def test_verify_all_node_guard_rejects_zero_tests():
    # verify_all 的 node --test 步驟：exit 0 但 0 個測試（或沒有摘要）也要判為失敗
    code, _msg = node_tap_guard(0, "# tests 0\n# pass 0\n# fail 0\n")
    assert code != 0
    code, _msg = node_tap_guard(0, "garbage without summary")
    assert code != 0
    assert node_tap_guard(0, "# tests 5\n# pass 5\n# fail 0\n")[0] == 0
    assert node_tap_guard(1, "# tests 5\n# fail 1\n")[0] == 1
