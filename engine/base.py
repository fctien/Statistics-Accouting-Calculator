"""進位轉換（number base conversion）與位元運算（bitwise operations）。

位寬 width ∈ 8、16、32、64；signed 為 True 時以二補數（two's complement）解讀。
輸出四種進位字串：BIN（補滿 width 位）、OCT（補滿 ceil(width/3) 位）、
DEC（無千分位，負數帶負號）、HEX（大寫，補滿 width/4 位）。
BIN／OCT／HEX 顯示的是位元型樣（bit pattern），負數即其二補數型樣。

輸入規則（parse）：
    - 進位 2、8、10、16；16 進位大小寫皆可；空白與底線可作分組，會被忽略。
    - 可選前綴，且必須與進位相符：0b（2）、0o（8）、0x（16）；10 進位無前綴。
      （16 進位的 "0B1" 是數字 0、B、1，不視為前綴。）
    - 正負號 + / - 只允許 10 進位；其他進位以位元型樣輸入（signed 時依二補數解讀）。
    - 小數點、其他字元一律錯誤；非法字元回報其在原字串中的第幾個字元（從 1 起算）。
    - 超出位寬可表示的範圍一律報錯，絕不截斷或環繞。
位元運算的遮罩（mask）是運算定義的一部分（例如 SHL 溢出的位元被丟棄、NOT 取補數），
不是截斷錯誤；但輸入值超出範圍仍然報錯。
僅用 CPython 與 MicroPython 都支援的功能（整數運算只用 Python int）。
"""
from engine.result import err, ok

_WIDTHS = (8, 16, 32, 64)
_BASES = (2, 8, 10, 16)
_DIGITS = "0123456789ABCDEF"
_PREFIX = {2: "0b", 8: "0o", 16: "0x"}
_OPS = ("AND", "OR", "XOR", "NOT", "SHL", "SHR", "SAR")


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _check_params(width, signed):
    """驗證位寬與 signed；合法回 None，否則回 err。"""
    if not _is_int(width) or width not in _WIDTHS:
        return err("位寬必須是 8、16、32 或 64", "WIDTH")
    if not isinstance(signed, bool):
        return err("SIGNED 必須是 true 或 false", "SIGNED")
    return None


def _range(width, signed):
    """回傳 (最小值, 最大值)。"""
    if signed:
        return -(1 << (width - 1)), (1 << (width - 1)) - 1
    return 0, (1 << width) - 1


def _to_pattern(value, width):
    """整數值 -> 無號位元型樣（遮罩 width 位）。"""
    return value & ((1 << width) - 1)


def _from_pattern(pattern, width, signed):
    """無號位元型樣 -> 整數值（signed 時以二補數解讀）。"""
    if signed and pattern >= (1 << (width - 1)):
        return pattern - (1 << width)
    return pattern


def _digits(n, base, min_len):
    """非負整數轉 base 進位大寫字串，左補 0 至 min_len 位。"""
    out = []
    while n > 0:
        out.append(_DIGITS[n % base])
        n //= base
    while len(out) < min_len:
        out.append("0")
    if not out:
        out.append("0")
    out.reverse()
    return "".join(out)


