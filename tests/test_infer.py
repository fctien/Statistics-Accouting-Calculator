"""信賴區間與檢定（engine/infer.py）與 bridge infer/* 路由測試。"""
import json
import math

import pytest

from engine import infer as inf
from engine.bridge import call
from golden import runner
from tests.conftest import rel_close

ROUTES = ("ci_mean_z", "ci_mean_t", "ci_prop", "t1", "t2", "tpaired",
          "chi_gof", "chi_ind")


def _call(req):
    return json.loads(call(json.dumps(req)))


def _req(action, **inputs):
    return {"sheet": "infer", "action": action, "inputs": inputs,
            "settings": {}}


def _r(action, **inputs):
    return _call(_req(action, **inputs))


def _v(action, **inputs):
    r = _r(action, **inputs)
    assert r["ok"], r
    return r["values"]


def _bad(action, field=None, text=None, **inputs):
    r = _r(action, **inputs)
    assert not r["ok"], r
    if field is not None:
        assert r["field"] == field, r
    if text is not None:
        assert text in r["error"], r
    return r


def _mean(xs):
    return sum(xs) / len(xs)


def _var(xs):
    m = _mean(xs)
    return sum((x - m) ** 2 for x in xs) / (len(xs) - 1)


# ---------------------------------------------------------------- golden

def test_infer_golden(golden_cases):
    cases = golden_cases("infer")
    assert len(cases) >= 90
    assert {c["call"]["action"] for c in cases} == set(ROUTES)
    assert runner.run(cases, _call) == []


def test_infer_golden_three_per_kind(golden_cases):
    """每種（動作、輸出鍵、單雙尾／合併或 Welch）至少 3 筆。"""
    count = {}
    for c in golden_cases("infer"):
        inp = c["call"]["inputs"]
        key = (c["call"]["action"], c["expect_key"],
               inp.get("TAILS"), inp.get("EQUAL_VAR"))
        count[key] = count.get(key, 0) + 1
    short = [k for k, n in count.items() if n < 3]
    assert not short, short


def test_infer_golden_pure_relative(golden_cases):
    """runner 以 max(1,|b|) 為底；逐筆另以純相對誤差 1e-9 檢查（p 值很小時仍要準）。"""
    bad = []
    for c in golden_cases("infer"):
        got = _call(c["call"])["values"][c["expect_key"]]
        exp = c["expected"]
        if abs(got - exp) > 1e-9 * abs(exp):
            bad.append((c["id"], got, exp))
    assert not bad, bad


def test_golden_has_small_and_unequal_samples(golden_cases):
    cases = golden_cases("infer")
    sizes = [len(c["call"]["inputs"]["X"]) for c in cases
             if isinstance(c["call"]["inputs"].get("X"), list)]
    assert min(sizes) <= 3
    unequal = [c for c in cases if c["call"]["action"] == "t2"
               and len(c["call"]["inputs"]["X"])
               != len(c["call"]["inputs"]["Y"])]
    assert len(unequal) >= 3


# ---------------------------------------------------------------- 結論文字

# p(雙尾, μ0=11.9) ≈ 0.027
_XS = [12.1, 11.8, 12.6, 12.3, 11.9, 12.4, 12.0, 12.7]


def test_conclusion_follows_alpha():
    v = _v("t1", X=_XS, MU0=11.9, TAILS=2)
    assert 0.01 < v["p"] < 0.05
    assert v["alpha"] == 0.05
    assert v["reject"] is True
    assert v["conclusion"] == "在 α=0.05 下拒絕 H0"
    v = _v("t1", X=_XS, MU0=11.9, TAILS=2, ALPHA=0.01)
    assert v["reject"] is False
    assert v["conclusion"] == "在 α=0.01 下不拒絕 H0"
    v = _v("t1", X=_XS, MU0=11.9, TAILS=2, ALPHA=0.1)
    assert v["conclusion"] == "在 α=0.1 下拒絕 H0"


