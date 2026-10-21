"""TVM 貨幣時間價值（Time Value of Money）：N、I/Y、PV、PMT、FV。

方程式（i 為每期利率，k = 1 若期初付款 BGN，否則 0）：
    PV*(1+i)^N + PMT*(1+i*k)*((1+i)^N - 1)/i + FV = 0
|i| 極小時改用 PV + PMT*N + FV = 0。
僅用 math 與 engine 內部模組，維持可攜（portable）。
"""
import math

from engine.result import err, ok
from engine.solver import find_root, snap_zero_pct

_VARS = ("N", "IY", "PV", "PMT", "FV")
_ZERO_RATE = 1e-12
_OVERFLOW_MSG = "計算結果超出範圍（溢位）"


def period_rate(iy, py, cy):
    """名目年利率 IY(%) 換算為每付款期有效利率（effective rate per period）。"""
    return (1 + iy / 100 / cy) ** (cy / py) - 1


def _annuity_factor(n, i, k):
    """回傳 (a, s)：a = (1+i)^N；s = (1+i*k)*((1+i)^N - 1)/i（i≈0 時為 N）。"""
    if abs(i) < _ZERO_RATE:
        return 1.0, float(n)
    a = (1 + i) ** n
    return a, (1 + i * k) * (a - 1) / i


def tvm_residual(n, i, pv, pmt, fv, bgn):
    """TVM 方程式殘差（residual）；解為 0。可能擲 OverflowError（CPython）。"""
    a, s = _annuity_factor(n, i, 1 if bgn else 0)
    return pv * a + pmt * s + fv


def _solve_n(i, pv, pmt, fv, k):
    """解 N；無實數解回 None。"""
    if abs(i) < _ZERO_RATE:
        if pmt == 0:
            return None
        return -(pv + fv) / pmt
    p = pmt * (1 + i * k)
    den = p + pv * i
    if den == 0:
        return None
    ratio = (p - fv * i) / den
    if ratio <= 0:
        return None
    return math.log(ratio) / math.log(1 + i)


def _solve_iy(inp, py, cy):
    """解 I/Y；找不到根回錯誤。"""
    n, pv, pmt, fv = inp["N"], inp["PV"], inp["PMT"], inp["FV"]
    bgn = bool(inp.get("BGN", False))

    def f(i):
        try:
            return tvm_residual(n, i, pv, pmt, fv, bgn)
        except (OverflowError, ZeroDivisionError):
            return float("inf")

    i = find_root(f, -0.9999, 10.0, 0.01)
    if i is None:
        return err("無法求出 I/Y：現金流方向或數值不合理", "IY")
    try:
        iy = cy * ((1 + i) ** (py / cy) - 1) * 100
    except OverflowError:
        return err(_OVERFLOW_MSG, "IY")
    return ok({"IY": snap_zero_pct(iy)})


def solve(inputs, unknown):
    """依 unknown 求解 TVM 變數；回傳 ok({unknown: 值}) 或 err。"""
    if unknown not in _VARS:
        return err("未知的 TVM 變數：%s" % unknown, None)
    inp = dict(inputs)
    inp[unknown] = None
    for key in ("PY", "CY"):
        v = inp.get(key)
        if v is None:
            return err("缺少 %s" % ("P/Y" if key == "PY" else "C/Y"), key)
        if not v > 0:
            return err("%s 必須大於 0" % ("P/Y" if key == "PY" else "C/Y"), key)
    for key in _VARS:
        if key != unknown and inp.get(key) is None:
            return err("缺少 %s" % key, key)
    py, cy = inp["PY"], inp["CY"]
    bgn = bool(inp.get("BGN", False))
    k = 1 if bgn else 0

    if unknown != "N" and not inp["N"] > 0:
        return err("N 必須大於 0", "N")

    try:
        if unknown == "IY":
            return _solve_iy(inp, py, cy)

        if 1 + inp["IY"] / 100 / cy <= 0:
            return err("I/Y 數值不合理（利率低於 -100%）", "IY")
        i = period_rate(inp["IY"], py, cy)

        if unknown == "N":
            n = _solve_n(i, inp["PV"], inp["PMT"], inp["FV"], k)
            if n is None or not n > 0:
                return err("此組數值無法求出 N：現金流方向需相反", "N")
            return ok({"N": n})

        n = inp["N"]
        a, s = _annuity_factor(n, i, k)
        if unknown == "PV":
            return ok({"PV": -(inp["PMT"] * s + inp["FV"]) / a})
        if unknown == "PMT":
            if s == 0:
                return err("此組數值無法求出 PMT", "PMT")
            return ok({"PMT": -(inp["PV"] * a + inp["FV"]) / s})
        return ok({"FV": -(inp["PV"] * a + inp["PMT"] * s)})
    except (OverflowError, ZeroDivisionError):
        return err(_OVERFLOW_MSG, unknown)
