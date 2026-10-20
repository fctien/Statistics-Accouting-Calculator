"""計算機算式剖析器（recursive descent parser）。

自寫詞法分析（tokenizer）與遞迴下降文法，不使用動態執行函式
（MicroPython 沒有 ast）。模式：
- AOS：代數運算優先序（^ 最高，其次 × ÷，最後 + −）
- CHAIN：二元 + − × ÷ ^ 一律由左到右、優先序相同；
  一元負號、後置運算（! % ²）、函式與括號仍照常結合

百分比 %：一般為 ÷100；作為二元 + 或 − 的「直接右運算元」時，
a ± b% = a ± a·b/100。

僅用 math；所有錯誤以 err(訊息, "expr") 回傳，絕不 raise。
"""
import math

from engine.result import err, ok, is_finite

_MAX_DEPTH = 40  # 巢狀深度上限（遞迴保護，MicroPython 堆疊較小）
_DIGITS = "0123456789"
_FUNCS = {"sqrt": 1, "ln": 1, "exp": 1, "inv": 1, "nPr": 2, "nCr": 2}
_MUL = {"*": "*", "×": "*", "/": "/", "÷": "/"}


class _CalcError(Exception):
    """內部錯誤：訊息與位置（1 起算）。"""

    def __init__(self, msg, pos):
        Exception.__init__(self, msg)
        self.msg = msg
        self.pos = pos


def _tokenize(s):
    """切成 (種類, 值, 位置) 清單；位置為 1 起算。"""
    toks = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c in " \t\r\n":
            i += 1
        elif c in _DIGITS or c == ".":
            j = i
            while j < n and s[j] in _DIGITS:
                j += 1
            if j < n and s[j] == ".":
                j += 1
                while j < n and s[j] in _DIGITS:
                    j += 1
            text = s[i:j]
            if not any(ch in _DIGITS for ch in text):
                raise _CalcError("無效的數字", i + 1)
            # 指數部分：e/E 後須有（可帶正負號的）數字才算
            if j < n and s[j] in "eE":
                k = j + 1
                if k < n and s[k] in "+-":
                    k += 1
                if k < n and s[k] in _DIGITS:
                    while k < n and s[k] in _DIGITS:
                        k += 1
                    text = s[i:k]
                    j = k
            try:
                val = float(text)
            except ValueError:
                raise _CalcError("無效的數字", i + 1)
            if not is_finite(val):
                raise _CalcError("數字超出範圍", i + 1)
            toks.append(("num", val, i + 1))
            i = j
        elif c.isalpha():
            j = i
            while j < n and (s[j].isalpha() or s[j] in _DIGITS):
                j += 1
            toks.append(("id", s[i:j], i + 1))
            i = j
        elif c in "+-−*×/÷^()!%²√,":
            toks.append(("op", c, i + 1))
            i += 1
        else:
            raise _CalcError("無法辨識的字元「%s」" % c, i + 1)
    return toks


def _fin(v, pos):
    """運算結果須為有限數，否則視為溢位。"""
    if not is_finite(v):
        raise _CalcError("計算結果超出範圍（溢位）", pos)
    return v


def _is_int(x):
    """x 是否為（合理範圍內的）整數值。"""
    return is_finite(x) and abs(x) < 1e15 and x == int(x)


def _factorial(x, pos):
    if not _is_int(x) or x < 0:
        raise _CalcError("階乘 ! 只接受非負整數", pos)
    if x > 170:
        raise _CalcError("階乘 ! 的數值過大（超過 170）", pos)
    r = 1.0
    for k in range(2, int(x) + 1):
        r *= k
    return r


def _check_nr(n, r, pos):
    if not (_is_int(n) and _is_int(r)) or n < 0 or r < 0 or r > n:
        raise _CalcError("nPr／nCr 的 n、r 須為整數且 0 ≤ r ≤ n", pos)
    return int(n), int(r)


def _perm(n, r, pos):
    n, r = _check_nr(n, r, pos)
    res = 1.0
    for k in range(r):
        res *= (n - k)
        if not is_finite(res):
            raise _CalcError("計算結果超出範圍（溢位）", pos)
    return res


def _comb(n, r, pos):
    n, r = _check_nr(n, r, pos)
    r = min(r, n - r)
    res = 1.0
    for k in range(1, r + 1):
        res = res * (n - r + k) / k
        if not is_finite(res):
            raise _CalcError("計算結果超出範圍（溢位）", pos)
    return float(round(res)) if res < 1e15 else res