def test_conclusion_present_in_every_test():
    for action, inp in (
            ("t2", {"X": [1, 2, 3, 4], "Y": [2, 3, 5, 7, 9]}),
            ("tpaired", {"X": [1, 2, 3.5], "Y": [1.2, 2.5, 3]}),
            ("chi_gof", {"OBS": [10, 20, 30]}),
            ("chi_ind", {"TABLE": [[10, 20], [30, 15]]})):
        v = _v(action, ALPHA=0.2, **inp)
        word = "拒絕 H0" if v["reject"] else "不拒絕 H0"
        assert v["conclusion"] == "在 α=0.2 下" + word
        assert (v["p"] <= 0.2) == v["reject"]


# ---------------------------------------------------------------- 定義與性質

def test_ci_mean_z_definition():
    v = _v("ci_mean_z", MEAN=50, SIGMA=8, N=36, CONF=0.95)
    assert rel_close(v["z_crit"], 1.959963984540054, 1e-12)
    assert rel_close(v["margin"], 1.959963984540054 * 8 / 6, 1e-12)
    assert rel_close(v["lower"] + v["upper"], 100, 1e-14)


def test_ci_mean_t_summary_equals_raw_data():
    raw = _v("ci_mean_t", X=_XS, CONF=0.95)
    s = _v("ci_mean_t", MEAN=raw["mean"], SX=raw["sx"], N=raw["n"],
           CONF=0.95)
    assert raw["df"] == 7 and isinstance(raw["df"], int)
    for k in ("t_crit", "margin", "lower", "upper", "se"):
        assert rel_close(s[k], raw[k], 1e-13), k


def test_ci_prop_wald_and_wilson():
    v = _v("ci_prop", X=45, N=100, CONF=0.95)
    assert v["p_hat"] == 0.45
    assert rel_close(v["se"], math.sqrt(0.45 * 0.55 / 100), 1e-14)
    assert v["method"] == "Wald" and v["wilson_method"] == "Wilson"
    assert v["wilson_lower"] < v["p_hat"] < v["wilson_upper"]
    assert r_ok_no_warning("ci_prop", X=45, N=100, CONF=0.95)


def r_ok_no_warning(action, **inputs):
    r = _r(action, **inputs)
    return r["ok"] and r["warnings"] == []


def test_ci_prop_extremes_stay_in_unit_interval():
    v = _v("ci_prop", X=0, N=30, CONF=0.95)
    assert v["lower"] == 0 and v["upper"] == 0          # Wald 退化
    assert v["wilson_lower"] == 0 and 0 < v["wilson_upper"] < 0.2
    v = _v("ci_prop", X=30, N=30, CONF=0.95)
    assert 0.8 < v["wilson_lower"] < 1
    assert rel_close(v["wilson_upper"], 1, 1e-14)


def test_t_one_sided_complement():
    """less 與 greater 的 p 值相加為 1；同方向單尾為雙尾的一半。"""
    for action, inp in (("t1", {"X": _XS, "MU0": 12}),
                        ("t2", {"X": [5, 6, 7, 9], "Y": [4, 4.5, 6, 5, 3]}),
                        ("tpaired", {"X": [5, 6, 7, 9], "Y": [4, 6.5, 6, 5]})):
        two = _v(action, TAILS=2, **inp)["p"]
        less = _v(action, TAILS=1, ALT="less", **inp)["p"]
        greater = _v(action, TAILS=1, ALT="greater", **inp)["p"]
        assert abs(less + greater - 1) < 1e-14
        assert rel_close(min(less, greater), two / 2, 1e-14)


def test_t2_pooled_and_welch_df():
    xs, ys = [3.1, 2.9, 3.4], [2.5, 2.7, 2.2, 2.6, 2.4]
    v = _v("t2", X=xs, Y=ys, EQUAL_VAR=True)
    assert v["df"] == 6 and isinstance(v["df"], int)
    assert v["method"] == "pooled"
    a, b = _var(xs) / 3, _var(ys) / 5
    welch = (a + b) ** 2 / (a * a / 2 + b * b / 4)
    w = _v("t2", X=xs, Y=ys, EQUAL_VAR=False)
    assert w["method"] == "Welch"
    assert rel_close(w["df"], welch, 1e-13)
    assert w["df"] != int(w["df"])
    # 預設（EQUAL_VAR 省略）為 Welch
    assert _v("t2", X=xs, Y=ys)["method"] == "Welch"


