"""機率分配（engine/dist.py）與 bridge dist/* 路由測試。"""
import json
import math

import pytest

from engine import dist as D
from engine.bridge import call
from golden import runner
from tests.conftest import rel_close

ROUTES = ("normal", "t", "chi2", "binom", "poisson")


def _call(req):
    return json.loads(call(json.dumps(req)))


def _req(action, **inputs):
    return {"sheet": "dist", "action": action, "inputs": inputs,
            "settings": {}}


def _v(action, **inputs):
    r = _call(_req(action, **inputs))
    assert r["ok"], r
    return r["values"]


# ---------------------------------------------------------------- golden

def test_dist_golden(golden_cases):
    cases = golden_cases("dist")
    assert len(cases) >= 60
    assert {c["call"]["action"] for c in cases} == set(ROUTES)
    assert runner.run(cases, _call) == []


def test_dist_golden_each_function_three_cases(golden_cases):
    """每個分配的每種功能（含右尾／雙尾）至少 3 筆。"""
    count = {}
    for c in golden_cases("dist"):
        key = (c["call"]["action"], c["call"]["inputs"]["FUNC"],
               c["expect_key"])
        count[key] = count.get(key, 0) + 1
    need = [(d, f, "value") for d in ("normal", "t", "chi2")
            for f in ("pdf", "cdf", "inv")]
    need += [(d, f, "value") for d in ("binom", "poisson")
             for f in ("pmf", "cdf")]
    need += [(d, "cdf", "right") for d in ROUTES]
    need += [(d, "cdf", "two") for d in ("normal", "t")]
    need += [(d, "inv", "right") for d in ("normal", "t", "chi2")]
    need += [(d, "inv", "two") for d in ("normal", "t")]
    short = [k for k in need if count.get(k, 0) < 3]
    assert not short, short


def test_dist_golden_pure_relative(golden_cases):
    """runner 以 max(1,|b|) 為底，極小值（< 1e-9）會空過；這裡逐筆以純相對誤差檢查。
    極小尾端要求 1e-7（brief），其餘一併以 1e-9 純相對誤差檢查（更嚴）。"""
    bad = []
    tiny = 0
    for c in golden_cases("dist"):
        got = _call(c["call"])["values"][c["expect_key"]]
        exp = c["expected"]
        tol = 1e-7 if abs(exp) < 1e-9 else 1e-9
        tiny += abs(exp) < 1e-9
        if abs(got - exp) > tol * abs(exp):
            bad.append((c["id"], got, exp))
    assert tiny >= 8
    assert not bad, bad


# ---------------------------------------------------------------- 特殊函式

def test_betainc_known_values():
    # I_x(1,1) = x；I_x(a,1) = x^a；I_0.5(a,a) = 0.5
    i, j = D.betainc(1.0, 1.0, 0.3)
    assert rel_close(i, 0.3, 1e-14) and rel_close(j, 0.7, 1e-14)
    i, _ = D.betainc(3.0, 1.0, 0.4)
    assert rel_close(i, 0.064, 1e-14)
    i, j = D.betainc(7.5, 7.5, 0.5)
    assert rel_close(i, 0.5, 1e-14) and rel_close(j, 0.5, 1e-14)
    assert D.betainc(2.0, 3.0, 0.0) == (0.0, 1.0)
    assert D.betainc(2.0, 3.0, 1.0) == (1.0, 0.0)


def test_gammainc_known_values():
    # P(1,x) = 1 - e^-x；Q(1,x) = e^-x（直接算，不經 1-P）
    p, q = D.gammainc(1.0, 0.5)
    assert rel_close(p, 1 - math.exp(-0.5), 1e-14)
    p, q = D.gammainc(1.0, 50.0)
    assert abs(q - math.exp(-50.0)) <= 1e-13 * math.exp(-50.0)
    assert D.gammainc(2.0, 0.0) == (0.0, 1.0)


