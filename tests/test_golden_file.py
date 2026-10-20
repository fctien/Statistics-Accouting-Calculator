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
        assert c["source"].startswith(("Excel 16:", "TI Guidebook"))
        assert isinstance(c["expected"], float)


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