def _format_all(value, width, signed):
    """整數值 -> {"BIN","OCT","DEC","HEX"} 字串。"""
    pat = _to_pattern(value, width)
    dec = str(value)
    return {"BIN": _digits(pat, 2, width),
            "OCT": _digits(pat, 8, (width + 2) // 3),
            "DEC": dec,
            "HEX": _digits(pat, 16, width // 4)}


def parse_int(text, from_base, width, signed):
    """把進位字串解析為整數值；回傳 ok({"value": int}) 或 err（field 為 None）。"""
    bad = _check_params(width, signed)
    if bad:
        return bad
    if not _is_int(from_base) or from_base not in _BASES:
        return err("進位必須是 2、8、10 或 16", "FROM")
    if not isinstance(text, str):
        return err("請輸入文字形式的數值", None)
    chars = []          # (原字串位置 1 起算, 字元)
    for i, ch in enumerate(text):
        if ch in " _\t":
            continue
        chars.append((i + 1, ch))
    if not chars:
        return err("請輸入數值", None)
    sign = 1
    if chars[0][1] in "+-":
        if from_base != 10:
            return err("第 %d 個字元 '%s' 不合法：只有 10 進位可用正負號，"
                       "其他進位請直接輸入位元型樣" % chars[0], None)
        if chars[0][1] == "-":
            sign = -1
        chars = chars[1:]
    pre = _PREFIX.get(from_base)
    if (pre and len(chars) >= 2 and chars[0][1] == "0"
            and chars[1][1].lower() == pre[1]):
        chars = chars[2:]
    if not chars:
        return err("請輸入數值（只有符號或前綴）", None)
    n = 0
    for pos, ch in chars:
        d = _DIGITS.find(ch.upper())
        if ch == ".":
            return err("第 %d 個字元 '.' 不合法：只接受整數" % pos, None)
        if d < 0 or d >= from_base:
            return err("第 %d 個字元 '%s' 不是 %d 進位的合法數字"
                       % (pos, ch, from_base), None)
        n = n * from_base + d
    lo, hi = _range(width, signed)
    if from_base == 10:
        value = sign * n
        if value < lo or value > hi:
            return err("數值超出 %d 位%s範圍（%d～%d）"
                       % (width, "有號" if signed else "無號", lo, hi), None)
        return ok({"value": value})
    if n >= (1 << width):
        return err("數值超出 %d 位範圍（位元型樣最大 %s）"
                   % (width, _digits((1 << width) - 1, from_base, 1)), None)
    return ok({"value": _from_pattern(n, width, signed)})


def convert_base(text, from_base, width, signed):
    """進位轉換：回傳 ok({"BIN","OCT","DEC","HEX"}) 四個字串。"""
    r = parse_int(text, from_base, width, signed)
    if not r["ok"]:
        return err(r["error"], "TEXT" if r["field"] is None else r["field"])
    return ok(_format_all(r["values"]["value"], width, signed))


def bitwise(op, a, b, width, signed):
    """位元運算。a、b 為整數值（signed 時可為負）；NOT 忽略 b。

    SHL／SHR／SAR 的 b 為位移量，須在 0..width；SHR 為邏輯右移（對位元型樣），
    SAR 為算術右移（保號），只適用於有號數。結果依位寬遮罩後，
    signed 時以二補數解讀。
    """
    bad = _check_params(width, signed)
    if bad:
        return bad
    if not isinstance(op, str) or op not in _OPS:
        return err("運算必須是 " + "、".join(_OPS), "OP")
    lo, hi = _range(width, signed)
    if not _is_int(a) or a < lo or a > hi:
        return err("A 必須是 %d 位%s範圍內的整數（%d～%d）"
                   % (width, "有號" if signed else "無號", lo, hi), "A")
    pa = _to_pattern(a, width)
    mask = (1 << width) - 1
    if op == "NOT":
        res = (~pa) & mask
    else:
        if not _is_int(b):
            return err("請輸入 B", "B")
        if op in ("SHL", "SHR", "SAR"):
            if b < 0 or b > width:
                return err("位移量必須在 0～%d" % width, "B")
        elif b < lo or b > hi:
            return err("B 必須是 %d 位%s範圍內的整數（%d～%d）"
                       % (width, "有號" if signed else "無號", lo, hi), "B")
        pb = _to_pattern(b, width)
        if op == "AND":
            res = pa & pb
        elif op == "OR":
            res = pa | pb
        elif op == "XOR":
            res = pa ^ pb
        elif op == "SHL":
            res = (pa << b) & mask
        elif op == "SHR":
            res = pa >> b
        else:  # SAR
            if not signed:
                return err("SAR（算術右移）只適用於有號數", "OP")
            res = (a >> b) & mask
    return ok(_format_all(_from_pattern(res, width, signed), width, signed))
