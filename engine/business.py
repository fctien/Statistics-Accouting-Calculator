"""商業與稅務：毛利／加成、損益兩平、百分比變動、稅額。

各函式皆為「留一格求解」：以關鍵字參數傳入變數並以 unknown 指定待求者，
unknown 本身的傳入值會被忽略。僅用 math，CPython 與 MicroPython 皆可執行。
"""
import math

from engine import money
from engine.result import ok, err, is_finite


def _is_num(x):
    """是否為有限數值（bool 不算數字）。"""
    return (isinstance(x, (int, float)) and not isinstance(x, bool)
            and is_finite(x))


def _check(values, names, unknown):
    """驗證 unknown 合法，且其餘必要變數皆為有限數；回傳 err 或 None。"""
    if unknown not in names:
        return err("未知數必須是 " + "、".join(names), "unknown")
    for k in names:
        if k != unknown and not _is_num(values.get(k)):
            return err("%s 必須是有限數值" % k, k)
    return None


def profit(cst=None, sel=None, mar=None, mu=None, unknown="MU"):
    """毛利率 MAR = (SEL-CST)/SEL*100；加成率 MU = (SEL-CST)/CST*100。

    unknown 為 MAR／MU 時由 CST、SEL 求；為 CST／SEL 時需另給 MAR 或 MU。
    """
    names = ("CST", "SEL", "MAR", "MU")
    if unknown not in names:
        return err("未知數必須是 " + "、".join(names), "unknown")
    v = {"CST": cst, "SEL": sel, "MAR": mar, "MU": mu}
    if unknown in ("MAR", "MU"):
        for k in ("CST", "SEL"):
            if not _is_num(v[k]):
                return err("%s 必須是有限數值" % k, k)
        c, s = float(cst), float(sel)
    else:
        known = "SEL" if unknown == "CST" else "CST"
        if not _is_num(v[known]):
            return err("%s 必須是有限數值" % known, known)
        for k in ("MAR", "MU"):
            if v[k] is not None and not _is_num(v[k]):
                return err("%s 必須是有限數值" % k, k)
        if mar is None and mu is None:
            return err("需提供 MAR 或 MU 其中之一", "MAR")
        if mar is not None and mu is not None:
            # 一致條件：(1 - MAR/100) * (1 + MU/100) = 1
            if abs((1 - mar / 100.0) * (1 + mu / 100.0) - 1) > 1e-9:
                return err("MAR 與 MU 不一致", "MAR")
        if unknown == "CST":
            s = float(sel)
            if mar is not None:
                c = s * (1 - mar / 100.0)
            else:
                if mu == -100:
                    return err("MU 不可為 -100", "MU")
                c = s / (1 + mu / 100.0)
        else:
            c = float(cst)
            if mar is not None:
                if mar == 100:
                    return err("MAR 不可為 100（除以零）", "MAR")
                s = c / (1 - mar / 100.0)
            else:
                s = c * (1 + mu / 100.0)
    if s == 0:
        return err("售價為 0，毛利率無法計算", "SEL")
    if c == 0:
        return err("成本為 0，加成率無法計算", "CST")
    return ok({"CST": c, "SEL": s, "MAR": (s - c) / s * 100.0,
               "MU": (s - c) / c * 100.0})


def breakeven(fc=None, vc=None, p=None, pft=None, q=None, unknown="Q"):
    """損益：PFT = P*Q - (FC + VC*Q)。"""
    v = {"FC": fc, "VC": vc, "P": p, "PFT": pft, "Q": q}
    names = ("FC", "VC", "P", "PFT", "Q")
    e = _check(v, names, unknown)
    if e:
        return e
    if unknown == "Q":
        if p == vc:
            return err("售價等於變動成本，無法損益兩平", "P")
        v["Q"] = (fc + pft) / (p - vc)
    elif unknown in ("P", "VC"):
        if q == 0:
            return err("數量為 0，無法求解", "Q")
        if unknown == "P":
            v["P"] = (fc + pft) / q + vc
        else:
            v["VC"] = p - (fc + pft) / q
    elif unknown == "FC":
        v["FC"] = (p - vc) * q - pft
    else:
        v["PFT"] = (p - vc) * q - fc
    return ok({k: float(v[k]) for k in names})


