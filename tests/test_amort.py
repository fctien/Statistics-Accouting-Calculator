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
    for p1, p2, f in ((0, 5, "P1"), (6, 5, "P2"), (1, 361, "P2"),
                      (2.5, 5, "P1"), (2, 5.5, "P2"), (None, 5, "P1"),
                      (2, None, "P2")):
        r = amort(BASE, p1, p2)
        assert not r["ok"] and r["field"] == f, (p1, p2)


def test_non_integer_n_error():
    inp = dict(BASE, N=24.5)
    for r in (amort(inp, 1, 5), schedule(inp)):
        assert not r["ok"] and r["field"] == "N"


def test_bgn_first_interest_zero():
    row = schedule(dict(BASE, N=12, BGN=True))["values"]["rows"][0]
    assert row[2] == 0
    assert amort(dict(BASE, BGN=True), 1, 1)["values"]["INT"] == 0


def test_negative_pv_sign():
    inp = dict(BASE, PV=-300000, PMT=1798.651575458257)
    r = amort(inp, 1, 12)
    assert r["ok"] and r["values"]["BAL"] < 0
    assert abs(r["values"]["BAL"] + 296315.96486317005) < 1e-6


def test_schedule_tail_warning():
    r = schedule(dict(BASE, N=12, PMT=-1000.0, PV=10000, IY=0))
    assert r["ok"] and len(r["values"]["rows"]) == 12
    assert any("尾差" in w for w in r["warnings"])
    r2 = schedule(dict(BASE, N=360))
    assert r2["ok"] and not r2["warnings"]
    assert r2["values"]["rows"][0][0] == 1


def test_non_finite_and_non_numeric():
    inf, nan = float("inf"), float("nan")
    assert amort(BASE, 1, inf)["field"] == "P2"
    assert amort(BASE, nan, 5)["field"] == "P1"
    for n in (inf, nan, "abc"):
        for r in (amort(dict(BASE, N=n), 1, 5), schedule(dict(BASE, N=n))):
            assert not r["ok"] and r["field"] == "N"
    assert amort(BASE, "1", 5)["field"] == "P1"
