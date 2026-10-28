"""機率分配（probability distributions），供「統計」頁的分配計算使用。

分配：常態 Normal(μ, σ)、t(df)、卡方 χ²(df)、二項 Binomial(n, p)、Poisson(λ)。
功能：pdf／pmf（機率密度／機率質量）、cdf（累積機率）、inv（給機率反查 x）。
輸出鍵：
    value  pdf／pmf 值、左尾累積機率 P(X≤x)，或反查的 x（P(X≤x)=PROB）
    right  右尾：cdf 時為 P(X>x)；inv 時為滿足 P(X>x)=PROB 的 x
    two    雙尾（只有常態與 t）：cdf 時為 P(|X−μ|≥|x−μ|)；
           inv 時為上側臨界值 x（P(|X−μ|≥x−μ)=PROB，下側臨界值為 2μ−x）

數值方法（numerical methods）：
    - 常態 cdf 用 math.erfc（左尾極小時仍有完整相對精度），右尾用 erfc(z/√2) 直接算
    - 正規化不完全 Beta I_x(a,b)（t、二項）與不完全 Gamma P(a,x)／Q(a,x)（卡方、Poisson）
      自寫：Numerical Recipes 式的連分數（continued fraction，modified Lentz）＋ 級數；
      依對稱關係選收斂快的一側「直接」算出較小的那一尾，另一尾才用 1−小尾，
      避免 1−0.9999999999 的相消誤差（cancellation）
    - 疊代上限 MAX_ITER、收斂容差 EPS 為模組常數；未收斂擲 NotConverged，
      公開函式轉成錯誤回傳，絕不回部分和
    - 二項／Poisson：pmf 用 lgamma 的對數形式避免溢位；cdf 不逐項累加，
      改用與不完全 Beta／Gamma 的恆等關係（大 n、大 λ 也是常數成本、兩尾皆精準）：
          P(Bin ≤ k) = I_{1−p}(n−k, k+1)，P(Bin > k) = I_p(k+1, n−k)
          P(Poi ≤ k) = Q(k+1, λ)，        P(Poi > k) = P(k+1, λ)
    - inv：以 solver.find_root 求根；先用對稱關係把問題化成「機率 ≤ 0.5 的那一尾」
      （p>0.5 時 1−p 在浮點數中是精確的），卡方在 ln x 上求根以保留極小臨界值的相對精度
參數上限：df、n、λ ≤ MAX_PARAM（更大時 lgamma 相減的捨入誤差會超過 1e-9 相對誤差）。
僅用 math 與 engine 內部匯入；無 I/O。
"""
import math

from engine.result import err, is_finite, ok
from engine.solver import find_root

MAX_ITER = 10000      # 連分數／級數最大疊代次數
EPS = 1e-15           # 連分數／級數收斂的相對容差
FPMIN = 1e-300        # Lentz 法避免除以 0 的極小值
ROOT_TOL = 1e-13      # 反查求根的相對容差（比全域 1e-10 更嚴，結果接近機器精度）
MAX_PARAM = 1e5       # df、n、λ 的上限
_SQRT2 = math.sqrt(2.0)
_LN_SQRT_2PI = 0.5 * math.log(2.0 * math.pi)
_MAX_X = 1e300


class NotConverged(Exception):
    """連分數或級數在 MAX_ITER 次內未收斂。"""


class _DistError(Exception):
    """參數或計算錯誤（內部使用），帶中文訊息與欄位名。"""

    def __init__(self, message, field=None):
        super().__init__(message)  # MicroPython 相容
        self.message = message
        self.field = field


# ---------------------------------------------------------------- 基本工具

def _log1p(u):
    """log(1+u)，u 很小時仍精準（MicroPython 沒有 math.log1p）。"""
    w = 1.0 + u
    if w == 1.0:
        return u
    return math.log(w) * u / (w - 1.0)


# ---------------------------------------------------------------- 不完全 Beta

def _betacf(a, b, x):
    """I_x(a,b) 的連分數（NR betacf，modified Lentz）。"""
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < FPMIN:
        d = FPMIN
    d = 1.0 / d
    h = d
    for m in range(1, MAX_ITER + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < EPS:
            return h
    raise NotConverged("betacf")


def betainc(a, b, x, y=None):
    """正規化不完全 Beta：回傳 (I_x(a,b), 1−I_x(a,b))。

    y＝1−x 可另外給（呼叫端能精確算出時），避免 1−x 的捨入；
    x 小於分配中心時直接算 I，否則用對稱關係 I_x(a,b)=1−I_y(b,a) 直接算 1−I。
    """
    if y is None:
        y = 1.0 - x
    if x <= 0.0:
        return 0.0, 1.0
    if y <= 0.0:
        return 1.0, 0.0
    lx = math.log(x) if x < 0.5 else _log1p(-y)
    ly = math.log(y) if y < 0.5 else _log1p(-x)
    bt = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                  + a * lx + b * ly)
    if x < (a + 1.0) / (a + b + 2.0):
        i = bt * _betacf(a, b, x) / a
        return i, 1.0 - i
    j = bt * _betacf(b, a, y) / b
    return 1.0 - j, j


