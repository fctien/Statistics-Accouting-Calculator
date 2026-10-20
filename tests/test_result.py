"""engine.result 統一回傳格式測試。"""
from engine.result import err, is_finite, ok


def test_ok_shape():
    assert ok({"PMT": -1.5}) == {"ok": True, "values": {"PMT": -1.5}, "warnings": []}


def test_ok_warnings_passthrough():
    assert ok({"A": 1}, ["注意"])["warnings"] == ["注意"]


def test_ok_rejects_inf():
    r = ok({"FV": float("inf")})
    assert r["ok"] is False and r["field"] == "FV"


def test_ok_rejects_neg_inf_and_nan():
    assert ok({"X": float("-inf")})["field"] == "X"
    r = ok({"A": 1.0, "Y": float("nan")})
    assert r["ok"] is False and r["field"] == "Y"


def test_ok_rejects_nonfinite_in_nested_list():
    r = ok({"rows": [[1.0, 2.0], [3.0, float("inf")]]})
    assert r["ok"] is False and r["field"] == "rows"
    assert "溢位" in r["error"]


def test_ok_accepts_nested_finite_and_non_numbers():
    v = {"rows": [[1, 2.5], [3, 4]], "label": "x", "flag": True, "n": None}
    assert ok(v)["ok"] is True


def test_err_shape():
    assert err("無解", "CF") == {"ok": False, "error": "無解", "field": "CF"}
    assert err("無解")["field"] is None


def test_is_finite():
    assert is_finite(1.0) and is_finite(0) and is_finite(-1e308)
    assert not is_finite(float("inf"))
    assert not is_finite(float("-inf"))
    assert not is_finite(float("nan"))