def test_continued_fraction_not_converged_returns_error(monkeypatch):
    """未收斂一律回錯誤，不回部分和。"""
    monkeypatch.setattr(D, "MAX_ITER", 2)
    for fn in (lambda: D.betainc(50.0, 60.0, 0.45),
               lambda: D.gammainc(50.0, 49.0),
               lambda: D.gammainc(50.0, 60.0)):
        with pytest.raises(D.NotConverged):
            fn()
    r = D.t_dist("cdf", 30, 0.7)
    assert not r["ok"] and "未收斂" in r["error"]
    r = D.chi2("cdf", 100, 99)
    assert not r["ok"] and "未收斂" in r["error"]
    r = _call(_req("poisson", FUNC="cdf", LAMBDA=100, K=100))
    assert not r["ok"] and "未收斂" in r["error"]


# ---------------------------------------------------------------- 性質

def test_cdf_monotone_and_tails_sum_to_one():
    for xs, fn in (
            ([-9, -3, -1, -0.1, 0, 0.1, 1, 3, 9],
             lambda x: _v("normal", FUNC="cdf", MU=0, SIGMA=1, X=x)),
            ([-50, -4, -1, -0.01, 0, 0.01, 1, 4, 50],
             lambda x: _v("t", FUNC="cdf", DF=3.5, X=x)),
            ([0, 0.01, 0.5, 2, 5, 10, 40, 100],
             lambda x: _v("chi2", FUNC="cdf", DF=6, X=x)),
            (list(range(0, 21)),
             lambda k: _v("binom", FUNC="cdf", N=20, P=0.35, K=k)),
            (list(range(0, 30)),
             lambda k: _v("poisson", FUNC="cdf", LAMBDA=7.5, K=k))):
        prev = -1.0
        for x in xs:
            v = fn(x)
            assert v["value"] >= prev
            assert abs(v["value"] + v["right"] - 1) <= 1e-14
            prev = v["value"]


def test_t_symmetry_sides():
    """t cdf 對稱關係：負值的左尾＝正值的右尾（選錯一側會被抓到）。"""
    for df in (1, 4, 2.5, 30):
        for t in (0.3, 1.7, 6.0):
            neg = _v("t", FUNC="cdf", DF=df, X=-t)
            pos = _v("t", FUNC="cdf", DF=df, X=t)
            assert neg["value"] < 0.5 < pos["value"]
            assert rel_close(neg["value"], pos["right"], 1e-15)
            assert rel_close(neg["two"], 2 * neg["value"], 1e-14)


def test_inverse_round_trip():
    for p in (1e-12, 1e-5, 0.025, 0.3, 0.5, 0.7, 0.975, 1 - 1e-9):
        for action, params in (("normal", {"MU": 3, "SIGMA": 2}),
                               ("t", {"DF": 1}), ("t", {"DF": 2.5}),
                               ("t", {"DF": 40}), ("chi2", {"DF": 0.7}),
                               ("chi2", {"DF": 4}), ("chi2", {"DF": 55.5})):
            inv = _v(action, FUNC="inv", PROB=p, **params)
            x = inv["value"]
            back = _v(action, FUNC="cdf", X=x, **params)["value"]
            assert abs(back - p) <= 1e-12 * min(p, 1 - p) + 1e-15, \
                (action, params, p, x, back)
            xr = inv["right"]
            right = _v(action, FUNC="cdf", X=xr, **params)["right"]
            assert abs(right - p) <= 1e-12 * min(p, 1 - p) + 1e-15
            if "two" in inv:
                two = _v(action, FUNC="cdf", X=inv["two"], **params)["two"]
                assert abs(two - p) <= 1e-12 * min(p, 1 - p) + 1e-15


def test_pmf_sums_to_cdf():
    total = 0.0
    for k in range(0, 13):
        total += _v("binom", FUNC="pmf", N=12, P=0.42, K=k)["value"]
        assert rel_close(total, _v("binom", FUNC="cdf", N=12, P=0.42,
                                   K=k)["value"], 1e-13)
    total = 0.0
    for k in range(0, 25):
        total += _v("poisson", FUNC="pmf", LAMBDA=4.2, K=k)["value"]
        assert rel_close(total, _v("poisson", FUNC="cdf", LAMBDA=4.2,
                                   K=k)["value"], 1e-13)


