"""敘述統計（engine/describe.py）與 bridge stats/describe 路由測試。"""
import json

from engine import describe as D
from engine.bridge import call
from golden import runner
from tests.conftest import rel_close


def _call(req):
    return json.loads(call(json.dumps(req)))


def _bridge(x, f=None, **settings):
    return _call({"sheet": "stats", "action": "describe", "settings": settings,
                  "inputs": {"X": x, "F": f}})


def test_describe_golden(golden_cases):
    cases = [c for c in golden_cases("stats")
             if c["call"]["action"] == "describe"]
    assert len(cases) >= 30
    assert {c["id"].split("_")[2] for c in cases} == {"a", "b", "c"}
    assert runner.run(cases, _call) == []


def test_known_values_dataset_a():
    r = D.describe([2, 4, 4, 4, 5, 5, 7, 9])
    v = r["values"]
    assert r["ok"] and r["warnings"] == []
    assert v["n"] == 8 and v["sum"] == 40 and v["mean"] == 5
    assert v["median"] == 4.5 and v["modes"] == [4]
    assert (v["min"], v["max"], v["range"]) == (2, 9, 7)
    assert (v["q1"], v["q3"], v["iqr"]) == (4.0, 5.5, 1.5)
    assert rel_close(v["sigma_x"], 2.0, 1e-12)
    assert rel_close(v["var"], 32 / 7, 1e-12)
    assert rel_close(v["cv"], v["sx"] / 5, 1e-12)


def test_quartile_position_is_n_minus_1_p():
    # n=5：Q1 位置 1.0、Q3 位置 3.0（整數位置）；(n+1)p 會得到 1.5／4.5
    v = D.describe([1, 2, 3, 4, 100])["values"]
    assert v["q1"] == 2 and v["q3"] == 4
    # n=4：位置 0.75、2.25 需要內插
    v = D.describe([10, 20, 30, 40])["values"]
    assert rel_close(v["q1"], 17.5, 1e-12)
    assert rel_close(v["q3"], 32.5, 1e-12)


def test_unsorted_input_same_as_sorted():
    xs = [9, 2, 5, 4, 7, 4, 5, 4]
    assert D.describe(xs)["values"] == D.describe(sorted(xs))["values"]


def test_n_too_small_warnings_and_omitted_keys():
    r = D.describe([7])
    v = r["values"]
    assert r["ok"]
    for k in ("var", "sx", "skew", "kurt", "cv"):
        assert k not in v
    assert v["n"] == 1 and v["mean"] == 7 and v["median"] == 7
    assert v["q1"] == 7 and v["q3"] == 7 and v["sigma_x"] == 0
    text = " ".join(r["warnings"])
    assert "n<2" in text and "n<3 無法計算偏態" in text and "n<4" in text
    r2 = D.describe([1, 2])
    assert "sx" in r2["values"] and "skew" not in r2["values"]
    assert any("n<3 無法計算偏態" in w for w in r2["warnings"])
    r3 = D.describe([1, 2, 4])
    assert "skew" in r3["values"] and "kurt" not in r3["values"]
    assert any("n<4" in w for w in r3["warnings"])
    assert "kurt" in D.describe([1, 2, 4, 8])["values"]


def test_empty_is_error():
    r = D.describe([])
    assert not r["ok"] and r["field"] == "X"
    assert not _bridge([])["ok"]


def test_all_equal_no_nan_inf():
    for xs in ([5, 5, 5, 5], [0.1, 0.1, 0.1, 0.1, 0.1]):
        r = D.describe(xs)
        v = r["values"]
        assert r["ok"]
        assert v["sx"] == 0 and v["var"] == 0 and v["range"] == 0
        assert "skew" not in v and "kurt" not in v
        assert any("偏態" in w for w in r["warnings"])
        assert any("峰態" in w for w in r["warnings"])
        assert v["modes"] == [xs[0]]
        assert _bridge(xs)["ok"]


def test_cv_zero_mean_omitted_with_warning():
    r = D.describe([-2, -1, 1, 2])
    assert r["ok"] and "cv" not in r["values"]
    assert any("CV" in w for w in r["warnings"])
    assert "sx" in r["values"]


def test_cv_uses_abs_mean():
    pos = D.describe([1, 2, 3])["values"]["cv"]
    neg = D.describe([-1, -2, -3])["values"]["cv"]
    assert rel_close(pos, neg, 1e-12) and pos > 0


def test_modes_multiple_ascending_and_none():
    r = D.describe([5, 1, 5, 3, 3, 1, 9])
    assert r["values"]["modes"] == [1, 3, 5] and r["warnings"] == []
    r = D.describe([4, 3, 2, 1])
    assert r["values"]["modes"] == []
    assert any("無眾數" in w for w in r["warnings"])
    assert D.describe([3, 3, 1])["values"]["modes"] == [3]