# ---------------------------------------------------------------- 不完全 Gamma

def gammainc(a, x):
    """正規化不完全 Gamma：回傳 (P(a,x), Q(a,x))。

    x < a+1 用級數（series）直接算 P；否則用連分數直接算 Q。
    """
    if x <= 0.0:
        return 0.0, 1.0
    lpre = a * math.log(x) - x - math.lgamma(a)
    if x < a + 1.0:
        ap = a
        s = delta = 1.0 / a
        for _ in range(MAX_ITER):
            ap += 1.0
            delta *= x / ap
            s += delta
            if abs(delta) < abs(s) * EPS:
                p = s * math.exp(lpre)
                return p, 1.0 - p
        raise NotConverged("gser")
    b = x + 1.0 - a
    c = 1.0 / FPMIN
    d = 1.0 / b
    h = d
    for i in range(1, MAX_ITER + 1):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < FPMIN:
            d = FPMIN
        c = b + an / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < EPS:
            q = math.exp(lpre) * h
            return 1.0 - q, q
    raise NotConverged("gcf")


# ---------------------------------------------------------------- 參數檢查

def _is_num(v):
    return (not isinstance(v, bool) and isinstance(v, (int, float))
            and is_finite(v) and abs(v) <= _MAX_X)


def _need(v, field):
    """必填有限數字。"""
    if v is None:
        raise _DistError("請輸入 %s" % field, field)
    if not _is_num(v):
        raise _DistError("%s 必須是有限數字" % field, field)
    return float(v)


def _need_int(v, field, lo, hi=None):
    """必填整數，lo ≤ v（≤ hi）。"""
    v = _need(v, field)
    if v != int(v):
        raise _DistError("%s 必須是整數" % field, field)
    if v < lo or (hi is not None and v > hi):
        if hi is None:
            raise _DistError("%s 必須 ≥ %d" % (field, lo), field)
        raise _DistError("%s 必須介於 %d 與 %d 之間" % (field, lo, hi), field)
    return int(v)


def _need_df(v, field="DF"):
    v = _need(v, field)
    if v <= 0:
        raise _DistError("%s 必須 > 0" % field, field)
    if v > MAX_PARAM:
        raise _DistError("%s 不可超過 %d" % (field, int(MAX_PARAM)), field)
    return v


def _need_prob(v):
    """反查用機率：0 < PROB < 1。"""
    v = _need(v, "PROB")
    if not 0.0 < v < 1.0:
        raise _DistError("PROB 必須介於 0 與 1 之間（不含 0、1）", "PROB")
    return v


def _check_func(func, allowed):
    if func not in allowed:
        raise _DistError("FUNC 必須是 %s" % "、".join(allowed), "FUNC")


def _run(fn):
    """執行計算並把內部例外轉成 err。"""
    try:
        return ok(fn())
    except _DistError as e:
        return err(e.message, e.field)
    except NotConverged:
        return err("不完全 Beta／Gamma 函數未收斂（參數過於極端）", None)
    except (OverflowError, ValueError, ZeroDivisionError):
        return err("計算結果超出範圍（溢位）", None)


# ---------------------------------------------------------------- 反查共用

def _root(f, lo, hi, guess):
    """find_root 包裝；找不到根擲錯誤。"""
    guess = min(max(guess, lo), hi)
    x = find_root(f, lo, hi, guess, tol=ROOT_TOL)
    if x is None:
        raise _DistError("反查找不到解", "PROB")
    return x


def _sym_quantiles(upper, prob):
    """對稱分配（標準化後）的反查：upper(q) 回傳 z ≥ 0 使右尾＝q（q ≤ 0.5）。

    回傳 (左尾 z, 右尾 z, 雙尾上側 z)。p > 0.5 時 1−p 為精確值。
    """
    def left(p):
        if p < 0.5:
            return -upper(p)
        if p == 0.5:
            return 0.0
        return upper(1.0 - p)
    return left(prob), -left(prob), upper(prob / 2.0)


# ---------------------------------------------------------------- 常態

def _norm_tails(z):
    """(左尾, 右尾, 雙尾)；各尾都以 erfc 直接算。"""
    left = 0.5 * math.erfc(-z / _SQRT2)
    right = 0.5 * math.erfc(z / _SQRT2)
    return left, right, math.erfc(abs(z) / _SQRT2)