def _power(a, b, pos):
    if a < 0 and not _is_int(b):
        raise _CalcError("負數的非整數次方無實數解", pos)
    if a == 0 and b < 0:
        raise _CalcError("0 不能取負次方（除以零）", pos)
    try:
        r = math.pow(a, b)
    except (OverflowError, ValueError):
        raise _CalcError("計算結果超出範圍（溢位）", pos)
    return _fin(r, pos)


def _call(name, args, pos):
    return _fin(_call_raw(name, args, pos), pos)


def _call_raw(name, args, pos):
    if name == "nPr":
        return _perm(args[0], args[1], pos)
    if name == "nCr":
        return _comb(args[0], args[1], pos)
    x = args[0]
    if name == "sqrt":
        if x < 0:
            raise _CalcError("負數不能開平方根", pos)
        return math.sqrt(x)
    if name == "ln":
        if x <= 0:
            raise _CalcError("ln 的引數須大於 0", pos)
        return math.log(x)
    if name == "exp":
        try:
            return math.exp(x)
        except OverflowError:
            raise _CalcError("計算結果超出範圍（溢位）", pos)
    if x == 0:  # inv
        raise _CalcError("除以零", pos)
    return 1.0 / x


class _Parser:
    def __init__(self, toks, mode, ans, mem):
        self.t = toks
        self.i = 0
        self.chain = (mode == "CHAIN")
        self.ans = ans
        self.mem = mem
        self.depth = 0
        self.end = (toks[-1][2] + 1) if toks else 1

    # ---- 基本操作 ----
    def peek(self):
        if self.i < len(self.t):
            return self.t[self.i]
        return ("eof", None, self.end)

    def take(self):
        tok = self.peek()
        self.i += 1
        return tok

    def is_op(self, *ops):
        tok = self.peek()
        return tok[0] == "op" and tok[1] in ops

    def enter(self, pos):
        self.depth += 1
        if self.depth > _MAX_DEPTH:
            raise _CalcError("算式巢狀過深", pos)

    def leave(self):
        self.depth -= 1

    # ---- 文法 ----
    def parse(self):
        if not self.t:
            raise _CalcError("算式是空的", 1)
        v, _ = self.expr()
        tok = self.peek()
        if tok[0] != "eof":
            if tok[1] == ")":
                raise _CalcError("多餘的右括號", tok[2])
            raise _CalcError("算式有多餘的內容", tok[2])
        return v

    def expr(self):
        self.enter(self.peek()[2])
        try:
            return self.chain_expr() if self.chain else self.aos_expr()
        finally:
            self.leave()

    @staticmethod
    def _addsub(op, left, right, pct, pos):
        if pct:  # a ± b% = a ± a·b/100（right 已除以 100）
            right = _fin(left * right, pos)
        return _fin(left + right if op == "+" else left - right, pos)

    def aos_expr(self):
        left, pct = self.term()
        while self.is_op("+", "-", "−"):
            op = self.take()
            right, rpct = self.term()
            left = self._addsub("+" if op[1] == "+" else "-",
                                left, right, rpct, op[2])
            pct = False
        return left, pct

    def term(self):
        left, pct = self.unary()
        while self.is_op("*", "×", "/", "÷"):
            op = self.take()
            right, _ = self.unary()
            left = self._muldiv(_MUL[op[1]], left, right, op[2])
            pct = False
        return left, pct

    @staticmethod
    def _muldiv(op, a, b, pos):
        if op == "*":
            return _fin(a * b, pos)
        if b == 0:
            raise _CalcError("除以零", pos)
        return _fin(a / b, pos)

    def chain_expr(self):
        left, pct = self.unary()
        while self.is_op("+", "-", "−", "*", "×", "/", "÷", "^"):
            op = self.take()
            right, rpct = self.unary()
            sym = op[1]
            if sym in ("+", "-", "−"):
                left = self._addsub("+" if sym == "+" else "-",
                                    left, right, rpct, op[2])
            elif sym == "^":
                left = _power(left, right, op[2])
            else:
                left = self._muldiv(_MUL[sym], left, right, op[2])
            pct = False
        return left, pct

    def unary(self):
        if self.is_op("-", "−", "+"):
            self.enter(self.peek()[2])
            try:
                op = self.take()
                v, pct = self.unary()
            finally:
                self.leave()
            return (-v if op[1] != "+" else v), pct
        if self.chain:
            return self.postfix()
        return self.power()

    def power(self):
        base, pct = self.postfix()
        if self.is_op("^"):
            op = self.take()
            self.enter(op[2])
            try:
                ex, _ = self.unary()
            finally:
                self.leave()
            return _power(base, ex, op[2]), False
        return base, pct

    def postfix(self):
        v, pct = self.primary()
        while self.is_op("!", "%", "²"):
            op = self.take()
            if op[1] == "!":
                v, pct = _factorial(v, op[2]), False
            elif op[1] == "%":
                v, pct = _fin(v / 100.0, op[2]), True
            else:
                v, pct = _fin(v * v, op[2]), False
        return v, pct

    def primary(self):
        tok = self.take()
        kind, val, pos = tok
        if kind == "num":
            return val, False
        if kind == "id":
            return self.ident(val, pos), False
        if kind == "op" and val == "(":
            v, _ = self.expr()
            close = self.take()
            if not (close[0] == "op" and close[1] == ")"):
                raise _CalcError("括號不平衡，缺少右括號", pos)
            return v, False
        if kind == "op" and val == "√":
            self.enter(pos)
            try:
                v, _ = self.postfix()
            finally:
                self.leave()
            return _call("sqrt", [v], pos), False
        if kind == "eof":
            raise _CalcError("算式不完整，缺少運算元", pos)
        raise _CalcError("此處不應出現「%s」" % val, pos)

    def ident(self, name, pos):
        if name == "ANS":
            return float(self.ans)
        if len(name) == 2 and name[0] == "M" and name[1] in "0123456789":
            return float(self.mem.get(name, 0.0))  # 未設定的記憶視為 0
        if name in _FUNCS:
            op = self.take()
            if not (op[0] == "op" and op[1] == "("):
                raise _CalcError("函式 %s 後須接左括號" % name, pos)
            args = [self.expr()[0]]
            while self.is_op(","):
                self.take()
                args.append(self.expr()[0])
            close = self.take()
            if not (close[0] == "op" and close[1] == ")"):
                raise _CalcError("括號不平衡，缺少右括號", op[2])
            if len(args) != _FUNCS[name]:
                raise _CalcError("函式 %s 需要 %d 個引數" % (name, _FUNCS[name]),
                                 pos)
            return _call(name, args, pos)
        raise _CalcError("未知的符號「%s」" % name, pos)


