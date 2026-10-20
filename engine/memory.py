"""記憶 M0～M9 與累加器（accumulator）。

方法皆回傳 ok／err 字典，不 raise；運算失敗（除以零、溢位）時記憶值不變。
to_dict() 的 "M0"～"M9" 鍵可直接作為 calc.evaluate 的 mem 參數。
僅用 CPython 與 MicroPython 共通功能。
"""
from engine.result import err, ok, is_finite


def _num(v):
    """v 是否為有限的 int／float（排除 bool）。"""
    return (isinstance(v, (int, float)) and not isinstance(v, bool)
            and is_finite(float(v)))


class Memory:
    """十個記憶格（M0～M9）與一個累加器（sum、count）。"""

    def __init__(self):
        self._v = [0.0] * 10
        self._sum = 0.0
        self._count = 0

    @staticmethod
    def _idx_ok(i):
        return isinstance(i, int) and not isinstance(i, bool) and 0 <= i <= 9

    def _check(self, i, v=0.0):
        if not self._idx_ok(i):
            return err("記憶編號須為 0～9 的整數", "index")
        if not _num(v):
            return err("數值必須是有限數", "value")
        return None

    def store(self, i, v):
        bad = self._check(i, v)
        if bad:
            return bad
        self._v[i] = float(v)
        return ok({"value": self._v[i]})

    def recall(self, i):
        bad = self._check(i)
        if bad:
            return bad
        return ok({"value": self._v[i]})

    def _apply(self, i, v, op):
        bad = self._check(i, v)
        if bad:
            return bad
        v = float(v)
        cur = self._v[i]
        if op == "+":
            new = cur + v
        elif op == "-":
            new = cur - v
        elif op == "*":
            new = cur * v
        else:
            if v == 0:
                return err("除以零", "value")
            new = cur / v
        r = ok({"value": new})
        if r["ok"]:
            self._v[i] = new
        return r

    def add(self, i, v):
        return self._apply(i, v, "+")

    def sub(self, i, v):
        return self._apply(i, v, "-")

    def mul(self, i, v):
        return self._apply(i, v, "*")

    def div(self, i, v):
        return self._apply(i, v, "/")

    def accumulate(self, v):
        """累加一個值；回傳目前的 {"sum", "count"}。"""
        if not _num(v):
            return err("數值必須是有限數", "value")
        new = self._sum + float(v)
        r = ok({"sum": new, "count": self._count + 1})
        if r["ok"]:
            self._sum = new
            self._count += 1
        return r

    def clear_accumulator(self):
        self._sum = 0.0
        self._count = 0

    def to_dict(self):
        d = {}
        for i in range(10):
            d["M%d" % i] = self._v[i]
        d["ACC"] = {"sum": self._sum, "count": self._count}
        return d

    @classmethod
    def from_dict(cls, d):
        """由 to_dict 結果還原；驗證各值，未知鍵與不合格的值一律忽略（保持 0）。"""
        m = cls()
        if not isinstance(d, dict):
            return m
        for i in range(10):
            v = d.get("M%d" % i)
            if _num(v):
                m._v[i] = float(v)
        acc = d.get("ACC")
        if isinstance(acc, dict):
            s, c = acc.get("sum"), acc.get("count")
            if (_num(s) and isinstance(c, int) and not isinstance(c, bool)
                    and c >= 0):
                m._sum = float(s)
                m._count = c
        return m
