"""現金流（Cash Flow, CF）工作表：NPV、IRR、NFV、MIRR、PB、DPB。

所有公開函式皆接受單一 inputs 字典：
{"CF0": float, "flows": [[金額, 次數], ...], "I": 百分比, "RI": 百分比或 None}
並回傳 result.ok / result.err。百分比輸入與輸出皆為「百分數」（10 代表 10%）。
"""
from engine.result import err, is_finite, ok
from engine.solver import find_root

_MAX_COUNT = 9999
_MULTI_SIGN_WARN = "現金流正負號變化多次，IRR 可能有多個解"


def _is_num(x):
    """有限數值（排除 bool、字串、inf、nan）。"""
    return (isinstance(x, (int, float)) and not isinstance(x, bool)
            and is_finite(float(x)))


def _expand(cf0, flows):
    """展開現金流群組（grouped flows）。

    回傳 (list, None) 或 (None, err 字典)；list[0] 為 CF0。
    次數須為 1～9999 的整數（接受整數值的 float，如 3.0）。
    """
    if not _is_num(cf0):
        return None, err("CF0 必須是有限數值", "CF")
    out = [float(cf0)]
    if not isinstance(flows, (list, tuple)):
        return None, err("現金流格式錯誤", "CF")
    for item in flows:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            return None, err("現金流格式錯誤", "CF")
        amount, count = item
        if not _is_num(amount):
            return None, err("現金流金額必須是有限數值", "CF")
        if not _is_num(count) or float(count) != int(count) \
                or not 1 <= int(count) <= _MAX_COUNT:
            return None, err("現金流次數須為 1～9999 的整數", "CF")
        out.extend([float(amount)] * int(count))
    return out, None


def expand(cf0, flows):
    """公開版展開：成功回傳 list[float]，失敗回傳 err 字典（請以 isinstance list 判斷）。"""
    flat, e = _expand(cf0, flows)
    return e if e else flat


def _prepare(inputs, need_rate=True):
    """取出並驗證輸入；回傳 (現金流 list, 利率小數, None) 或 (None, None, err)。"""
    flat, e = _expand(inputs.get("CF0"), inputs.get("flows"))
    if e:
        return None, None, e
    rate = None
    if need_rate:
        i = inputs.get("I")
        if not _is_num(i):
            return None, None, err("請輸入利率 I", "I")
        rate = i / 100.0
        if rate <= -1:
            return None, None, err("利率 I 必須大於 -100%", "I")
    return flat, rate, None


_INF = float("inf")
_OVERFLOW_MSG = "數值過大，無法計算"


def _pow(rate, t):
    """(1+rate)^t；溢位（Python 擲例外、MicroPython 回 inf）一律回 inf。"""
    try:
        return (1.0 + rate) ** t
    except (OverflowError, ZeroDivisionError):
        return _INF


def _signed_inf(c):
    """與 c 同號的無限大；c 為 0 時回 0.0。"""
    if c == 0:
        return 0.0
    return _INF if c > 0 else -_INF


def _disc(c, rate, t):
    """c / (1+rate)^t。分母溢位 → 0；分母下溢為 0 → 與 c 同號的 inf（c=0 則 0）。"""
    p = _pow(rate, t)
    if p == _INF:
        return 0.0
    if p == 0:
        return _signed_inf(c)
    try:
        return c / p
    except (OverflowError, ZeroDivisionError):
        return _signed_inf(c)


def _grow(c, rate, t):
    """c * (1+rate)^t。溢位 → 與 c 同號的 inf（c=0 則 0）。"""
    p = _pow(rate, t)
    if p == _INF:
        return _signed_inf(c)
    return c * p


def _npv_of(flat, rate):
    """CF0 + 各期折現（Excel：CF0 + NPV(rate, flows)）。"""
    total = 0.0
    for t, c in enumerate(flat):
        total += _disc(c, rate, t)
    return total


def npv(inputs):
    """淨現值 NPV。"""
    flat, rate, e = _prepare(inputs)
    if e:
        return e
    v = _npv_of(flat, rate)
    if not is_finite(v):
        return err(_OVERFLOW_MSG, "NPV")
    return ok({"NPV": v})