def _z_guess(q):
    """標準常態右尾 q（≤ 0.5）的近似臨界值（Abramowitz & Stegun 26.2.23）。"""
    t = math.sqrt(-2.0 * math.log(q))
    return t - ((2.515517 + 0.802853 * t + 0.010328 * t * t)
                / (1.0 + 1.432788 * t + 0.189269 * t * t
                   + 0.001308 * t * t * t))


def _z_upper(q):
    """z ≥ 0 使 P(Z > z) = q（0 < q ≤ 0.5）。"""
    if q == 0.5:
        return 0.0

    def f(z):
        return (0.5 * math.erfc(z / _SQRT2) - q) / q
    return _root(f, 0.0, 40.0, _z_guess(q))


def normal(func, mu, sigma, x=None, prob=None):
    """常態分配 Normal(μ, σ)。"""
    def calc():
        _check_func(func, ("pdf", "cdf", "inv"))
        m = _need(mu, "MU")
        s = _need(sigma, "SIGMA")
        if s <= 0:
            raise _DistError("SIGMA 必須 > 0", "SIGMA")
        if func == "inv":
            p = _need_prob(prob)
            zl, zr, z2 = _sym_quantiles(_z_upper, p)
            return {"value": m + s * zl, "right": m + s * zr,
                    "two": m + s * z2}
        z = (_need(x, "X") - m) / s
        z = min(max(z, -1e10), 1e10)   # 極端值：機率已是 0／1，避免 z² 溢位
        if func == "pdf":
            return {"value": math.exp(-0.5 * z * z - _LN_SQRT_2PI) / s}
        left, right, two = _norm_tails(z)
        return {"value": left, "right": right, "two": two}
    return _run(calc)


# ---------------------------------------------------------------- t 分配

def _t_tails(t, v):
    """(左尾, 右尾, 雙尾)。雙尾 = I_x(v/2, 1/2)，x = v/(v+t²)、1−x = t²/(v+t²) 分別直接算。"""
    if t == 0:
        return 0.5, 0.5, 1.0
    a = 0.5 * v
    lx = math.log(v) - 2.0 * math.log(abs(t))   # ln x 的近似（|t| 極大時）
    if lx < -690.0:
        # x < 1e-300 會下溢（underflow）：用 I_x(a,b) 的首項 x^a / (a·B(a,b))，
        # 其後各項相對大小為 O(x)，可忽略
        two = math.exp(a * lx - math.log(a) - math.lgamma(a)
                       - math.lgamma(0.5) + math.lgamma(a + 0.5))
    else:
        t2 = t * t
        two, _ = betainc(a, 0.5, v / (v + t2), t2 / (v + t2))
    tail = 0.5 * two            # |t| 那一側的單尾（直接算，不經 1−cdf）
    if t > 0:
        return 1.0 - tail, tail, two
    return tail, 1.0 - tail, two


def _t_upper_fn(v):
    """回傳 upper(q)：t ≥ 0 使 P(T > t) = q（0 < q ≤ 0.5）。"""
    def upper(q):
        if q == 0.5:
            return 0.0

        def f(t):
            return (_t_tails(t, v)[1] - q) / q
        hi = 1.0
        while _t_tails(hi, v)[1] >= q:
            hi *= 2.0
            if hi > _MAX_X:
                raise _DistError("臨界值超出可計算範圍", "PROB")
        z = _z_upper(q)
        # Cornish-Fisher 展開當初值（df 小時不準，由 find_root 的二分法後備）
        g = z + (z ** 3 + z) / (4.0 * v) + (5 * z ** 5 + 16 * z ** 3
                                            + 3 * z) / (96.0 * v * v)
        return _root(f, 0.0, hi, g)
    return upper


def _t_pdf(t, v):
    q = abs(t) / math.sqrt(v)
    lt = _log1p(q * q) if q < 1e150 else 2.0 * math.log(q)
    c = (math.lgamma(0.5 * (v + 1.0)) - math.lgamma(0.5 * v)
         - 0.5 * math.log(v * math.pi))
    return math.exp(c - 0.5 * (v + 1.0) * lt)


def t_dist(func, df, x=None, prob=None):
    """Student t 分配（df 可為非整數 > 0）。"""
    def calc():
        _check_func(func, ("pdf", "cdf", "inv"))
        v = _need_df(df)
        if func == "inv":
            p = _need_prob(prob)
            zl, zr, z2 = _sym_quantiles(_t_upper_fn(v), p)
            return {"value": zl, "right": zr, "two": z2}
        t = _need(x, "X")
        if func == "pdf":
            return {"value": _t_pdf(t, v)}
        left, right, two = _t_tails(t, v)
        return {"value": left, "right": right, "two": two}
    return _run(calc)


# ---------------------------------------------------------------- 卡方