def test_frequencies_equivalent_to_expansion():
    xs, fs = [3, 1, 4, 1.5], [2, 3, 1, 4]
    expanded = [3, 3, 1, 1, 1, 4, 1.5, 1.5, 1.5, 1.5]
    a = D.describe(xs, fs)
    b = D.describe(expanded)
    assert a["ok"] and b["ok"]
    assert set(a["values"]) == set(b["values"])
    for k, v in b["values"].items():
        if k == "modes":
            assert a["values"][k] == v
        else:
            assert rel_close(a["values"][k], v, 1e-12), k
    assert a["warnings"] == b["warnings"]


def test_frequency_mode_counts_use_frequencies():
    # 每個 X 只列一次，但次數使 7 成為眾數
    assert D.describe([5, 7, 9], [1, 3, 1])["values"]["modes"] == [7]
    assert D.describe([5, 7, 9], [1, 1, 1])["values"]["modes"] == []
    # 重複的 X 其次數要合併計算
    assert D.describe([5, 5, 9], [1, 1, 1])["values"]["modes"] == [5]


def test_bad_frequencies():
    for fs in ([1, 2], [1, 0, 1], [1, -1, 1], [1, 1.5, 1], [True, 1, 1],
               [1, float("nan"), 1], "abc"):
        r = D.describe([1, 2, 3], fs)
        assert not r["ok"] and r["field"] == "F", fs
    assert D.describe([1, 2, 3], [2.0, 1, 1])["ok"]  # 整數值的 float 可


def test_bad_values():
    for xs in ([1, "a"], [1, True], [1, float("inf")], [float("nan")], "12",
               None):
        assert not D.describe(xs)["ok"], xs


def test_overflow_never_silent_garbage():
    r = D.describe([1e200, -1e200, 1e200, 5e199])
    if r["ok"]:
        for v in r["values"].values():
            if isinstance(v, float):
                assert v == v and abs(v) != float("inf")


def test_numerical_stability_large_offset():
    xs = [1e9 + d for d in (1, 2, 3, 4, 5, 6)]
    v = D.describe(xs)["values"]
    ref = D.describe([1, 2, 3, 4, 5, 6])["values"]
    assert rel_close(v["sx"], ref["sx"], 1e-6)
    assert abs(v["skew"] - ref["skew"]) < 1e-6
    assert rel_close(v["kurt"], ref["kurt"], 1e-6)


def test_symmetric_data_zero_skew_and_known_kurt():
    v = D.describe([1, 2, 3, 4, 5])["values"]
    assert abs(v["skew"]) < 1e-12
    assert rel_close(v["kurt"], -1.2, 1e-12)  # Excel KURT({1,2,3,4,5})


# ---- bridge 路由 ----

def test_bridge_describe_ok_and_display():
    r = _bridge([2, 4, 4, 4, 5, 5, 7, 9], decimals=2)
    assert r["ok"]
    assert r["display"]["mean"] == "5.00"
    assert r["display"]["n"] == "8"
    assert r["display"]["modes"] == ["4"]
    assert r["values"]["modes"] == [4]


def test_bridge_display_modes_empty_and_multi():
    assert _bridge([1, 2, 3])["display"]["modes"] == []
    assert _bridge([1, 1, 2, 2], decimals=3)["display"]["modes"] == ["1", "2"]


def test_bridge_with_frequencies_and_errors():
    r = _bridge([1, 2, 3], [1, 2, 1])
    assert r["ok"] and r["values"]["n"] == 4
    assert r["values"]["modes"] == [2]
    for bad in (_bridge([1, 2], [1]), _bridge([1, "a"]), _bridge(None),
                _bridge([1, 2], [0, 1]), _bridge([1e301, 1])):
        assert not bad["ok"]
    r = _call({"sheet": "stats", "action": "describe", "inputs": {}})
    assert not r["ok"] and r["field"] == "X"


def test_bridge_f_optional_missing_key():
    r = _call({"sheet": "stats", "action": "describe",
               "inputs": {"X": [1, 2, 3, 4]}})
    assert r["ok"] and r["values"]["n"] == 4


def test_bridge_warnings_passthrough():
    r = _bridge([1, 2])
    assert r["ok"] and any("n<3" in w for w in r["warnings"])


def test_bridge_one_var_unchanged():
    r = _call({"sheet": "stats", "action": "one_var",
               "inputs": {"X": [1, 2, 3]}})
    assert r["ok"] and "modes" not in r["values"]