def pct_change(old=None, new=None, pct=None, pd=None, unknown="NEW"):
    """複利百分比變動：NEW = OLD * (1 + PCT/100) ** PD；PD 預設 1。"""
    names = ("OLD", "NEW", "PCT", "PD")
    v = {"OLD": old, "NEW": new, "PCT": pct, "PD": pd}
    if unknown != "PD" and pd is None:
        v["PD"] = 1
    e = _check(v, names, unknown)
    if e:
        return e
    try:
        e = _pct_solve(v, unknown)
    except (OverflowError, ZeroDivisionError, ValueError):
        return err("計算結果超出範圍（溢位）", unknown)
    if e:
        return e
    return ok({k: float(v[k]) for k in names})


def _pct_solve(v, unknown):
    """pct_change 的求解本體；成功回傳 None 並寫回 v，失敗回傳 err。"""
    o, n, c, d = v["OLD"], v["NEW"], v["PCT"], v["PD"]
    base = 1 + c / 100.0 if unknown != "PCT" else None
    if unknown in ("NEW", "OLD"):
        if base < 0 and d != int(d):
            return err("底數為負時 PD 必須是整數", "PD")
        if base == 0 and d <= 0:
            return err("(1+PCT/100) 為 0 時 PD 必須大於 0", "PD")
        f = base ** d
        if isinstance(f, complex):
            return err("無實數解", "PCT")
        if unknown == "NEW":
            v["NEW"] = o * f
        else:
            if f == 0:
                return err("成長倍數為 0，無法反求 OLD", "PCT")
            v["OLD"] = n / f
        return None
    if o == 0:
        return err("OLD 為 0，無法求解", "OLD")
    ratio = n / o
    if unknown == "PCT":
        if d == 0:
            return err("PD 為 0，無法求解", "PD")
        if ratio < 0:
            return err("NEW/OLD 為負，無實數解", "NEW")
        if ratio == 0 and d < 0:
            return err("NEW 為 0 且 PD 為負，無解", "NEW")
        v["PCT"] = (ratio ** (1.0 / d) - 1) * 100.0
        return None
    # 求 PD
    if ratio <= 0:
        return err("NEW/OLD 必須大於 0 才能求期數", "NEW")
    if base <= 0:
        return err("PCT 必須大於 -100", "PCT")
    if c == 0:
        return err("PCT 為 0 時期數無法決定", "PCT")
    v["PD"] = math.log(ratio) / math.log(base)
    return None


def tax(amount, rate_pct, mode):
    """稅額：amount 為元；mode 為 exclusive（未稅求含稅）或 inclusive（含稅求未稅）。

    內部以分（cents）整數運算，輸出換回元。
    """
    if not _is_num(amount):
        return err("金額必須是有限數值", "amount")
    if abs(amount) >= money.MAX_AMOUNT:
        return err("金額絕對值必須小於 1e13 元", "amount")
    if not _is_num(rate_pct) or rate_pct <= -100:
        return err("稅率必須是大於 -100 的有限數值", "rate")
    if mode not in ("exclusive", "inclusive"):
        return err("mode 必須是 exclusive 或 inclusive", "mode")
    cents = money.to_cents(amount)
    if mode == "exclusive":
        r = money.tax_exclusive(cents, rate_pct)
    else:
        r = money.tax_inclusive(cents, rate_pct)
    return ok({k: r[k] / 100.0 for k in ("net", "tax", "gross")})


# 稅率預設值；僅收錄於官方網頁查證到者，checked 為查證日期
TAX_PRESETS = {
    "營業稅": {
        "rate": 5,
        "source_url": ("https://www.etax.nat.gov.tw/etwmain/tax-info/"
                       "innotative-tax-e-reference/filing/business-tax/"
                       "wMDMRl7"),
        "checked": "2026-10-20",
    },
    "二代健保補充保費": {
        "rate": 2.11,
        "source_url": "https://www.mohw.gov.tw/cp-4624-57420-1.html",
        "checked": "2026-10-20",
    },
}