def nfv(inputs):
    """淨終值 NFV = NPV·(1+i)^總期數（不含 CF0 的期數）。"""
    flat, rate, e = _prepare(inputs)
    if e:
        return e
    v = _grow(_npv_of(flat, rate), rate, len(flat) - 1)
    if not is_finite(v):
        return err(_OVERFLOW_MSG, "NFV")
    return ok({"NFV": v})


def _sign_changes(flat):
    """計算非零現金流的正負號變化次數。"""
    signs = [1 if c > 0 else -1 for c in flat if c != 0]
    return sum(1 for a, b in zip(signs, signs[1:]) if a != b)


def _irr_root(flat):
    """求 IRR 的根（小數）。

    先在 (-0.9999, 10] 直接求根；若端點的 NPV 因溢位為 inf 使二分法無法進行
    （長期現金流常見），改掃描有限值的格點，找出異號區間再求根。
    """
    def f(r):
        return _npv_of(flat, r)

    root = find_root(f, -0.9999, 10.0, 0.1)
    if root is not None:
        return root
    grid = [-0.99, -0.95] + [-0.9 + k * 0.02 for k in range(550)]
    prev_x, prev_v = None, None
    for x in grid:
        v = f(x)
        if not is_finite(v):
            prev_x = None
            continue
        if v == 0:
            return x
        if prev_x is not None and (v < 0) != (prev_v < 0):
            return find_root(f, prev_x, x, (prev_x + x) / 2)
        prev_x, prev_v = x, v
    return None


def irr(inputs):
    """內部報酬率 IRR（百分數）。"""
    flat, _, e = _prepare(inputs, need_rate=False)
    if e:
        return e
    changes = _sign_changes(flat)
    if changes == 0:
        return err("IRR 無解：現金流沒有正負號變化", "CF")
    warnings = [_MULTI_SIGN_WARN] if changes >= 2 else []
    root = _irr_root(flat)
    if root is None:
        return err("IRR 無法收斂", "IRR")
    return ok({"IRR": root * 100.0}, warnings)


def mirr(inputs):
    """修正內部報酬率 MIRR：融資率＝I、再投資率＝RI（百分數）。"""
    flat, fin, e = _prepare(inputs)
    if e:
        return e
    ri = inputs.get("RI")
    if not _is_num(ri):
        return err("MIRR 需要再投資利率 RI", "RI")
    rein = ri / 100.0
    if rein <= -1:
        return err("再投資利率 RI 必須大於 -100%", "RI")
    n = len(flat)
    if not any(c > 0 for c in flat) or not any(c < 0 for c in flat) or n < 2:
        return err("MIRR 需要同時有正與負的現金流", "CF")
    fv_pos = sum(_grow(c, rein, n - 1 - t)
                 for t, c in enumerate(flat) if c > 0)
    pv_neg = sum(_disc(c, fin, t) for t, c in enumerate(flat) if c < 0)
    if not is_finite(fv_pos) or not is_finite(pv_neg) or pv_neg == 0:
        return err(_OVERFLOW_MSG, "MIRR")
    try:
        m = ((fv_pos / -pv_neg) ** (1.0 / (n - 1)) - 1.0) * 100.0
    except (OverflowError, ZeroDivisionError):
        return err(_OVERFLOW_MSG, "MIRR")
    return ok({"MIRR": m})


def _payback(flat, rate, field):
    """累計現金流首次 >= 0 的期間，期內線性內插；rate 為 None 表不折現。"""
    if flat[0] >= 0:
        return err("CF0 須為負值（初始投資）", "CF")
    cum = 0.0
    for t, c in enumerate(flat):
        v = c if rate is None else _disc(c, rate, t)
        if not is_finite(v):
            return err(_OVERFLOW_MSG, field)
        prev = cum
        cum += v
        if t > 0 and prev < 0 <= cum:
            return ok({field: (t - 1) + (-prev) / v})
    return err("未回本", field)


def payback(inputs):
    """回收期間 PB（期數，可含小數）。"""
    flat, _, e = _prepare(inputs, need_rate=False)
    if e:
        return e
    return _payback(flat, None, "PB")


def dpayback(inputs):
    """折現回收期間 DPB：各期以 I 折現。"""
    flat, rate, e = _prepare(inputs)
    if e:
        return e
    return _payback(flat, rate, "DPB")
