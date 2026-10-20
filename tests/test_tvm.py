"""TVM 貨幣時間價值測試（golden + 邊界案例）。"""
from engine.tvm import period_rate, solve
from tests.conftest import rel_close


def test_tvm_golden(golden_cases):
    cases = golden_cases("tvm")
    assert cases
    for c in cases:
        inp = c["call"]["inputs"]
        unknown = next(k for k in ("N", "IY", "PV", "PMT", "FV")
                       if inp.get(k) is None)
        r = solve(inp, unknown)
        assert r["ok"] and rel_close(
            r["values"][c["expect_key"]], c["expected"], c["tol"]), c["id"]


def test_tvm_simple_anchor():
    r = solve({"N": 1, "IY": 10, "PV": -100, "PMT": 0, "PY": 1, "CY": 1,
               "BGN": False}, "FV")
    assert abs(r["values"]["FV"] - 110) < 1e-9


def test_tvm_zero_rate():
    base = {"N": 10, "PV": 1000, "FV": 0, "PY": 1, "CY": 1, "BGN": False}
    assert abs(solve({**base, "IY": 0}, "PMT")["values"]["PMT"] + 100) < 1e-9
    assert abs(solve({**base, "IY": 1e-10}, "PMT")["values"]["PMT"]
               + 100) < 1e-6


def test_tvm_overflow_is_error():
    r = solve({"N": 1e6, "IY": 1000, "PV": -1, "PMT": 0, "PY": 1, "CY": 1,
               "BGN": False}, "FV")
    assert r["ok"] is False


def test_tvm_same_sign_no_rate():
    r = solve({"N": 10, "PV": 100, "PMT": 10, "FV": 100, "PY": 1, "CY": 1,
               "BGN": False}, "IY")
    assert r["ok"] is False and r["field"] == "IY"


def test_tvm_validation():
    base = {"N": 10, "IY": 5, "PV": 100, "PMT": None, "FV": 0, "PY": 1,
            "CY": 1, "BGN": False}
    assert solve({**base, "PY": 0}, "PMT")["ok"] is False
    assert solve({**base, "CY": -1}, "PMT")["ok"] is False
    r = solve({k: v for k, v in base.items() if k != "PY"}, "PMT")
    assert r["ok"] is False and r["field"] == "PY"
    assert solve({**base, "N": 0}, "PMT")["field"] == "N"


def test_tvm_n_unreachable():
    r = solve({"N": None, "IY": 5, "PV": 100, "PMT": 10, "FV": 0, "PY": 1,
               "CY": 1, "BGN": False}, "N")
    assert r["ok"] is False and r["field"] == "N"


def test_period_rate():
    assert abs(period_rate(12, 12, 12) - 0.01) < 1e-15
