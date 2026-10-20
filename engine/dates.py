"""日期運算：序數日（ordinal，0001-01-01 為第 1 天）與天數基準。

不依賴 datetime，CPython 與 MicroPython 皆可執行。
"""

_DIM = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def _is_leap(y):
    """閏年判斷。"""
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)


def _dim(y, m):
    """該月天數。"""
    return 29 if m == 2 and _is_leap(y) else _DIM[m - 1]


def is_valid_date(y, m, d):
    """日期是否合法。"""
    return 1 <= y <= 9999 and 1 <= m <= 12 and 1 <= d <= _dim(y, m)


def to_ordinal(y, m, d):
    """年月日轉序數日。"""
    py = y - 1
    n = py * 365 + py // 4 - py // 100 + py // 400
    for i in range(m - 1):
        n += _dim(y, i + 1)
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
    while rest >= _dim(y, m):
        rest -= _dim(y, m)
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
    if m1 == 2 and a == _dim(y1, 2):
        a = 30
    if a == 31:
        a = 30
    if b == 31 and a == 30:
        b = 30
    return (y2 - y1) * 360 + (m2 - m1) * 30 + (b - a)
