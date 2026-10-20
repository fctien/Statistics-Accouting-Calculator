"""統計工作表（STAT worksheet）：單變數統計與 LIN／LN／EXP／PWR 迴歸、預測。

僅用 math 與 engine 內部匯入；無 I/O。算不出來一律回 err，不回看似正常的錯誤數字。
"""
import math

from engine.result import err, ok, is_finite

MODELS = ("LIN", "LN", "EXP", "PWR")


def _is_num(v):
    """是否為有限實數（排除 bool、nan、inf）。"""
    return (isinstance(v, (int, float)) and not isinstance(v, bool)
            and is_finite(float(v)))


def _check_list(vals, field):
    """檢查為非空、元素皆有限數的 list；回傳錯誤結果或 None。"""
    if not isinstance(vals, (list, tuple)) or len(vals) == 0:
        return err("%s 資料不可為空" % field, field)
    for v in vals:
        if not _is_num(v):
            return err("%s 含非數值或非有限數" % field, field)
    return None


def _moments(vals, weights):
    """回傳 (N, 平均, 離差平方和 Sxx)；用離差計算以維持數值穩定。"""
    n = 0
    total = 0.0
    for v, w in zip(vals, weights):
        n += w
        total += v * w
    mean = total / n
    sxx = 0.0
    for v, w in zip(vals, weights):
        sxx += w * (v - mean) ** 2
    return n, mean, sxx


def one_var(xs, fs=None):
    """單變數統計（one-variable statistics）；fs 為次數（frequency），預設全 1。"""
    bad = _check_list(xs, "X")
    if bad:
        return bad
    if fs is None:
        fs = [1] * len(xs)
    else:
        if not isinstance(fs, (list, tuple)) or len(fs) != len(xs):
            return err("次數個數須與 X 相同", "F")
        for f in fs:
            if not _is_num(f) or f < 1 or f != int(f):
                return err("次數須為 ≥ 1 的整數", "F")
    try:
        n, mean, sxx = _moments(xs, fs)
        sum_x = sum(v * w for v, w in zip(xs, fs))
        sum_x2 = sum(v * v * w for v, w in zip(xs, fs))
        values = {"n": n, "mean_x": mean, "sigma_x": math.sqrt(sxx / n),
                  "sum_x": sum_x, "sum_x2": sum_x2}
        warnings = []
        if n < 2:
            warnings.append("n=1 時無法計算樣本標準差 Sx")
        else:
            values["sx"] = math.sqrt(sxx / (n - 1))
    except (OverflowError, ValueError, ZeroDivisionError):
        return err("計算結果超出範圍（溢位）", "X")
    return ok(values, warnings)


def _transform(xs, ys, model):
    """依模型轉換資料（LN 轉 x；EXP 轉 y；PWR 兩者皆轉）；回傳 (資料, 錯誤)。"""
    tx, ty = list(xs), list(ys)
    if model in ("LN", "PWR"):
        if any(v <= 0 for v in xs):
            return None, err("%s 模式需要正數 X" % model, "X")
        tx = [math.log(v) for v in xs]
    if model in ("EXP", "PWR"):
        if any(v <= 0 for v in ys):
            return None, err("%s 模式需要正數 Y" % model, "Y")
        ty = [math.log(v) for v in ys]
    return (tx, ty), None


