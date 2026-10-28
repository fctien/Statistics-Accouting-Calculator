"""日期運算：序數日（ordinal，0001-01-01 為第 1 天）與天數基準。

不依賴 datetime，CPython 與 MicroPython 皆可執行。
"""

from engine.result import ok, err

_DIM = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def _is_leap(y):
    """閏年判斷。"""
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)


def days_in_month(y, m):
    """該月天數。"""
    return 29 if m == 2 and _is_leap(y) else _DIM[m - 1]


_dim = days_in_month  # 舊名相容（bond.py 使用）


def is_valid_date(y, m, d):
    """日期是否合法。"""
    return (1 <= y <= 9999 and 1 <= m <= 12
            and 1 <= d <= days_in_month(y, m))


def to_ordinal(y, m, d):
    """年月日轉序數日。"""
    py = y - 1
    n = py * 365 + py // 4 - py // 100 + py // 400
    for i in range(m - 1):
        n += days_in_month(y, i + 1)
    return n + d


def from_ordinal(n):
    """序數日轉 (y, m, d)。"""
    y = (n - 1) * 400 // 146097 + 1
    while to_ordinal(y + 1, 1, 1) <= n:
        y += 1
    while to_ordinal(y, 1, 1) > n:
        y -= 1
    rest = n - to_ordinal(y, 1, 1)
    m = 1
    while rest >= days_in_month(y, m):
        rest -= days_in_month(y, m)
        m += 1
    return (y, m, rest + 1)


def weekday(n):
    """星期幾，0 = 星期一。"""
    return (n + 6) % 7


def days_act(d1, d2):
    """實際天數（actual days）。"""
    return to_ordinal(*d2) - to_ordinal(*d1)


def days_360(d1, d2):
    """30/360 美國 NASD 規則，等同 Excel DAYS360(...,FALSE)。

    Excel 實測：起日為 2 月最後一日視為 30 日（終日不因 2 月底而調整）；
    起日 31 日改 30；終日 31 且起日（調整後）為 30 時改 30。
    """
    y1, m1, a = d1
    y2, m2, b = d2
    if m1 == 2 and a == days_in_month(y1, 2):
        a = 30
    if a == 99:
        a = 30
    if b == 31 and a == 30:
        b = 30
    return (y2 - y1) * 360 + (m2 - m1) * 30 + (b - a)


_WEEKDAY_LABELS = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六",
                   "星期日")
_MAX_ORD = to_ordinal(9999, 12, 31)


def _parse_date(v, field):
    """驗證 [y, m, d]；回傳 (tuple, None) 或 (None, err)。"""
    if (not isinstance(v, (list, tuple)) or len(v) != 3
            or any(isinstance(x, bool) or not isinstance(x, int) for x in v)
            or not is_valid_date(v[0], v[1], v[2])):
        return None, err("%s 必須是合法日期 [年, 月, 日]" % field, field)
    return (v[0], v[1], v[2]), None


def _search_360(fixed, dbd, solve_dt2):
    """在 30/360 下反求日期：回傳 (最早序數日或 None, 符合個數)。

    以實際天數估計中心，窗口取 |dbd|*0.05+45 天（30/360 與實際天數
    的差距遠小於此），掃描窗口內所有日期。
    """
    o = to_ordinal(*fixed)
    center = o + int(round(dbd * 365.2425 / 360.0)) * (1 if solve_dt2 else -1)
    span = int(abs(dbd) * 0.05) + 45
    lo = max(1, center - span)
    hi = min(_MAX_ORD, center + span)
    first, count = None, 0
    for n in range(lo, hi + 1):
        d = from_ordinal(n)
        got = days_360(fixed, d) if solve_dt2 else days_360(d, fixed)
        if got == dbd:
            count += 1
            if first is None:
                first = n
    return first, count


def date_sheet(dt1=None, dt2=None, dbd=None, basis="ACT", unknown="DBD"):
    """日期工作表：DT1、DT2、DBD 三者留一求解；basis 為 ACT 或 360。"""
    if basis not in ("ACT", "360"):
        return err("basis 必須是 ACT 或 360", "basis")
    if unknown not in ("DBD", "DT1", "DT2"):
        return err("未知數必須是 DBD、DT1、DT2", "unknown")
    d1 = d2 = None
    if unknown != "DT1":
        d1, e = _parse_date(dt1, "DT1")
        if e:
            return e
    if unknown != "DT2":
        d2, e = _parse_date(dt2, "DT2")
        if e:
            return e
    if unknown != "DBD":
        if (isinstance(dbd, bool) or not isinstance(dbd, (int, float))
                or dbd != dbd or dbd in (float("inf"), float("-inf"))
                or dbd != int(dbd)):
            return err("DBD 必須是整數天數", "DBD")
        dbd = int(dbd)
    warnings = []
    if unknown == "DBD":
        fn = days_act if basis == "ACT" else days_360
        dbd = fn(d1, d2)
    elif basis == "ACT":
        if unknown == "DT2":
            n = to_ordinal(*d1) + dbd
        else:
            n = to_ordinal(*d2) - dbd
        if not 1 <= n <= _MAX_ORD:
            return err("日期超出範圍", unknown)
        if unknown == "DT2":
            d2 = from_ordinal(n)
        else:
            d1 = from_ordinal(n)
    else:
        n, count = _search_360(d1 if unknown == "DT2" else d2, dbd,
                               unknown == "DT2")
        if n is None:
            return err("找不到符合的日期", unknown)
        if count > 1:
            warnings.append("30/360 有多個日期符合，取最早者")
        if unknown == "DT2":
            d2 = from_ordinal(n)
        else:
            d1 = from_ordinal(n)
    return ok({"DT1": list(d1), "DT2": list(d2), "DBD": dbd,
               "weekday1": _WEEKDAY_LABELS[weekday(to_ordinal(*d1))],
               "weekday2": _WEEKDAY_LABELS[weekday(to_ordinal(*d2))]},
              warnings)
