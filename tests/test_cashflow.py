"""現金流 CF 測試（golden + 邊界案例）。"""
from engine import cashflow
from tests.conftest import rel_close

_ACTIONS = {"npv": cashflow.npv, "irr": cashflow.irr, "nfv": cashflow.nfv,
            "mirr": cashflow.mirr}


def _in(cf0, flows, i=10, ri=None):
    return {"CF0": cf0, "flows": flows, "I": i, "RI": ri}


def test_cashflow_golden(golden_cases):
    cases = golden_cases("cashflow")
    assert cases
    for c in cases:
        r = _ACTIONS[c["call"]["action"]](c["call"]["inputs"])
        assert r["ok"] and rel_close(
            r["values"][c["expect_key"]], c["expected"], c["tol"]), c["id"]


def test_irr_no_sign_change():
    r = cashflow.irr(_in(100, [[50, 2]]))
    assert r["ok"] is False and r["field"] == "CF"


def test_irr_multiple_sign_warning():
    r = cashflow.irr(_in(-100, [[230, 1], [-132, 1]]))
    assert r["ok"] and r["warnings"]
    assert abs(r["values"]["IRR"] - 10) < 1e-6 or r["values"]["IRR"] > 0


def test_payback_interpolated():
    r = cashflow.payback(_in(-1000, [[400, 3]]))
    assert r["ok"] and abs(r["values"]["PB"] - 2.5) < 1e-12


def test_dpayback_never_recovered():
    r = cashflow.dpayback(_in(-1000, [[100, 3]]))
    assert r["ok"] is False and r["field"] == "DPB"


def test_payback_never_recovered():
    r = cashflow.payback(_in(-1000, [[100, 3]]))
    assert r["ok"] is False and r["field"] == "PB"


def test_dpayback_value():
    # 折現後累計：-1000, -636.36, -272.73(…) 手算 -1000+500/1.1+500/1.21+500/1.331
    r = cashflow.dpayback(_in(-1000, [[500, 3]]))
    assert r["ok"]
    c1, c2, c3 = 500 / 1.1, 500 / 1.21, 500 / 1.331
    expect = 2 + (1000 - c1 - c2) / c3
    assert abs(r["values"]["DPB"] - expect) < 1e-12


def test_flow_count_invalid():
    for bad in (0, 10000, 1.5, -1, None, True):
        r = cashflow.npv(_in(-100, [[50, bad]]))
        assert r["ok"] is False and r["field"] == "CF", bad
    assert cashflow.npv(_in(-100, [[50, 3.0]]))["ok"]


def test_mirr_requires_ri_and_both_signs():
    r = cashflow.mirr(_in(-100, [[50, 3]], ri=None))
    assert r["ok"] is False and r["field"] == "RI"
    r = cashflow.mirr(_in(100, [[50, 3]], ri=5))
    assert r["ok"] is False


def test_expand():
    assert cashflow.expand(-1, [[2, 2], [3, 1]]) == [-1, 2, 2, 3]
    assert cashflow.expand(-1, [[2, 0]])["ok"] is False
