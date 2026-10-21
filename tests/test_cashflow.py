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


def _bisect(f, lo, hi):
    """測試用獨立二分法（f(lo) 與 f(hi) 異號）。"""
    for _ in range(200):
        mid = (lo + hi) / 2
        if (f(mid) < 0) == (f(lo) < 0):
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def test_long_horizon_irr_value():
    """CF0=-100、9999 期每期 1：封閉式 (1-(1+r)^-9999)/r = 100 的根約 1%。"""
    expected = _bisect(
        lambda r: (1 - (1 + r) ** -9999) / r - 100, 1e-4, 0.5) * 100
    r = cashflow.irr(_in(-100, [[1, 9999]]))
    assert r["ok"] and abs(r["values"]["IRR"] - expected) < 1e-6
    assert abs(expected - 1.0) < 1e-3


def test_long_horizon_npv_values():
    r = cashflow.npv(_in(-100, [[1, 9999]], i=500))
    assert r["ok"]
    assert abs(r["values"]["NPV"] - (-100 + (1 / 5) * (1 - 6.0 ** -9999))) < 1e-9
    r = cashflow.npv(_in(-100, [[0, 9999]], i=500))
    assert r["ok"] and r["values"]["NPV"] == -100
    # i=-99.9%：分母 0.001^t 下溢為 0，非零現金流真值為無限大 → 須回錯誤
    r = cashflow.npv(_in(-100, [[1, 9999]], i=-99.9))
    assert r["ok"] is False
    r = cashflow.npv(_in(-100, [[0, 9999]], i=-99.9))
    assert r["ok"] and r["values"]["NPV"] == -100


def test_long_horizon_nfv_mirr():
    # NFV = NPV·6^9999：真值（約 -1e7781）超出 float 範圍 → 錯誤是正確結果
    r = cashflow.nfv(_in(-100, [[1, 9999]], i=500))
    assert r["ok"] is False and r["field"] == "NFV"
    # i=0 時 NFV = NPV（不放大），應為有限值 -100
    r = cashflow.nfv(_in(-100, [[0, 9999]], i=0))
    assert r["ok"] and r["values"]["NFV"] == -100
    # MIRR：正現金流終值 sum 6^k 超出 float 範圍（真值有限約 500%，但此引擎
    # 無法表示中間量）→ 回錯誤而非猜測值
    r = cashflow.mirr(_in(-100, [[1, 9999]], i=10, ri=500))
    assert r["ok"] is False and r["field"] == "MIRR"
    # 小利率長期：有限且可手算驗證（ri=0 → fv=9999，fin=0 → pv=-100）
    r = cashflow.mirr(_in(-100, [[1, 9999]], i=0, ri=0))
    assert r["ok"]
    assert abs(r["values"]["MIRR"] - ((9999 / 100) ** (1 / 9999) - 1) * 100) < 1e-9


def test_irr_negative_rate():
    """負報酬率（-50%）：搜尋範圍必須涵蓋負值（突變測試補強）。"""
    r = cashflow.irr(_in(-100, [[50, 1]]))
    assert r["ok"] and rel_close(r["values"]["IRR"], -50.0, 1e-8)


def test_payback_exact_boundary():
    """累計現金流剛好為 0 時即算回本（突變測試補強）。"""
    r = cashflow.payback(_in(-1000, [[500, 2]]))
    assert r["ok"] and rel_close(r["values"]["PB"], 2.0, 1e-12)


def test_irr_true_zero_is_exact_zero():
    # [-1000, 1000] 的 IRR 正好 0%：不可顯示 -1.266E-15 這種求根雜訊
    from engine import cashflow
    for flows in ([[1000, 1]], [[500, 2]]):
        r = cashflow.irr({"CF0": -1000, "flows": flows})
        assert r["ok"], r
        assert r["values"]["IRR"] == 0.0, r
