"""折舊 DEPR 工作表（depreciation worksheet）：SL、SYD、DB、DBX。

schedule() 回傳整張折舊表，year() 回傳單一年度。
僅用 CPython 與 MicroPython 都支援的功能。
"""
from engine.result import err, ok, is_finite

METHODS = ("SL", "SYD", "DB", "DBX")
MAX_LIF = 10000
_M01_MSG = "SYD 部分年度需 TI 手冊範例驗證，目前僅支援 M01=1"


def _num(x):
    """是否為有限實數（bool 不算）。"""
    return (isinstance(x, (int, float)) and not isinstance(x, bool)
            and is_finite(x))


def _validate(method, cst, sal, lif, m01, db_pct):
    """驗證輸入；回傳 (錯誤結果或 None, 整數 LIF)。"""
    if method not in METHODS:
        return err("折舊方法必須是 SL、SYD、DB 或 DBX", "method"), 0
    for name, val in (("CST", cst), ("SAL", sal), ("LIF", lif),
                      ("M01", m01), ("DB", db_pct)):
        if not _num(val):
            return err(name + " 必須是有限數字", name), 0
    if cst < 0:
        return err("CST 不可為負數", "CST"), 0
    if sal < 0:
        return err("SAL 不可為負數", "SAL"), 0
    if sal > cst:
        return err("SAL 不可大於 CST", "SAL"), 0
    if lif != int(lif) or lif < 1 or lif > MAX_LIF:
        return err("LIF 必須是 1 到 %d 的整數" % MAX_LIF, "LIF"), 0
    if not 1 <= m01 < 13:
        return err("M01 必須 ≥ 1 且 < 13", "M01"), 0
    if db_pct <= 0:
        return err("DB 必須大於 0", "DB"), 0
    if method in ("SYD", "DBX") and m01 != 1:
        return err(_M01_MSG, "M01"), 0
    return None, int(lif)


def _deps(method, cst, sal, lif, m01, db_pct):
    """依方法回傳各年折舊額 list（尚未累計 RBV）。"""
    span = cst - sal
    frac = (13 - m01) / 12.0
    deps = []
    if method == "SL":
        d = span / lif
        if m01 == 1:
            return [d] * lif
        deps = [d * frac] + [d] * (lif - 1) + [d * (1 - frac)]
    elif method == "SYD":
        total = lif * (lif + 1) / 2.0
        deps = [span * (lif - k) / total for k in range(lif)]
    else:
        rate = db_pct / 100.0 / lif
        rbv = cst
        n = lif if m01 == 1 else lif + 1
        for k in range(n):
            avail = rbv - sal
            dep = rbv * rate
            if k == 0 and m01 != 1:
                dep *= frac
            if method == "DBX":
                # 改用直線法：剩餘可折舊額 ÷ 剩餘年數，取較大者（VDB）
                dep = max(dep, avail / (lif - k))
            dep = min(dep, avail)
            deps.append(dep)
            rbv -= dep
    return deps


def _build(method, cst, sal, lif, m01, db_pct):
    """建立表列 [[年, DEP, RBV, RDV], …]。"""
    rows = []
    rbv = float(cst)
    for k, dep in enumerate(_deps(method, cst, sal, lif, m01, db_pct)):
        rbv = max(rbv - dep, float(sal))
        rows.append([k + 1, dep, rbv, rbv - sal])
    return rows


def schedule(method, cst, sal, lif, m01=1, db_pct=200):
    """整張折舊表；ok({"rows": [[年, DEP, RBV, RDV], …]})。"""
    e, n = _validate(method, cst, sal, lif, m01, db_pct)
    if e:
        return e
    try:
        rows = _build(method, cst, sal, n, m01, db_pct)
    except (ArithmeticError, ValueError):
        return err("計算結果超出範圍（溢位）")
    return ok({"rows": rows})


def year(method, cst, sal, lif, m01=1, db_pct=200, yr=None):
    """單一年度；ok({"DEP", "RBV", "RDV"})。參數順序同 schedule，YR 最後。"""
    e, n = _validate(method, cst, sal, lif, m01, db_pct)
    if e:
        return e
    if not _num(yr) or yr != int(yr):
        return err("YR 必須是整數", "YR")
    last = n if m01 == 1 else n + 1
    if yr < 1 or yr > last:
        return err("YR 超出範圍（1 到 %d）" % last, "YR")
    try:
        row = _build(method, cst, sal, n, m01, db_pct)[int(yr) - 1]
    except (ArithmeticError, ValueError):
        return err("計算結果超出範圍（溢位）")
    return ok({"DEP": row[1], "RBV": row[2], "RDV": row[3]})
