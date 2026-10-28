"""敘述統計擴充（extended descriptive statistics），供「統計」頁使用。

輸出 n、總和、平均、中位數、眾數（可多個）、極值、全距、Q1／Q3／IQR、
樣本變異數、Sx、σx、CV、偏態（SKEW）、峰態（KURT）。定義對齊 Excel：
    - 四分位數：QUARTILE.INC，線性內插位置 (n-1)·p（0 起算）
    - 偏態：SKEW（n≥3）；峰態：KURT（超額峰態 excess kurtosis，n≥4）
    - Sx＝STDEV.S、σx＝STDEV.P
統計量算不出來（n 不足、Sx 為 0、平均為 0）時省略該鍵並加 warning，絕不回 0、inf 或 nan。
可選次數 frequencies（整數 ≥ 1），以累計次數查表，不展開資料。
離差（deviation）一律以兩遍法的平均計算，不用原始動差相減。
僅用 math 與 engine 內部匯入；無 I/O。
"""
import math

from engine.result import err, ok
from engine.stats import _check_list, _is_num


def _check_freqs(xs, fs):
    """回傳 (整數次數 list, 錯誤或 None)；fs 為 None 時全 1。"""
    if fs is None:
        return [1] * len(xs), None
    if not isinstance(fs, (list, tuple)) or len(fs) != len(xs):
        return None, err("次數個數須與 X 相同", "F")
    out = []
    for f in fs:
        if not _is_num(f) or f < 1 or f != int(f):
            return None, err("次數須為 ≥ 1 的整數", "F")
        out.append(int(f))
    return out, None


def _group(xs, fs):
    """合併相同數值，回傳依數值遞增的 [(值, 總次數), ...]。"""
    counts = {}
    for v, w in zip(xs, fs):
        counts[v] = counts.get(v, 0) + w
    return sorted(counts.items())


def _at(groups, k):
    """第 k 小（0 起算）的數值；以累計次數查表。"""
    cum = 0
    for v, w in groups:
        cum += w
        if k < cum:
            return v
    return groups[-1][0]


def _quantile(groups, n, p):
    """Excel QUARTILE.INC／PERCENTILE.INC：位置 (n-1)·p 線性內插。"""
    pos = (n - 1) * p
    lo = int(math.floor(pos))
    frac = pos - lo
    a = _at(groups, lo)
    if frac == 0:
        return float(a)
    b = _at(groups, lo + 1)
    return a + (b - a) * frac


def _modes(groups):
    """回傳 (眾數 list（遞增）, 是否有眾數)；所有值都只出現一次視為無眾數。"""
    top = max(w for _, w in groups)
    if top < 2:
        return [], False
    return [v for v, w in groups if w == top], True


def describe(xs, fs=None):
    """計算敘述統計；xs 為數值 list，fs 為可選次數。"""
    bad = _check_list(xs, "X")
    if bad:
        return bad
    fs, bad = _check_freqs(xs, fs)
    if bad:
        return bad
    try:
        groups = _group(xs, fs)
        n = sum(fs)
        total = sum(v * w for v, w in zip(xs, fs))
        mean = total / n
        # 兩遍法：先求平均，再累計離差的 2、3、4 次方
        s2 = s3 = s4 = 0.0
        for v, w in zip(xs, fs):
            d = v - mean
            d2 = d * d
            s2 += w * d2
            s3 += w * d2 * d
            s4 += w * d2 * d2
        lo, hi = groups[0][0], groups[-1][0]
        if lo == hi:  # 全部相同：離差必為 0（避免平均的捨入殘差造成假的非零）
            mean = float(lo)
            s2 = s3 = s4 = 0.0
        q1 = _quantile(groups, n, 0.25)
        q3 = _quantile(groups, n, 0.75)
        values = {
            "n": n, "sum": total, "mean": mean,
            "median": _quantile(groups, n, 0.5),
            "min": lo, "max": hi, "range": hi - lo,
            "q1": q1, "q3": q3, "iqr": q3 - q1,
            "sigma_x": math.sqrt(s2 / n),
        }
        modes, has_mode = _modes(groups)
        values["modes"] = modes
        warnings = [] if has_mode else ["無眾數（每個值都只出現一次）"]
        sx = _add_sample_stats(values, warnings, n, mean, s2, s3, s4)
        _add_cv(values, warnings, mean, sx)
    except (OverflowError, ValueError, ZeroDivisionError):
        return err("計算結果超出範圍（溢位）", "X")
    return ok(values, warnings)


def _add_sample_stats(values, warnings, n, mean, s2, s3, s4):
    """加入樣本變異數、Sx、偏態、峰態；回傳 sx（算不出來為 None）。"""
    if n < 2:
        warnings.append("n<2 無法計算樣本變異數與標準差 Sx")
        warnings.append("n<3 無法計算偏態")
        warnings.append("n<4 無法計算峰態")
        return None
    var = s2 / (n - 1)
    sx = math.sqrt(var)
    values["var"] = var
    values["sx"] = sx
    flat = sx == 0 or s2 == 0
    if n < 3:
        warnings.append("n<3 無法計算偏態")
    elif flat:
        warnings.append("Sx 為 0（所有值相同），無法計算偏態")
    else:
        # Σ((x-m)/s)^3 = s3 / sx^3
        values["skew"] = n / ((n - 1) * (n - 2)) * s3 / (sx ** 3)
    if n < 4:
        warnings.append("n<4 無法計算峰態")
    elif flat:
        warnings.append("Sx 為 0（所有值相同），無法計算峰態")
    else:
        c = n * (n + 1) / ((n - 1) * (n - 2) * (n - 3))
        values["kurt"] = (c * s4 / (sx ** 4)
                          - 3 * (n - 1) ** 2 / ((n - 2) * (n - 3)))
    return sx


def _add_cv(values, warnings, mean, sx):
    """加入變異係數 CV＝Sx／|平均|；平均為 0 或 Sx 不存在時省略。"""
    if sx is None:
        warnings.append("無 Sx，無法計算 CV")
    elif mean == 0:
        warnings.append("平均為 0，無法計算 CV")
    else:
        values["cv"] = sx / abs(mean)