def test_paired_equals_one_sample_on_differences():
    xs, ys = [200, 210, 190, 220, 205, 215], [195, 200, 192, 210, 198, 207]
    p = _v("tpaired", X=xs, Y=ys)
    o = _v("t1", X=[x - y for x, y in zip(xs, ys)], MU0=0)
    for k in ("t", "df", "p"):
        assert rel_close(p[k], o[k], 1e-13), k


def test_chi_gof_df_and_expected():
    v = _v("chi_gof", OBS=[45, 35, 20], PROBS=[0.5, 0.3, 0.2])
    assert v["df"] == 2
    assert all(rel_close(a, b, 1e-14)
               for a, b in zip(v["expected"], [50, 30, 20]))
    u = _v("chi_gof", OBS=[18, 22, 20, 25, 15])
    assert u["df"] == 4 and u["expected"] == [20.0] * 5
    assert rel_close(u["chi2"], (4 + 4 + 0 + 25 + 25) / 20, 1e-14)


def test_chi_ind_df_and_expected_table():
    table = [[25, 30, 45], [35, 20, 15]]
    v = _v("chi_ind", TABLE=table)
    assert v["df"] == 2                         # (r−1)(c−1)，不是 r·c−1
    v3 = _v("chi_ind", TABLE=[[10, 4, 6], [3, 8, 9], [2, 1, 3]])
    assert v3["df"] == 4
    e = v["expected"]
    assert len(e) == 2 and all(len(row) == 3 for row in e)
    assert rel_close(e[0][0], 100 * 60 / 170, 1e-14)
    for i, row in enumerate(table):
        assert rel_close(sum(e[i]), sum(row), 1e-14)


def test_tiny_p_values_are_positive_and_accurate():
    """p 值以尾端直接算（不經 1−cdf）：極小 p 值仍有相對精度。"""
    v = _v("chi_gof", OBS=[500, 100, 100], PROBS=[0.2, 0.4, 0.4])
    # df=2 時右尾＝exp(−χ²/2)；1−cdf 會得到 0
    assert v["p"] > 0
    assert abs(v["p"] - math.exp(-v["chi2"] / 2)) <= 1e-11 * v["p"]
    xs = [100.0, 100.1, 99.9, 100.05, 99.95, 100.02]
    t = _v("t1", X=xs, MU0=90, TAILS=1, ALT="greater")
    assert 0 < t["p"] < 1e-8
    ref = json.loads(call(json.dumps({
        "sheet": "dist", "action": "t", "settings": {},
        "inputs": {"FUNC": "cdf", "DF": 5, "X": t["t"]}})))["values"]
    assert t["p"] == ref["right"]
    big = _v("t1", X=xs, MU0=90, TAILS=1, ALT="less")["p"]
    assert abs(big - (1 - t["p"])) < 1e-15


# ---------------------------------------------------------------- 警告

def test_warnings():
    r = _r("ci_prop", X=3, N=20, CONF=0.95)
    assert r["ok"] and "樣本太小，常態近似可能不準" in r["warnings"]
    r = _r("ci_prop", X=18, N=20, CONF=0.95)       # n(1−p̂)=2 < 5
    assert r["ok"] and "樣本太小，常態近似可能不準" in r["warnings"]
    r = _r("chi_gof", OBS=[8, 12, 3, 2], EXP=[10, 10, 2.5, 2.5])
    assert r["ok"] and any("期望次數 < 5" in w for w in r["warnings"])
    r = _r("chi_gof", OBS=[30, 30, 40])
    assert r["ok"] and r["warnings"] == []
    r = _r("chi_ind", TABLE=[[10, 4, 6], [3, 8, 9], [2, 1, 3]])
    assert r["ok"] and any("期望次數 < 5" in w for w in r["warnings"])
    # 剛好 20%（5 格中 1 格）不警告
    r = _r("chi_gof", OBS=[20, 20, 20, 20, 3],
           PROBS=[0.24, 0.24, 0.24, 0.24, 0.04])
    assert r["ok"] and r["warnings"] == []
    # EXP 總和與 OBS 總和不同：回錯誤（不只是警告）
    _bad("chi_gof", "EXP", "期望次數總和必須等於觀察次數總和，或改用機率 PROBS",
         OBS=[10, 20], EXP=[10, 25])
    assert _r("chi_gof", OBS=[10, 20], EXP=[10, 20 + 1e-8])["ok"]


# ---------------------------------------------------------------- 錯誤路徑

