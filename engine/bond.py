"""債券 BOND：價格（price）、殖利率（yield）、應計利息（accrued interest, AI）。

公式對照 Excel PRICE／YIELD／COUPDAYBS／COUPDAYS：
- "ACT" 對應 Excel basis 1（actual/actual）：A、E 皆為實際天數
- "360" 對應 Excel basis 0（US 30/360）：A 用 days_360，E = 360/freq
- DSC = E − A（Excel basis 0 亦如此，不是 DAYS360(SDT, NCD)）
僅用 CPython 與 MicroPython 都支援的功能。
"""
from engine.dates import is_valid_date, to_ordinal, days_act, days_360, \
    _dim
from engine.result import ok, err
from engine.solver import find_root, snap_zero_pct

# 殖利率搜尋區間（小數）：(-0.99, 10]，下界取 -0.99 + 1e-9 以表示開區間
_Y_LO = -0.99 + 1e-9
_Y_HI = 10.0


def _shift_months(rdt, months, eom):
    """自到期日往回 months 個月的付息日；月底規則（end-of-month）與日數截斷。"""
    y, m, d = rdt
    t = y * 12 + (m - 1) - months
    ny, nm = t // 12, t % 12 + 1
    last = _dim(ny, nm)
    return (ny, nm, last if eom else min(d, last))


def _coupon_dates(sdt, rdt, freq):
    """回傳 (PCD, NCD, N)：結算日前一付息日、下一付息日、剩餘付息次數。"""
    step = 12 // freq
    eom = rdt[2] == _dim(rdt[0], rdt[1])
    s = to_ordinal(*sdt)
    k = 0
    ncd = tuple(rdt)
    while True:
        pcd = _shift_months(rdt, (k + 1) * step, eom)
        if to_ordinal(*pcd) <= s:
            return pcd, ncd, k + 1
        ncd = pcd
        k += 1


def _parse_date(v):
    """[y, m, d] → tuple；不合法回 None。"""
    try:
        if len(v) != 3:
            return None
        y, m, d = int(v[0]), int(v[1]), int(v[2])
        if (y, m, d) != (v[0], v[1], v[2]):
            return None
    except (TypeError, ValueError):
        return None
    return (y, m, d) if is_valid_date(y, m, d) else None


def _num(v):
    """轉為有限浮點數；不合法回 None。"""
    if v is None or isinstance(v, bool):
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if x != x or x in (float("inf"), float("-inf")):
        return None
    return x


def _setup(inputs):
    """驗證共同輸入，回傳 (參數 dict, None) 或 (None, err)。"""
    sdt = _parse_date(inputs.get("SDT"))
    if sdt is None:
        return None, err("結算日（SDT）日期不合法", "SDT")
    rdt = _parse_date(inputs.get("RDT"))
    if rdt is None:
        return None, err("贖回日（RDT）日期不合法", "RDT")
    if to_ordinal(*sdt) >= to_ordinal(*rdt):
        return None, err("結算日（SDT）必須早於贖回日（RDT）", "SDT")
    freq = inputs.get("freq")
    if isinstance(freq, bool) or freq not in (1, 2):
        return None, err("付息頻率（freq）必須為 1 或 2", "freq")
    freq = int(freq)
    basis = inputs.get("basis")
    if basis not in ("ACT", "360"):
        return None, err("天數基準（basis）必須為 ACT 或 360", "basis")
    cpn = _num(inputs.get("CPN"))
    if cpn is None or cpn < 0:
        return None, err("票面利率（CPN）必須 ≥ 0", "CPN")
    rv = _num(inputs.get("RV"))
    if rv is None or rv <= 0:
        return None, err("贖回價（RV）必須 > 0", "RV")
    pcd, ncd, n = _coupon_dates(sdt, rdt, freq)
    if basis == "ACT":
        a = days_act(pcd, sdt)
        e = days_act(pcd, ncd)
    else:
        a = days_360(pcd, sdt)
        e = 360 / freq
    c = cpn / freq  # 每期票息（每 100 面額；CPN 為年利率 %）
    return {"A": a, "E": e, "DSC": e - a, "N": n, "f": freq,
            "c": c, "RV": rv}, None


def _ai(p):
    """應計利息 AI = (A/E)·C/f（每 100 面額）。"""
    return p["A"] / p["E"] * p["c"]


def _price_at(p, y):
    """給定殖利率 y（小數）的淨價（clean price）。"""
    f, n, e, dsc, c, rv = p["f"], p["N"], p["E"], p["DSC"], p["c"], p["RV"]
    if n == 1:
        return (rv + c) / (1 + dsc / e * y / f) - _ai(p)
    base = 1 + y / f
    frac = dsc / e
    total = rv / base ** (n - 1 + frac)
    for k in range(1, n + 1):
        total += c / base ** (k - 1 + frac)
    return total - _ai(p)


def price(inputs):
    """由 YLD 計算 PRI 與 AI。"""
    p, e = _setup(inputs)
    if e:
        return e
    yld = _num(inputs.get("YLD"))
    if yld is None:
        return err("請輸入殖利率（YLD）", "YLD")
    y = yld / 100
    if y <= -p["f"]:
        return err("殖利率（YLD）過低，無法計算", "YLD")
    try:
        pri = _price_at(p, y)
    except (OverflowError, ZeroDivisionError):
        return err("計算溢位，無法求得價格", "PRI")
    return ok({"PRI": pri, "AI": _ai(p)})


def yield_(inputs):
    """由 PRI 求解 YLD（百分比）與 AI；搜尋區間 (-99%, 1000%]。"""
    p, e = _setup(inputs)
    if e:
        return e
    pri = _num(inputs.get("PRI"))
    if pri is None:
        return err("請輸入價格（PRI）", "PRI")
    if pri <= 0:
        return err("價格（PRI）必須 > 0", "PRI")

    def f(y):
        try:
            return _price_at(p, y) - pri
        except (OverflowError, ZeroDivisionError):
            return float("nan")

    guess = p["c"] * p["f"] / 100 if p["c"] > 0 else 0.05
    y = find_root(f, _Y_LO, _Y_HI, guess)
    if y is None:
        return err("殖利率無法收斂（不在 -99%～1000% 範圍內）", "YLD")
    return ok({"YLD": snap_zero_pct(y * 100), "AI": _ai(p)})
