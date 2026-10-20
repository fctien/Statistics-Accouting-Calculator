"""web/js/input.js 的 parseNumber 與 engine/fmt.parse_number 逐案一致（parity）。

瀏覽器在 Python 載入前就用 JS 解析輸入；兩邊規則不同會造成「畫面接受、引擎拒絕」之類的落差。
"""
import json

from engine.fmt import parse_number
from tests._node import run_node

TEXTS = [
    "0", "1", "-1", "+1", "1000", "1,000", "1,0000", "10,00", ",100",
    "1,000,000", "12,345,678.9", "1.5", ".5", "5.", "-.5", "1.2.3",
    "1,000.5.5", "1e3", "1E3", "1e+3", "1e-3", "1.5e2", "1,000e2", "1e",
    "e5", "1e3.5", "1ee3", "", " ", "-", "+", ".", "abc", "1a", "0x10",
    "1_000", "1 000", "  42  ", "　７　", "１２３", "－５",
    "１，０００", "1e400", "-1e400", "1e-400", "Infinity", "NaN", "inf",
    "00012", "1,23", "1.000.000,25", "0,5", "1.000", "1,5", "--1", "+-1",
    "1e-", "1e+", "١٢٣", "5%", "1/2", "0.1e1", "9" * 30,
]


def test_parse_number_matches_engine_fmt():
    cases = [[t, sep] for t in TEXTS for sep in ("us", "eu")]
    proc = run_node(["tests/js/helpers/parse_corpus.mjs"],
                    stdin=json.dumps(cases))
    assert proc.returncode == 0, proc.stderr
    got = json.loads(proc.stdout)
    diffs = []
    for (text, sep), js in zip(cases, got):
        py = parse_number(text, sep)
        same = (py is None and js is None) or (
            py is not None and js is not None and py == js)
        if not same:
            diffs.append("%r (%s): Python=%r JS=%r" % (text, sep, py, js))
    assert not diffs, "\n".join(diffs)