def two_var(xs, ys, model):
    """雙變數統計與迴歸（two-variable regression）。

    LIN：y=a+b·x；LN：y=a+b·ln x；EXP：y=a·b^x；PWR：y=a·x^b。
    r 為轉換後資料的相關係數；Sx、Sy 等描述統計為原始資料。
    """
    if model not in MODELS:
        return err("未知迴歸模式", "model")
    for vals, name in ((xs, "X"), (ys, "Y")):
        bad = _check_list(vals, name)
        if bad:
            return bad
    if len(xs) != len(ys):
        return err("X 與 Y 個數須相同", "Y")
    n = len(xs)
    if n < 2:
        return err("至少需要 2 筆資料", "X")
    if max(xs) == min(xs):
        return err("X 全部相同，無法迴歸", "X")
    if max(ys) == min(ys):
        return err("Y 全部相同，無法計算 r", "Y")
    try:
        w = [1] * n
        _, mx, sxx0 = _moments(xs, w)
        _, my, syy0 = _moments(ys, w)
        t, bad = _transform(xs, ys, model)
        if bad:
            return bad
        tx, ty = t
        _, mtx, sxx = _moments(tx, w)
        _, mty, syy = _moments(ty, w)
        sxy = sum((p - mtx) * (q - mty) for p, q in zip(tx, ty))
        if sxx == 0:
            return err("X 全部相同，無法迴歸", "X")
        if syy == 0:
            return err("Y 全部相同，無法計算 r", "Y")
        slope = sxy / sxx
        icpt = mty - slope * mtx
        r = sxy / math.sqrt(sxx * syy)
        a = math.exp(icpt) if model in ("EXP", "PWR") else icpt
        b = math.exp(slope) if model == "EXP" else slope
        values = {
            "n": n, "mean_x": mx, "sx": math.sqrt(sxx0 / (n - 1)),
            "sigma_x": math.sqrt(sxx0 / n), "mean_y": my,
            "sy": math.sqrt(syy0 / (n - 1)), "sigma_y": math.sqrt(syy0 / n),
            "a": a, "b": b, "r": r,
            "sum_x": sum(xs), "sum_x2": sum(v * v for v in xs),
            "sum_y": sum(ys), "sum_y2": sum(v * v for v in ys),
            "sum_xy": sum(p * q for p, q in zip(xs, ys)),
        }
    except (OverflowError, ValueError, ZeroDivisionError):
        return err("計算結果超出範圍（溢位）", "X")
    return ok(values)


def predict(model, a, b, x=None, y=None):
    """預測：給 x 求 Y'，或給 y 求 X'（恰給其一）。"""
    if model not in MODELS:
        return err("未知迴歸模式", "model")
    if not _is_num(a):
        return err("a 須為有限數", "a")
    if not _is_num(b):
        return err("b 須為有限數", "b")
    if (x is None) == (y is None):
        return err("須恰好給定 X 或 Y 其中之一", "X")
    given, field = (x, "X") if x is not None else (y, "Y")
    if not _is_num(given):
        return err("%s 須為有限數" % field, field)
    try:
        if x is not None:
            return _forward(model, a, b, x)
        return _inverse(model, a, b, y)
    except (OverflowError, ValueError, ZeroDivisionError):
        return err("計算結果超出範圍（溢位）", field)


def _forward(model, a, b, x):
    """由 x 求 Y'。"""
    if model in ("LN", "PWR") and x <= 0:
        return err("%s 模式需要正數 X" % model, "X")
    if model == "LIN":
        res = a + b * x
    elif model == "LN":
        res = a + b * math.log(x)
    elif model == "EXP":
        if b <= 0:
            return err("EXP 模式需要 b 為正數", "b")
        res = a * math.exp(x * math.log(b))
    else:
        res = a * math.exp(b * math.log(x))
    return ok({"y": float(res)})


def _inverse(model, a, b, y):
    """由 y 求 X'。"""
    if model == "LIN":
        if b == 0:
            return err("b 為 0，無法反求 X", "b")
        res = (y - a) / b
    elif model == "LN":
        if b == 0:
            return err("b 為 0，無法反求 X", "b")
        res = math.exp((y - a) / b)
    else:
        if a == 0:
            return err("a 為 0，無法反求 X", "a")
        q = y / a
        if q <= 0:
            return err("%s 模式需要 Y/a 為正數" % model, "Y")
        if model == "EXP":
            if b <= 0 or b == 1:
                return err("EXP 模式需要 b 為正且不等於 1", "b")
            res = math.log(q) / math.log(b)
        else:
            if b == 0:
                return err("b 為 0，無法反求 X", "b")
            res = math.exp(math.log(q) / b)
    return ok({"x": float(res)})
