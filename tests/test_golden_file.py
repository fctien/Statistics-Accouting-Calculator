"""golden 檔案與 runner 的測試。"""
import json
import os
from collections import Counter

from golden import runner
from golden.cases import CASES

PATH = os.path.join(os.path.dirname(__file__), "golden", "excel.json")
SHEETS = ["tvm", "amort", "cashflow", "iconv", "stats", "bond", "depr", "date"]


def _data():
    with open(PATH, encoding="utf-8") as f:
        return json.load(f)


def test_every_case_has_source_and_value():
    data = _data()
    assert len(data) >= 30
    for c in data:
        assert c["source"].startswith(("Excel 16:", "TI Guidebook", "定義值："))
        # base 工作表的 expected 為字串，其餘為數值
        assert isinstance(c["expected"], str if c["sheet"] == "base" else float)


def test_each_sheet_has_three_cases():
    sheets = Counter(c["sheet"] for c in _data())
    for s in SHEETS:
        assert sheets[s] >= 3


def test_file_matches_cases_definition():
    assert [c["id"] for c in _data()] == [c["id"] for c in CASES]
    ids = [c["id"] for c in CASES]
    assert len(ids) == len(set(ids))


def test_requests_are_well_formed():
    for c in _data():
        call = c["call"]
        assert set(call) == {"sheet", "action", "inputs", "settings"}
        assert call["sheet"] == c["sheet"]
        if c["sheet"] == "amort":
            assert isinstance(call["inputs"]["PMT"], float)


def _echo(case):
    return lambda req: {"ok": True, "values": {case["expect_key"]:
                                               case["expected"]}}


def test_runner_passes_and_fails():
    data = _data()
    by_id = {c["id"]: c for c in data}
    c = data[0]
    assert runner.run([c], _echo(c)) == []
    bad = lambda req: {"ok": True, "values": {c["expect_key"]: c["expected"] * 1.01}}
    assert len(runner.run([c], bad)) == 1
    assert len(runner.run([c], lambda r: {"ok": False, "error": "x"})) == 1
    assert len(runner.run([c], lambda r: {"ok": True, "values": {}})) == 1
    assert runner.dump([c], _echo(c)) == {c["id"]: c["expected"]}
    assert runner.dump([c], lambda r: {"ok": False}) == {c["id"]: None}
    assert by_id


def test_runner_string_cases_exact_match():
    """expected 為字串：完全相等才通過；數值比對行為不變。"""
    case = {"id": "s", "expect_key": "HEX", "expected": "00FF", "tol": 0,
            "call": {}}

    def ret(v):
        return lambda req: {"ok": True, "values": {"HEX": v}}
    assert runner.run([case], ret("00FF")) == []
    assert len(runner.run([case], ret("00ff"))) == 1      # 大小寫須相同
    assert len(runner.run([case], ret("FF"))) == 1        # 不補零差異
    assert len(runner.run([case], ret(255))) == 1         # 數值不等於字串
    assert len(runner.run([case], ret(None))) == 1
    assert len(runner.run([case], lambda r: {"ok": False, "error": "x"})) == 1


def test_runner_numeric_behaviour_unchanged():
    num = {"id": "n", "expect_key": "v", "expected": 100.0, "tol": 1e-9,
           "call": {}}

    def ret(v):
        return lambda req: {"ok": True, "values": {"v": v}}
    assert runner.run([num], ret(100.0)) == []
    assert runner.run([num], ret(100.0 + 5e-8)) == []     # 相對 5e-10 內
    assert len(runner.run([num], ret(100.0 + 5e-6))) == 1
    assert len(runner.run([num], ret("100"))) == 1        # 字串不等於數值
    assert len(runner.run([num], ret(None))) == 1
    num0 = dict(num, expected=0.0)
    assert runner.run([num0], ret(5e-10)) == []           # 底數 max(1, |b|)
    assert len(runner.run([num0], ret(5e-8))) == 1
