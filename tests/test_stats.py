"""STAT 工作表測試：golden、錯誤路徑、預測。"""
import pytest

from engine import stats
from tests.conftest import rel_close


def _run(call):
    i = call["inputs"]
    if call["action"] == "one_var":
        return stats.one_var(i["X"], None)
    return stats.two_var(i["X"], i["Y"], i["model"])


def test_golden(golden_cases):
    cases = golden_cases("stats")
    assert len(cases) == 15
    for c in cases:
        res = _run(c["call"])
        assert res["ok"], c["id"]
        got = res["values"][c["expect_key"]]
        assert rel_close(got, c["expected"], c["tol"]), c["id"]


def test_sx_vs_sigma():
    v = stats.one_var([2, 4, 4, 4, 5, 5, 7, 9], None)["values"]
    assert v["sigma_x"] == pytest.approx(2.0)
    assert v["sx"] == pytest.approx(2.138089935299395)
    assert v["n"] == 8 and v["sum_x"] == 40 and v["sum_x2"] == 232


def test_frequencies():
    v = stats.one_var([1, 2], [3, 1])["values"]
    assert v["n"] == 4 and v["mean_x"] == 1.25 and v["sum_x"] == 5


def test_bad_frequencies():
    for fs in ([1], [1, 0], [1, 1.5], [1, -1], [1, True]):
        assert not stats.one_var([1, 2], fs)["ok"]


def test_one_var_n1_and_empty():
    r = stats.one_var([5], None)
    assert r["ok"] and "sx" not in r["values"] and r["values"]["sigma_x"] == 0
    assert r["warnings"]
    assert not stats.one_var([], None)["ok"]
    assert not stats.one_var([1, float("nan")], None)["ok"]


def test_exp_requires_positive_y():
    r = stats.two_var([1, 2, 3], [1, 0, 3], "EXP")
    assert not r["ok"] and r["field"] == "Y"


def test_ln_pwr_require_positive_x():
    for m in ("LN", "PWR"):
        r = stats.two_var([0, 1, 2], [1, 2, 3], m)
        assert not r["ok"] and r["field"] == "X"


def test_constant_x_and_y():
    r = stats.two_var([2, 2, 2], [1, 2, 3], "LIN")
    assert not r["ok"] and r["field"] == "X"
    r = stats.two_var([1, 2, 3], [4, 4, 4], "LIN")
    assert not r["ok"] and r["field"] == "Y"


def test_length_mismatch_and_small_n():
    assert not stats.two_var([1, 2], [1], "LIN")["ok"]
    assert not stats.two_var([1], [1], "LIN")["ok"]
    assert not stats.two_var([1, 2], [1, 2], "XYZ")["ok"]


def test_overflow_is_err():
    r = stats.two_var([1, 2, 3], [1e200, 2e200, 5e200], "LIN")
    assert not r["ok"]


def test_predict_inverse():
    f = stats.predict("LIN", 1.5, 2.0, x=4.0)["values"]["y"]
    assert f == 9.5
    assert stats.predict("LIN", 1.5, 2.0, y=f)["values"]["x"] == 4.0


@pytest.mark.parametrize("model", ["LN", "EXP", "PWR"])
def test_predict_roundtrip(model):
    a, b = 2.0, 1.7
    y = stats.predict(model, a, b, x=3.0)["values"]["y"]
    x = stats.predict(model, a, b, y=y)["values"]["x"]
    assert x == pytest.approx(3.0)


def test_predict_errors():
    assert not stats.predict("LIN", 1, 1)["ok"]
    assert not stats.predict("LIN", 1, 1, x=1, y=2)["ok"]
    assert not stats.predict("EXP", 2, 1.5, y=-1)["ok"]
    assert not stats.predict("PWR", 2, 1.5, y=0)["ok"]
    assert not stats.predict("LN", 1, 1, x=0)["ok"]
    assert not stats.predict("LIN", 1, 0, y=3)["ok"]
    assert not stats.predict("EXP", 1, 10.0, x=1e5)["ok"]
