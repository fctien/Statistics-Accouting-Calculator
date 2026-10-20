"""顯示格式與輸入解析（display formatting / input parsing）。

format_number：固定小數位（0～9）或浮動（floating）模式，千分位與小數點可選
美式（us：1,234.50）或歐式（eu：1.234,50）。
進位一律在 '%.15g' 產生的十進位字串上做 half away from zero，
不用 round()、不用 format 規格。僅用 '%' 格式化，MicroPython 亦可用。
解析失敗或輸入不合法一律回傳錯誤字串或 None，不拋例外。
"""

_ERR = "錯誤"
_INF = float("inf")
_SEPS = {"us": (",", "."), "eu": (".", ",")}  # (千分位, 小數點)
_FLOAT_SIG = 10          # 浮動模式最多有效位數
_SCI_HIGH = 10           # 指數 >= 10 用科學記號
_SCI_LOW = -9            # 指數 < -9 用科學記號
_DIGITS = "0123456789"
_FULL_DIGITS = "０１２３４５６７８９"


def _decompose(x):
    """把有限數 |x| 拆成 (有效數字字串 ds, 小數點前位數 dp)。

    值 = 0.ds * 10**dp；ds 無前導 0、無尾端 0；零回傳 ("", 0)。
    """
    s = "%.15g" % abs(x)
    exp = 0
    low = s.lower()
    if "e" in low:
        i = low.index("e")
        exp = int(low[i + 1:])
        s = low[:i]
    if "." in s:
        ip, fp = s.split(".")
    else:
        ip, fp = s, ""
    digits = ip + fp
    dp = len(ip) + exp
    stripped = digits.lstrip("0")
    dp -= len(digits) - len(stripped)
    stripped = stripped.rstrip("0")
    if stripped == "":
        return "", 0
    return stripped, dp


def _round_digits(ds, dp, keep):
    """保留前 keep 位有效數字（half away from zero），回傳 (ds, dp)。

    keep <= 0 時：keep == 0 且首位 >= 5 進位成 1；其餘為零。
    """
    if ds == "" or keep >= len(ds):
        return ds, dp
    if keep < 0:
        return "", 0
    up = ds[keep] >= "5"
    head = ds[:keep]
    if not up:
        head = head.rstrip("0")
        return (head, dp) if head else ("", 0)
    n = str(int(head or "0") + 1)
    if keep == 0:
        return "1", dp + 1
    if len(n) > keep:      # 99.. 進位使位數增加
        dp += 1
    n = n.rstrip("0")
    return n, dp


def _group(int_str, tsep):
    """整數字串每三位加千分位。"""
    out = []
    while len(int_str) > 3:
        out.append(int_str[-3:])
        int_str = int_str[:-3]
    out.append(int_str)
    out.reverse()
    return tsep.join(out)


def _plain(ds, dp, min_frac, tsep, dsep):
    """由 (ds, dp) 組出一般（非科學）表示，小數至少 min_frac 位。"""
    if dp <= 0:
        int_part = "0"
        frac = "0" * (-dp) + ds
    elif dp >= len(ds):
        int_part = ds + "0" * (dp - len(ds))
        frac = ""
    else:
        int_part = ds[:dp]
        frac = ds[dp:]
    if ds == "":
        frac = ""
    if len(frac) < min_frac:
        frac += "0" * (min_frac - len(frac))
    text = _group(int_part, tsep)
    if frac:
        text += dsep + frac
    return text


def format_number(x, decimals, sep="us"):
    """格式化數字。decimals 為 0～9（固定小數位）或 None（浮動）。

    任何不合法輸入（NaN、inf、decimals 超出範圍、型別錯誤）回傳「錯誤」。
    """
    if sep not in _SEPS:
        return _ERR
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return _ERR
    if decimals is not None:
        if isinstance(decimals, bool) or not isinstance(decimals, int):
            return _ERR
        if decimals < 0 or decimals > 9:
            return _ERR
    try:
        x = float(x)
    except (OverflowError, ValueError):
        return _ERR
    if x != x or x == _INF or x == -_INF:
        return _ERR
    tsep, dsep = _SEPS[sep]
    ds, dp = _decompose(x)
    neg = x < 0

    if decimals is not None:
        # 固定小數位：保留 dp + decimals 位有效數字
        ds, dp = _round_digits(ds, dp, dp + decimals)
        if ds == "":
            neg = False
        text = _plain(ds, dp, decimals, tsep, dsep)
        return ("-" + text) if neg else text

    # 浮動模式
    ds, dp = _round_digits(ds, dp, _FLOAT_SIG)
    if ds == "":
        return "0"
    e = dp - 1
    if e >= _SCI_HIGH or e < _SCI_LOW:
        mant = ds[0]
        if len(ds) > 1:
            mant += dsep + ds[1:]
        text = mant + "E" + str(e)
    else:
        text = _plain(ds, dp, 0, tsep, dsep)
    return ("-" + text) if neg else text


def _normalize(text):
    """全形數字轉半形、全形負號／空白轉半形。"""
    out = []
    for ch in text:
        if ch in _FULL_DIGITS:
            out.append(_DIGITS[_FULL_DIGITS.index(ch)])
        elif ch == "－":
            out.append("-")
        elif ch == "\u3000":
            out.append(" ")
        else:
            out.append(ch)
    return "".join(out)


def _all_digits(s):
    """s 非空且全為 0-9。"""
    if s == "":
        return False
    for ch in s:
        if ch not in _DIGITS:
            return False
    return True


def _valid_int_part(s, tsep):
    """整數部分：純數字，或千分位分組正確（首組 1～3 位，其後每組 3 位）。"""
    if tsep not in s:
        return _all_digits(s)
    groups = s.split(tsep)
    if not (1 <= len(groups[0]) <= 3) or not _all_digits(groups[0]):
        return False
    for g in groups[1:]:
        if len(g) != 3 or not _all_digits(g):
            return False
    return True


def parse_number(text, sep="us"):
    """解析使用者輸入為 float；無法解析（或結果為 inf／nan）回傳 None。"""
    if sep not in _SEPS or not isinstance(text, str):
        return None
    tsep, dsep = _SEPS[sep]
    s = _normalize(text).strip()
    sign = ""
    if s[:1] in ("+", "-"):
        sign = "-" if s[0] == "-" else ""
        s = s[1:]
    exp = ""
    low = s.lower()
    if "e" in low:
        i = low.index("e")
        exp = low[i + 1:]
        s = s[:i]
        body = exp[1:] if exp[:1] in ("+", "-") else exp
        if not _all_digits(body):
            return None
    if s.count(dsep) > 1:
        return None
    if dsep in s:
        ip, fp = s.split(dsep)
    else:
        ip, fp = s, ""
    if ip == "" and fp == "":
        return None
    if ip != "" and not _valid_int_part(ip, tsep):
        return None
    if fp != "" and not _all_digits(fp):
        return None
    clean = ip.replace(tsep, "") or "0"
    literal = sign + clean + ("." + fp if fp else "")
    if exp:
        literal += "e" + exp
    try:
        v = float(literal)
    except ValueError:
        return None
    if v != v or v == _INF or v == -_INF:
        return None
    return v
