"""金額運算：以「分」為單位的整數（integer cents），避免浮點誤差。

僅用純 Python 整數運算，CPython 與 MicroPython 皆可執行。
"""


def round_div(num, den):
    """整數除法並四捨五入，0.5 時遠離零（half away from zero）。"""
    if den < 0:
        num, den = -num, -den
    if num >= 0:
        return (2 * num + den) // (2 * den)
    return -((-2 * num + den) // (2 * den))


def to_cents(x):
    """浮點金額轉分；先格式化成 6 位小數字串再解析，避開 2.675*100 的誤差。"""
    s = "%.6f" % x
    neg = s.startswith("-")
    if neg:
        s = s[1:]
    whole, frac = s.split(".")
    micro = int(whole) * 1000000 + int(frac)
    cents = round_div(micro, 10000)
    return -cents if neg else cents


def _rate_bp(rate_pct):
    """稅率（百分比）轉萬分比整數（basis points of percent）。"""
    return round_div(int(rate_pct * 10000), 100)


def tax_exclusive(net_cents, rate_pct):
    """未稅價（net）求稅額與含稅價（gross）。"""
    bp = _rate_bp(rate_pct)
    tax = round_div(net_cents * bp, 10000)
    return {"net": net_cents, "tax": tax, "gross": net_cents + tax}


def tax_inclusive(gross_cents, rate_pct):
    """含稅價求未稅價與稅額；稅額 = 含稅 - 未稅，確保兩者相加恆等於含稅。"""
    bp = _rate_bp(rate_pct)
    net = round_div(gross_cents * 10000, 10000 + bp)
    return {"net": net, "tax": gross_cents - net, "gross": gross_cents}
