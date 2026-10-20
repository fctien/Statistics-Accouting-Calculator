"""AMORT 分期攤還測試。"""
from engine.amort import amort, schedule
from tests.conftest import rel_close

BASE = {"N": 360, "IY": 6, "PV": 300000, "PMT": -1798.651575458257, "FV": 0,
        "PY": 12, "CY": 12, "BGN": False}


def test_amort_golden(golden_cases):
    cases = golden_cases("amort")
    assert cases
    for c in cases:
        inp = c["call"]["inputs"]
        r = amort(inp, inp["P1"], inp["P2"])
        assert r["ok"] and rel_close(
            r["values"][c["expect_key"]], c["expected"], c["tol"]), c["id"]


def test_amort_rows_sum():
    for bgn in (False, True):
        inp = dict(BASE, BGN=bgn)
        r = amort(inp, 5, 40)
        assert r["ok"]
        v = r["values"]
        before = amort(inp, 1, 4)["values"]["BAL"]
        assert abs(v["PRN"] - (v["BAL"] - before)) < 1e-6


def test_amort_p_range_error():
    for p1, p2 in ((0, 5), (6, 5), (1, 361)):
        r = amort(BASE, p1, p2)
        assert not r["ok"] and r["field"] == "P2"


def test_schedule_tail_warning():
    r = schedule(dict(BASE, N=12, PMT=-1000.0, PV=10000, IY=0))
    assert r["ok"] and len(r["values"]["rows"]) == 12
    assert any("尾差" in w for w in r["warnings"])
    r2 = schedule(dict(BASE, N=360))
    assert r2["ok"] and not r2["warnings"]
    assert r2["values"]["rows"][0][0] == 1
