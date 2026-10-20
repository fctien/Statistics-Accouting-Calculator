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


# 金額絕對值上限（元，不含）：to_cents 用 '%.15g' 取 15 位有效數字，
# 13 位整數 + 2 位小數才保得住「分」；1e13 元（10 兆）遠超任何會計用途
MAX_AMOUNT = 1e13


def to_cents(x):
    """浮點金額轉分（half away from zero），避開 2.675*100 的二進位誤差。

    先以 '%.15g' 取 15 位有效數字，還原使用者輸入的十進位值（2.675 → "2.675"），
    再以整數運算進位到分。不用 '%.6f'：其在 ~1e9 元以上會露出二進位誤差，
    且 MicroPython 的 %f 超過約 16 位有效數字即不精確。
    |x| 須 < MAX_AMOUNT 且為有限數，否則拋 ValueError（呼叫端應先驗證並回 err）。
    """
    if not (-MAX_AMOUNT < x < MAX_AMOUNT):  # NaN 比較皆為 False，一併擋下
        raise ValueError("金額超出範圍")
    s = "%.15g" % abs(x)
    exp = 0
    if "e" in s:                 # |x| < 1e13，只會出現負指數（如 1e-05）
        s, e = s.split("e")
        exp = int(e)
    if "." in s:
        ip, fp = s.split(".")
    else:
        ip, fp = s, ""
    digits = int(ip + fp)        # 值 = digits * 10**(exp - len(fp))
    k = 2 + exp - len(fp)        # 換成分需乘 10**k
    if k >= 0:
        cents = digits * 10 ** k
    else:
        cents = round_div(digits, 10 ** (-k))
    return -cents if x < 0 else cents


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