def _chi2_solve(a, target, use_right):
    """在 u = ln x 上求根：P(a, x/2) = target（或 Q = target，use_right）；target ≤ 0.5。"""
    def g(u):
        p, q = gammainc(a, 0.5 * math.exp(u))
        return ((q if use_right else p) - target) / target

    # g 的符號：左尾版遞增、右尾版遞減；先找出兩端異號的區間
    sign = -1.0 if use_right else 1.0
    start = math.log(max(2.0 * a, 1.0))
    hi = start
    while sign * g(hi) <= 0:
        hi += 2.0
        if hi > 690.0:
            raise _DistError("臨界值超出可計算範圍", "PROB")
    lo = start
    while sign * g(lo) >= 0:
        lo -= 2.0
        if lo < -690.0:
            raise _DistError("臨界值超出可計算範圍", "PROB")
    # Wilson-Hilferty 近似當初值
    v = 2.0 * a
    z = _z_upper(target)
    if not use_right:
        z = -z
    w = 1.0 - 2.0 / (9.0 * v) + z * math.sqrt(2.0 / (9.0 * v))
    guess = 3.0 * math.log(w) + math.log(v) if w > 0 else 0.5 * (lo + hi)
    return math.exp(_root(g, lo, hi, guess))


def chi2(func, df, x=None, prob=None):
    """卡方分配 χ²(df)（df 可為非整數 > 0）。"""
    def calc():
        _check_func(func, ("pdf", "cdf", "inv"))
        v = _need_df(df)
        a = 0.5 * v
        if func == "inv":
            p = _need_prob(prob)
            left = (_chi2_solve(a, p, False) if p <= 0.5
                    else _chi2_solve(a, 1.0 - p, True))
            right = (_chi2_solve(a, p, True) if p <= 0.5
                     else _chi2_solve(a, 1.0 - p, False))
            return {"value": left, "right": right}
        xv = _need(x, "X")
        if xv < 0:
            raise _DistError("X 必須 ≥ 0", "X")
        if func == "pdf":
            if xv == 0:
                if v < 2:
                    raise _DistError("df < 2 時 X=0 的密度為無限大", "X")
                return {"value": 0.5 if v == 2 else 0.0}
            return {"value": math.exp((a - 1.0) * math.log(0.5 * xv)
                                      - 0.5 * xv - math.lgamma(a)) * 0.5}
        p, q = gammainc(a, 0.5 * xv)
        return {"value": p, "right": q}
    return _run(calc)


# ---------------------------------------------------------------- 二項

def binom(func, n, p, k):
    """二項分配 Binomial(n, p)：pmf P(X=k)、cdf P(X≤k)（right 為 P(X>k)）。"""
    def calc():
        _check_func(func, ("pmf", "cdf"))
        nn = _need_int(n, "N", 0, int(MAX_PARAM))
        pp = _need(p, "P")
        if not 0.0 <= pp <= 1.0:
            raise _DistError("P 必須介於 0 與 1 之間", "P")
        kk = _need_int(k, "K", 0, nn)
        if func == "pmf":
            if pp == 0.0:
                return {"value": 1.0 if kk == 0 else 0.0}
            if pp == 1.0:
                return {"value": 1.0 if kk == nn else 0.0}
            return {"value": math.exp(
                math.lgamma(nn + 1.0) - math.lgamma(kk + 1.0)
                - math.lgamma(nn - kk + 1.0)
                + kk * math.log(pp) + (nn - kk) * _log1p(-pp))}
        if kk == nn or pp == 0.0:
            return {"value": 1.0, "right": 0.0}
        if pp == 1.0:
            return {"value": 0.0, "right": 1.0}
        # P(X ≤ k) = I_{1−p}(n−k, k+1)；y = p 精確傳入
        cdf, right = betainc(float(nn - kk), kk + 1.0, 1.0 - pp, pp)
        return {"value": cdf, "right": right}
    return _run(calc)


# ---------------------------------------------------------------- Poisson

def poisson(func, lam, k):
    """Poisson(λ)：pmf P(X=k)、cdf P(X≤k)（right 為 P(X>k)）。"""
    def calc():
        _check_func(func, ("pmf", "cdf"))
        lm = _need(lam, "LAMBDA")
        if lm <= 0:
            raise _DistError("LAMBDA 必須 > 0", "LAMBDA")
        if lm > MAX_PARAM:
            raise _DistError("LAMBDA 不可超過 %d" % int(MAX_PARAM), "LAMBDA")
        kk = _need_int(k, "K", 0)
        if func == "pmf":
            return {"value": math.exp(kk * math.log(lm) - lm
                                      - math.lgamma(kk + 1.0))}
        # P(X ≤ k) = Q(k+1, λ)；P(X > k) = P(k+1, λ)
        p, q = gammainc(kk + 1.0, lm)
        return {"value": q, "right": p}
    return _run(calc)