def test_errors_sample_size_and_zero_variance():
    _bad("t1", "X", "n", X=[5], MU0=1)
    _bad("t1", "X", "t 統計量未定義", X=[3, 3, 3], MU0=1)
    _bad("ci_mean_t", "X", None, X=[4], CONF=0.95)
    _bad("ci_mean_t", "X", "Sx", X=[2, 2], CONF=0.95)
    _bad("ci_mean_t", "SX", None, MEAN=1, SX=0, N=5, CONF=0.95)
    _bad("ci_mean_t", "N", None, MEAN=1, SX=2, N=1, CONF=0.95)
    _bad("t2", "Y", None, X=[1, 2, 3], Y=[4])
    _bad("t2", "X", None, X=[1], Y=[4, 5])
    _bad("t2", None, "t 統計量未定義", X=[2, 2, 2], Y=[5, 5], EQUAL_VAR=True)
    _bad("t2", None, "t 統計量未定義", X=[2, 2, 2], Y=[5, 5], EQUAL_VAR=False)
    _bad("tpaired", None, "t 統計量未定義", X=[2, 3, 4], Y=[1, 2, 3])
    _bad("tpaired", "Y", "長度", X=[2, 3, 4], Y=[1, 2])
    _bad("tpaired", "X", None, X=[2], Y=[1])
    _bad("ci_mean_z", "SIGMA", None, MEAN=1, SIGMA=0, N=5, CONF=0.95)
    _bad("ci_mean_z", "N", None, MEAN=1, SIGMA=1, N=0, CONF=0.95)
    _bad("ci_prop", "X", None, X=11, N=10, CONF=0.95)
    _bad("ci_prop", "N", None, X=0, N=0, CONF=0.95)


# 浮點雜訊造成的「假」變異數：差值數學上全為 1，浮點相減後只差 1e-16 級
_NOISE_X = [1.1, 2.2, 3.3, 4.4]
_NOISE_Y = [0.1, 1.2, 2.3, 3.4]
_PRE = [12.3, 15.7, 9.8, 11.1, 14.6, 10.9]
_POST = [x + 1 for x in _PRE]


def test_float_noise_variance_is_zero():
    """標準差 ≤ 64·eps·max|x| 視為 0：回錯誤，不給 t≈1e16 的假「拒絕 H0」。"""
    diffs = [x - y for x, y in zip(_NOISE_X, _NOISE_Y)]
    assert min(diffs) != max(diffs)          # 確實含捨入雜訊
    _bad("tpaired", None, "差值的標準差為 0", X=_NOISE_X, Y=_NOISE_Y)
    _bad("tpaired", None, "t 統計量未定義", X=_POST, Y=_PRE)
    _bad("t1", "X", "t 統計量未定義", X=diffs, MU0=0)
    _bad("ci_mean_t", "X", "Sx", X=diffs, CONF=0.95)
    _bad("t2", None, "t 統計量未定義", X=diffs, Y=[2.0, 2.0, 2.0],
         EQUAL_VAR=True)
    _bad("t2", None, "t 統計量未定義", X=diffs, Y=[2.0, 2.0, 2.0],
         EQUAL_VAR=False)
    # 只有一組為 0 時 Welch／合併仍可計算
    assert _v("t2", X=diffs, Y=[1.5, 2.0, 2.7])["sx"] == 0
    # 一般小幅差異不受影響
    v = _v("tpaired", X=[x + 1 + 0.1 * (i % 2) for i, x in enumerate(_PRE)],
           Y=_PRE)
    assert v["sd"] > 0
    assert _v("t1", X=[1e6, 1e6 + 1e-6, 1e6 + 2e-6], MU0=1e6)["sx"] > 0


def test_constant_shift_randomized_always_errors():
    """前後測恰差 1（一、兩位小數，基數 1e2～1e6）：差值的捨入雜訊與原始資料的
    ulp 同級，門檻須以原始 X、Y 的大小為尺度；每一組都必須回錯誤（固定種子）。"""
    import random
    rng = random.Random(20261028)
    passed = []
    for base in (1e2, 1e3, 1e4, 1e5, 1e6):
        for dec in (1, 2):
            for _ in range(200):
                pre = [round(base * (1 + rng.random()), dec)
                       for _ in range(rng.randint(3, 8))]
                post = [round(p + 1, dec) for p in pre]
                r = _r("tpaired", X=post, Y=pre)
                if r["ok"]:
                    passed.append((base, dec, pre, r["values"]["t"]))
                else:
                    assert "t 統計量未定義" in r["error"], r
    assert not passed, passed[:3]