def test_poisson_cdf_includes_k0_term():
    lam = 2.5
    v = _v("poisson", FUNC="cdf", LAMBDA=lam, K=0)
    assert rel_close(v["value"], math.exp(-lam), 1e-14)
    v = _v("poisson", FUNC="cdf", LAMBDA=lam, K=1)
    assert rel_close(v["value"], math.exp(-lam) * (1 + lam), 1e-14)


def test_binom_degenerate_p():
    assert _v("binom", FUNC="pmf", N=5, P=0, K=0)["value"] == 1.0
    assert _v("binom", FUNC="pmf", N=5, P=0, K=2)["value"] == 0.0
    assert _v("binom", FUNC="cdf", N=5, P=1, K=4)["value"] == 0.0
    assert _v("binom", FUNC="cdf", N=5, P=1, K=5)["value"] == 1.0
    assert _v("binom", FUNC="pmf", N=5, P=1, K=5)["value"] == 1.0


def test_chi2_pdf_at_zero():
    assert _v("chi2", FUNC="pdf", DF=2, X=0)["value"] == 0.5
    assert _v("chi2", FUNC="pdf", DF=3, X=0)["value"] == 0.0
    r = _call(_req("chi2", FUNC="pdf", DF=1, X=0))
    assert not r["ok"] and r["field"] == "X"


def test_output_keys():
    assert set(_v("normal", FUNC="pdf", MU=0, SIGMA=1, X=0)) == {"value"}
    assert set(_v("normal", FUNC="cdf", MU=0, SIGMA=1, X=0)) == {
        "value", "right", "two"}
    assert set(_v("t", FUNC="inv", DF=5, PROB=0.1)) == {
        "value", "right", "two"}
    assert set(_v("chi2", FUNC="cdf", DF=5, X=1)) == {"value", "right"}
    assert set(_v("chi2", FUNC="inv", DF=5, PROB=0.1)) == {"value", "right"}
    assert set(_v("binom", FUNC="cdf", N=5, P=0.5, K=1)) == {"value", "right"}
    assert set(_v("poisson", FUNC="pmf", LAMBDA=1, K=1)) == {"value"}