def evaluate(expr, mode="AOS", ans=0.0, mem=None):
    """計算算式字串，回傳 ok({"value": float}) 或 err(訊息, "expr")。

    expr：算式；mode："AOS" 或 "CHAIN"；ans：ANS 的值；
    mem：如 {"M3": 1.0}，未出現的 Mn 視為 0.0（同 TI 計算機）。
    """
    try:
        if mode not in ("AOS", "CHAIN"):
            return err("未知的運算模式 %s" % (mode,), "expr")
        if not isinstance(expr, str):
            return err("算式必須是字串", "expr")
        if isinstance(ans, bool) or not isinstance(ans, (int, float)) \
                or not is_finite(float(ans)):
            return err("ANS 必須是有限數", "expr")
        memory = {}
        if mem is not None and not isinstance(mem, dict):
            return err("mem 必須是字典（如 {\"M3\": 1.0}）", "expr")
        if mem:
            for k in mem:
                if not (isinstance(k, str) and len(k) == 2 and k[0] == "M"
                        and k[1] in _DIGITS):
                    continue  # 非 M0～M9 的鍵（如 ACC）忽略
                v = mem[k]
                if isinstance(v, bool) or not isinstance(v, (int, float)) \
                        or not is_finite(float(v)):
                    return err("記憶 %s 的值不是有限數" % (k,), "expr")
                memory[k] = v
        parser = _Parser(_tokenize(expr), mode, ans, memory)
        value = float(parser.parse())
    except _CalcError as e:
        return err("%s（第 %d 個字元）" % (e.msg, e.pos), "expr")
    except (OverflowError, ZeroDivisionError, ValueError):
        return err("計算結果超出範圍或無法計算", "expr")
    except RuntimeError:  # 含 RecursionError
        return err("算式過於複雜", "expr")
    r = ok({"value": value})
    if not r["ok"]:
        return err("計算結果超出範圍（溢位）", "expr")
    return r