def test_legitimate_small_variance_still_computes():
    v = _v("t1", X=[1e9 + 0.5, 1e9 + 0.6, 1e9 + 0.7], MU0=1e9)
    assert abs(v["sx"] - 0.1) < 1e-5
    assert abs(v["mean"] - (1e9 + 0.6)) < 1e-5
    v = _v("tpaired", X=[1e9 + 0.5, 1e9 + 0.6, 1e9 + 0.8],
           Y=[1e9, 1e9, 1e9])
    assert v["sd"] > 0.1
    v = _v("t1", X=[1e6, 1e6 + 1e-6, 1e6 + 2e-6], MU0=1e6)
    assert abs(v["sx"] - 1e-6) < 1e-9


def test_zero_sd_messages_have_no_stray_space():
    for action, inp in (("tpaired", {"X": [2, 3, 4], "Y": [1, 2, 3]}),
                        ("t1", {"X": [3, 3, 3], "MU0": 1}),
                        ("t2", {"X": [2, 2], "Y": [5, 5],
                                "EQUAL_VAR": True})):
        msg = _r(action, **inp)["error"]
        assert "標準差 為" not in msg and "為 0" in msg, msg


def test_errors_tables_and_probs():
    _bad("chi_ind", "TABLE", "總和為 0", TABLE=[[0, 0], [3, 4]])
    _bad("chi_ind", "TABLE", "總和為 0", TABLE=[[0, 5], [0, 4]])
    _bad("chi_ind", "TABLE", None, TABLE=[[1, 2, 3], [4, 5]])
    _bad("chi_ind", "TABLE", None, TABLE=[[1, 2, 3]])
    _bad("chi_ind", "TABLE", None, TABLE=[[1], [2]])
    _bad("chi_ind", "TABLE", None, TABLE=[[1, -2], [3, 4]])
    _bad("chi_ind", "TABLE", None, TABLE=[[1, True], [3, 4]])
    _bad("chi_ind", "TABLE", None, TABLE="abc")
    _bad("chi_ind", "TABLE", None, TABLE=None)
    _bad("chi_gof", "PROBS", "1", OBS=[1, 2, 3], PROBS=[0.5, 0.3, 0.3])
    _bad("chi_gof", "PROBS", None, OBS=[1, 2, 3], PROBS=[0.5, 0.5])
    _bad("chi_gof", "PROBS", None, OBS=[1, 2, 3], PROBS=[0.5, 0.5, 0])
    _bad("chi_gof", "EXP", None, OBS=[1, 2], EXP=[1, 2, 3])
    _bad("chi_gof", "EXP", None, OBS=[1, 2], EXP=[0, 3])
    _bad("chi_gof", None, None, OBS=[1, 2], EXP=[1, 2], PROBS=[0.5, 0.5])
    _bad("chi_gof", "OBS", None, OBS=[1, -2, 3])
    _bad("chi_gof", "OBS", None, OBS=[0, 0, 0])
    _bad("chi_gof", "OBS", None, OBS=[5])
    # 1±1e-9 以內視為 1
    assert _r("chi_gof", OBS=[1, 2, 3], PROBS=[0.5, 0.3, 0.2 + 5e-10])["ok"]


