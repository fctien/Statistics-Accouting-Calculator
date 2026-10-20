"""債券 BOND 測試（golden + 邊界案例）。"""
from engine import bond
from tests.conftest import rel_close

_ACTIONS = {"price": bond.price, "yield": bond.yield_}


def _in(sdt=(2026, 6, 12), rdt=(2036, 1, 1), cpn=7.0, rv=100.0,
        basis="ACT", freq=2, yld=None, pri=None):
    return {"SDT": list(sdt), "RDT": list(rdt), "CPN": cpn, "RV": rv,
            "basis": basis, "freq": freq, "YLD": yld, "PRI": pri}


def test_bond_golden(golden_cases):
    cases = golden_cases("bond")
    assert cases
    for c in cases:
        r = _ACTIONS[c["call"]["action"]](c["call"]["inputs"])
        assert r["ok"], (c["id"], r)
        got = r["values"][c["expect_key"]]
        assert rel_close(got, c["expected"], c["tol"]), (
            c["id"], got, c["expected"])


def test_price_yield_roundtrip():
    for basis in ("ACT", "360"):
        for freq in (1, 2):
            p = bond.price(_in(basis=basis, freq=freq, yld=5.25))
            assert p["ok"]
            y = bond.yield_(_in(basis=basis, freq=freq,
                                pri=p["values"]["PRI"]))
            assert y["ok"] and abs(y["values"]["YLD"] - 5.25) < 1e-8
            assert y["values"]["AI"] == p["values"]["AI"]


def test_settle_after_maturity_error():
    r = bond.price(_in(sdt=(2036, 1, 1), yld=8))
    assert r["ok"] is False and r["field"] == "SDT"
    r = bond.price(_in(sdt=(2037, 1, 1), yld=8))
    assert r["ok"] is False and r["field"] == "SDT"


def test_invalid_date_error():
    r = bond.price(_in(sdt=(2026, 2, 30), yld=8))
    assert r["ok"] is False and r["field"] == "SDT"
    r = bond.price(_in(rdt=(2036, 13, 1), yld=8))
    assert r["ok"] is False and r["field"] == "RDT"


def test_invalid_fields():
    assert bond.price(_in(freq=4, yld=8))["field"] == "freq"
    assert bond.price(_in(rv=0, yld=8))["field"] == "RV"
    assert bond.price(_in(cpn=-1, yld=8))["field"] == "CPN"
    assert bond.price(_in(basis="X", yld=8))["field"] == "basis"
    assert bond.price(_in())["field"] == "YLD"
    assert bond.yield_(_in())["field"] == "PRI"
    assert bond.yield_(_in(pri=-5))["ok"] is False


def test_single_period_price():
    # N = 1：簡單貼現公式；結算日在最後一期內
    # PCD=2035-07-01、NCD=RDT=2036-01-01，A=153、E=184（ACT）
    r = bond.price(_in(sdt=(2035, 12, 1), yld=8))
    a, e = 153, 184
    dsc = e - a
    exp = (100 + 3.5) / (1 + dsc / e * 0.04) - a / e * 3.5
    assert r["ok"] and abs(r["values"]["PRI"] - exp) < 1e-12


def test_end_of_month_coupon_dates():
    # 到期日 8/31（月底）→ 付息日為 2/28 或 2/29（月底規則）
    pcd, ncd, n = bond._coupon_dates((2026, 3, 15), (2030, 8, 31), 2)
    assert pcd == (2026, 2, 28) and ncd == (2026, 8, 31) and n == 9
    pcd, ncd, n = bond._coupon_dates((2028, 1, 15), (2030, 8, 31), 2)
    assert pcd == (2027, 8, 31) and ncd == (2028, 2, 29)
    # 非月底：到期日 8/30 → 付息日 2/28、8/30
    pcd, ncd, n = bond._coupon_dates((2026, 3, 15), (2030, 8, 30), 2)
    assert pcd == (2026, 2, 28) and ncd == (2026, 8, 30)


def test_settle_on_coupon_date_zero_ai():
    r = bond.price(_in(sdt=(2026, 7, 1), yld=8))
    assert r["ok"] and r["values"]["AI"] == 0


def test_yield_unsolvable():
    # 價格極端高，殖利率需 < -99% → 無解
    r = bond.yield_(_in(pri=1e12))
    assert r["ok"] is False and r["field"] == "YLD"
