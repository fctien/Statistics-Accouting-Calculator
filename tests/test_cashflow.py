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
    # 多重根時回傳哪個根取決於起始猜測值 0.1（此例落在 10%）
    assert abs(r["values"]["IRR"] - 10) < 1e-6
    assert r["warnings"] == ["現金流正負號變化多次，IRR 可能有多個解"]


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
    # 手算：折現值 454.55、413.22、375.66；前兩期累計 -132.23，故 2+132.23/375.66=2.352
    r = cashflow.dpayback(_in(-1000, [[500, 3]]))
    assert r["ok"]
    c1, c2, c3 = 500 / 1.1, 500 / 1.21, 500 / 1.331
    expect = 2 + (1000 - c1 - c2) / c3
    assert abs(r["values"]["DPB"] - expect) < 1e-12
    assert abs(r["values"]["DPB"] - 2.352) < 5e-4


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


def test_payback_positive_cf0_is_error():
    for f in (cashflow.payback, cashflow.dpayback):
        r = f(_in(500, [[-100, 3]]))
        assert r["ok"] is False and r["field"] == "CF"


def test_long_horizon_no_exception():
    """9999 期極端利率：不得擲例外，結果須為錯誤或有限數。"""
    cases = [
        (cashflow.irr, _in(-100, [[1, 9999]])),
        (cashflow.nfv, _in(-100, [[1, 9999]], i=500)),
        (cashflow.mirr, _in(-100, [[1, 9999]], i=10, ri=500)),
        (cashflow.npv, _in(-100, [[1, 9999]], i=-99.9)),
        (cashflow.dpayback, _in(-100, [[1, 9999]], i=-99.9)),
    ]
    for f, inp in cases:
        r = f(inp)
        if r["ok"]:
            assert all(v == v and abs(v) != float("inf")
                       for v in r["values"].values())
        else:
            assert r["error"]