def test_errors_tails_alt_alpha_conf():
    _bad("t1", "TAILS", None, X=_XS, MU0=12, TAILS=3)
    _bad("t1", "TAILS", None, X=_XS, MU0=12, TAILS=1.5)
    _bad("t1", "ALT", None, X=_XS, MU0=12, TAILS=1)
    _bad("t1", "ALT", None, X=_XS, MU0=12, TAILS=1, ALT="bigger")
    _bad("t2", "ALT", None, X=_XS, Y=[1, 2], TAILS=2, ALT="two")
    _bad("t1", "ALT", "雙尾", X=_XS, MU0=12, TAILS=2, ALT="less")
    _bad("t2", "ALT", "雙尾", X=_XS, Y=[1, 2], ALT="greater")   # TAILS 預設 2
    _bad("tpaired", "ALT", None, X=[1, 2, 4], Y=[0, 2, 1], TAILS=2,
         ALT="greater")
    _bad("t1", "ALPHA", None, X=_XS, MU0=12, ALPHA=0)
    _bad("t1", "ALPHA", None, X=_XS, MU0=12, ALPHA=1)
    _bad("chi_gof", "ALPHA", None, OBS=[1, 2], ALPHA=-0.1)
    _bad("ci_mean_z", "CONF", None, MEAN=1, SIGMA=1, N=5, CONF=1)
    _bad("ci_prop", "CONF", None, X=1, N=5, CONF=0)
    _bad("ci_mean_t", "CONF", None, X=_XS)
    _bad("t2", "EQUAL_VAR", None, X=_XS, Y=[1, 2], EQUAL_VAR="yes")
    _bad("ci_mean_t", None, "擇一", X=_XS, MEAN=1, CONF=0.95)
    _bad("ci_mean_t", "MEAN", None, SX=1, N=5, CONF=0.95)
    _bad("t1", "MU0", None, X=_XS)


def test_engine_direct_errors():
    """直接呼叫引擎（不經 bridge）也要擋下錯誤輸入，絕不擲例外或回 inf／nan。"""
    assert not inf.t1([1, "a"], 0)["ok"]
    assert not inf.t1(None, 0)["ok"]
    assert not inf.t1([1, 2, float("nan")], 0)["ok"]
    assert not inf.t2([1, 2], [3, 4], equal_var="x")["ok"]
    assert not inf.ci_mean_z(1, 1, 2.5, 0.95)["ok"]
    assert not inf.ci_prop(True, 5, 0.95)["ok"]
    assert not inf.chi_ind([[1, 2], [3, float("inf")]])["ok"]
    assert not inf.chi_gof([1, 2], probs="ab")["ok"]


def test_overflow_is_error_not_inf():
    r = _r("t1", X=[1e300, -1e300, 5e299], MU0=0)
    assert not r["ok"]
    r = _r("chi_gof", OBS=[1e300, 1], EXP=[1e-300, 1])
    assert not r["ok"]


# ---------------------------------------------------------------- 與 scipy 比對

def test_against_scipy():
    st = pytest.importorskip("scipy.stats")
    import random
    rng = random.Random(20261028)
    for _ in range(25):
        n1, n2 = rng.randint(2, 30), rng.randint(2, 30)
        xs = [round(rng.gauss(10, 3), 3) for _ in range(n1)]
        ys = [round(rng.gauss(11, 5), 3) for _ in range(n2)]
        for eq in (True, False):
            v = _v("t2", X=xs, Y=ys, EQUAL_VAR=eq)
            ref = st.ttest_ind(xs, ys, equal_var=eq)
            assert rel_close(v["t"], ref.statistic, 1e-10)
            assert abs(v["p"] - ref.pvalue) <= 1e-10 * ref.pvalue + 1e-15
        v = _v("t1", X=xs, MU0=10)
        ref = st.ttest_1samp(xs, 10)
        assert abs(v["p"] - ref.pvalue) <= 1e-10 * ref.pvalue + 1e-15
        m = min(n1, n2)
        v = _v("tpaired", X=xs[:m], Y=ys[:m])
        ref = st.ttest_rel(xs[:m], ys[:m])
        assert abs(v["p"] - ref.pvalue) <= 1e-10 * ref.pvalue + 1e-15
        k = rng.randint(2, 6)
        obs = [rng.randint(0, 40) for _ in range(k)]
        obs[0] += 1
        v = _v("chi_gof", OBS=obs)
        ref = st.chisquare(obs)
        assert abs(v["p"] - ref.pvalue) <= 1e-10 * ref.pvalue + 1e-15
        r, c = rng.randint(2, 4), rng.randint(2, 4)
        table = [[rng.randint(1, 30) for _ in range(c)] for _ in range(r)]
        v = _v("chi_ind", TABLE=table)
        chi, p, dof, _ = st.chi2_contingency(table, correction=False)
        assert v["df"] == dof
        assert rel_close(v["chi2"], chi, 1e-12)
        assert abs(v["p"] - p) <= 1e-10 * p + 1e-15