def test_scipy_cross_check_random_grid():
    """（開發輔助）與 scipy 的大範圍比對；未安裝 scipy 時略過。"""
    stats = pytest.importorskip("scipy.stats")
    bad = []

    def chk(tag, got, exp, tol=None):
        # 一般 1e-11；df ≥ 1e4 時 lgamma 相減（量級 ~5e5）的捨入使誤差達 ~7e-11，
        # 極端反查（PROB=1e-300，在 ln x≈-460 上求根）亦同，放寬到 1e-10（仍遠小於 golden 的 1e-9）
        if tol is None:
            big = any(isinstance(t, (int, float)) and (t >= 1e4 or t == 1e-300)
                      for t in tag[1:])
            tol = 1e-10 if big else 1e-11
        if exp == 0:
            ok = got == 0 or abs(got) < 1e-300
        else:
            ok = abs(got - exp) <= tol * abs(exp)
        if not ok:
            bad.append((tag, got, float(exp)))

    for df in (0.3, 1, 2.5, 7, 33.3, 500, 50000):
        for x in (-1e4, -30, -2.2, -0.05, 0.05, 1, 4.4, 80):
            v = _v("t", FUNC="cdf", DF=df, X=x)
            chk(("t cdf", df, x), v["value"], stats.t.cdf(x, df))
            chk(("t right", df, x), v["right"], stats.t.sf(x, df))
            chk(("t pdf", df, x), _v("t", FUNC="pdf", DF=df, X=x)["value"],
                stats.t.pdf(x, df))
    for df in (0.3, 1, 2.5, 7, 33.3, 500, 50000):
        for x in (1e-6, 0.2, 1.5, 9, 40, 600, 52000):
            v = _v("chi2", FUNC="cdf", DF=df, X=x)
            chk(("chi2 cdf", df, x), v["value"], stats.chi2.cdf(x, df))
            chk(("chi2 right", df, x), v["right"], stats.chi2.sf(x, df))
            chk(("chi2 pdf", df, x),
                _v("chi2", FUNC="pdf", DF=df, X=x)["value"],
                stats.chi2.pdf(x, df))
    for n, p in ((1, 0.5), (30, 0.01), (200, 0.73), (5000, 0.2)):
        for k in sorted({0, 1, n // 10, n // 5, n // 2, n - 1, n}):
            v = _v("binom", FUNC="cdf", N=n, P=p, K=k)
            chk(("binom cdf", n, p, k), v["value"], stats.binom.cdf(k, n, p))
            chk(("binom right", n, p, k), v["right"], stats.binom.sf(k, n, p))
            chk(("binom pmf", n, p, k),
                _v("binom", FUNC="pmf", N=n, P=p, K=k)["value"],
                stats.binom.pmf(k, n, p), 1e-10)
    for lam in (0.01, 1, 17.5, 300, 20000):
        for k in sorted({0, 1, int(lam / 2), int(lam), int(lam * 1.5) + 3}):
            v = _v("poisson", FUNC="cdf", LAMBDA=lam, K=k)
            chk(("pois cdf", lam, k), v["value"], stats.poisson.cdf(k, lam))
            chk(("pois right", lam, k), v["right"], stats.poisson.sf(k, lam))
            chk(("pois pmf", lam, k),
                _v("poisson", FUNC="pmf", LAMBDA=lam, K=k)["value"],
                stats.poisson.pmf(k, lam), 1e-10)
    for p in (1e-300, 1e-50, 1e-8, 0.2, 0.5, 0.9, 1 - 1e-12):
        chk(("norm inv", p), _v("normal", FUNC="inv", MU=0, SIGMA=1,
                                PROB=p)["value"], stats.norm.ppf(p))
        for df in (0.5, 3, 77.7):
            if p == 1e-300 and df < 1:
                continue  # 真值超出浮點數範圍（t≈1e600、卡方≈1e-1200）；另測回錯誤
            chk(("t inv", df, p), _v("t", FUNC="inv", DF=df,
                                     PROB=p)["value"], stats.t.ppf(p, df))
            chk(("chi2 inv", df, p), _v("chi2", FUNC="inv", DF=df,
                                        PROB=p)["value"],
                stats.chi2.ppf(p, df))
    assert not bad, bad[:20]


# ---------------------------------------------------------------- 參數錯誤

@pytest.mark.parametrize("action,inputs,field", [
    ("normal", {"FUNC": "pdf", "MU": 0, "SIGMA": 0, "X": 1}, "SIGMA"),
    ("normal", {"FUNC": "cdf", "MU": 0, "SIGMA": -2, "X": 1}, "SIGMA"),
    ("normal", {"FUNC": "cdf", "MU": 0, "SIGMA": 1, "X": None}, "X"),
    ("normal", {"FUNC": "inv", "MU": 0, "SIGMA": 1, "PROB": 0}, "PROB"),
    ("normal", {"FUNC": "inv", "MU": 0, "SIGMA": 1, "PROB": 1}, "PROB"),
    ("normal", {"FUNC": "inv", "MU": 0, "SIGMA": 1, "PROB": 1.5}, "PROB"),
    ("normal", {"FUNC": "pmf", "MU": 0, "SIGMA": 1, "X": 1}, "FUNC"),
    ("normal", {"MU": 0, "SIGMA": 1, "X": 1}, "FUNC"),
    ("t", {"FUNC": "cdf", "DF": 0, "X": 1}, "DF"),
    ("t", {"FUNC": "cdf", "DF": -3, "X": 1}, "DF"),
    ("t", {"FUNC": "cdf", "DF": 2e5, "X": 1}, "DF"),
    ("t", {"FUNC": "inv", "DF": 4, "PROB": -0.1}, "PROB"),
    ("t", {"FUNC": "inv", "DF": 4, "PROB": "0.5"}, "PROB"),
    ("chi2", {"FUNC": "cdf", "DF": 0, "X": 1}, "DF"),
    ("chi2", {"FUNC": "cdf", "DF": 3, "X": -1}, "X"),
    ("chi2", {"FUNC": "inv", "DF": 3, "PROB": 0}, "PROB"),
    ("binom", {"FUNC": "pmf", "N": 10, "P": 1.2, "K": 3}, "P"),
    ("binom", {"FUNC": "pmf", "N": 10, "P": -0.1, "K": 3}, "P"),
    ("binom", {"FUNC": "pmf", "N": 10, "P": 0.3, "K": 3.5}, "K"),
    ("binom", {"FUNC": "cdf", "N": 10, "P": 0.3, "K": 11}, "K"),
    ("binom", {"FUNC": "cdf", "N": 10, "P": 0.3, "K": -1}, "K"),
    ("binom", {"FUNC": "cdf", "N": 2.5, "P": 0.3, "K": 1}, "N"),
    ("binom", {"FUNC": "cdf", "N": -1, "P": 0.3, "K": 0}, "N"),
    ("binom", {"FUNC": "inv", "N": 10, "P": 0.3, "K": 1}, "FUNC"),
    ("poisson", {"FUNC": "pmf", "LAMBDA": 0, "K": 1}, "LAMBDA"),
    ("poisson", {"FUNC": "pmf", "LAMBDA": 2, "K": -1}, "K"),
    ("poisson", {"FUNC": "cdf", "LAMBDA": 2, "K": 1.5}, "K"),
    ("poisson", {"FUNC": "cdf", "LAMBDA": 2, "K": True}, "K"),
])
def test_parameter_errors(action, inputs, field):
    r = _call({"sheet": "dist", "action": action, "inputs": inputs,
               "settings": {}})
    assert not r["ok"] and r["field"] == field, r


def test_engine_direct_errors():
    """不經 bridge 直接呼叫引擎函式，參數錯誤一樣回 err（不擲例外）。"""
    assert D.normal("cdf", 0, 0, x=1)["field"] == "SIGMA"
    assert D.t_dist("inv", 3, prob=1.0)["field"] == "PROB"
    assert D.chi2("pdf", -1, x=1)["field"] == "DF"
    assert D.binom("pmf", 5, 0.5, 6)["field"] == "K"
    assert D.poisson("cdf", -1, 0)["field"] == "LAMBDA"


def test_inverse_out_of_range_is_error():
    # df 很小、機率極小時臨界值超出浮點數範圍：回錯誤，不回假的數字
    r = _call(_req("t", FUNC="inv", DF=0.01, PROB=1e-10))
    assert not r["ok"] and r["field"] == "PROB"
    r = _call(_req("chi2", FUNC="inv", DF=0.5, PROB=1e-300))
    assert not r["ok"] and r["field"] == "PROB"


def test_t_huge_x_tail_not_zero():
    """|t| 極大時 x=v/(v+t²) 會下溢；右尾仍須是正確的正數（df 小時尾巴很厚）。"""
    v = _v("t", FUNC="cdf", DF=0.01, X=1e300)
    # 參考值：mpmath（40 位數）betainc(0.005, 0.5, 0, 0.01/(0.01+1e600)) / 2
    exp = 0.000485263285755870040261543495021861162782
    assert abs(v["right"] - exp) <= 1e-12 * exp
    assert rel_close(v["value"], 1 - exp, 1e-15)
    # df=5、t=1e200：真值 9.49e-1000 下溢為 0（不是錯誤的正數）
    v = _v("t", FUNC="cdf", DF=5, X=-1e200)
    assert v["value"] == 0.0 and v["right"] == 1.0
