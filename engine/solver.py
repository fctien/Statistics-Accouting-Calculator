"""共用求根器：牛頓法（Newton）失敗時退回二分法（bisection）。"""

_INF = float("inf")


def _bad(v):
    """非有限數（nan 或 inf）。"""
    return v != v or v == _INF or v == -_INF


def _newton(f, lo, hi, x, tol, max_iter):
    """牛頓法；數值微分。發散、出界或微分為 0 回傳 None。"""
    for _ in range(max_iter):
        fx = f(x)
        if _bad(fx):
            return None
        if fx == 0:
            return x
        h = 1e-7 * max(1.0, abs(x))
        d = (f(x + h) - f(x - h)) / (2 * h)
        if _bad(d) or d == 0:
            return None
        nx = x - fx / d
        if _bad(nx) or nx < lo or nx > hi:
            return None
        if abs(nx - x) <= tol * max(1.0, abs(nx)):
            return nx
        x = nx
    return None


def _bisect(f, lo, hi, tol, max_iter):
    """二分法；僅在兩端異號時進行。"""
    flo, fhi = f(lo), f(hi)
    if _bad(flo) or _bad(fhi):
        return None
    if flo == 0:
        return lo
    if fhi == 0:
        return hi
    if (flo < 0) == (fhi < 0):
        return None
    for _ in range(max_iter):
        mid = (lo + hi) / 2
        fm = f(mid)
        if _bad(fm):
            return None
        if fm == 0 or (hi - lo) / 2 <= tol * max(1.0, abs(mid)):
            return mid
        if (fm < 0) == (flo < 0):
            lo, flo = mid, fm
        else:
            hi = mid
    return None


def find_root(f, lo, hi, guess, tol=1e-10, max_iter=200):
    """在 [lo, hi] 內求 f(x)=0 的根；找不到回 None。"""
    x = _newton(f, lo, hi, guess, tol, max_iter)
    if x is not None:
        return x
    return _bisect(f, lo, hi, tol, max_iter)


# 百分數結果的零點雜訊門檻：疊代求根在真實解為 0 時常停在 ±1e-15 附近，
# 顯示成 -1.266E-15 或 0.000000001 會像是一個真的（錯的）數字；
# 1e-9 個百分點遠小於任何顯示位數與求根容許誤差，收成 0 不影響正確性。
SNAP_PCT = 1e-9


def snap_zero_pct(x):
    """疊代求解結果（百分數）|x| < SNAP_PCT 時回傳 0.0（不回傳 -0.0），否則原值。"""
    if -SNAP_PCT < x < SNAP_PCT:
        return 0.0
    return x
