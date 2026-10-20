"""AMORT 分期攤還（amortization worksheet）。

符號慣例同 Excel CUMIPMT／CUMPRINC：INT、PRN 為負（付出），
BAL 與 PV 同號。逐期遞推（不做中途四捨五入）：
    INT_k = -(BAL_{k-1} * i)，BGN 第 1 期為 0
    PRN_k = PMT - INT_k
    BAL_k = BAL_{k-1} + PRN_k
"""
from engine.result import err, is_finite, ok
from engine.tvm import period_rate

_TAIL_TOL = 0.005


def _is_num(x):
    """是否為有限實數（排除 bool、字串、inf、nan）。"""
    return (isinstance(x, (int, float)) and not isinstance(x, bool)
            and is_finite(x))


def _prepare(inputs):
    """檢查並回傳 (n, i, pv, pmt, bgn)；失敗回 err 結果。"""
    for key in ("N", "IY", "PV", "PMT", "PY", "CY"):
        if inputs.get(key) is None:
            return err("缺少 %s" % key, key)
    if not inputs["PY"] > 0:
        return err("P/Y 必須大於 0", "PY")
    if not inputs["CY"] > 0:
        return err("C/Y 必須大於 0", "CY")
    if 1 + inputs["IY"] / 100 / inputs["CY"] <= 0:
        return err("I/Y 數值不合理（利率低於 -100%）", "IY")
    if not _is_num(inputs["N"]):
        return err("N 必須為有限數值", "N")
    if inputs["N"] != int(inputs["N"]):
        return err("N 必須為整數期數", "N")
    n = int(inputs["N"])
    if n < 1:
        return err("N 必須為正整數", "N")
    i = period_rate(inputs["IY"], inputs["PY"], inputs["CY"])
    return n, i, inputs["PV"], inputs["PMT"], bool(inputs.get("BGN", False))


def _step(bal, k, i, pmt, bgn):
    """第 k 期：回傳 (INT, PRN, 新餘額)。"""
    interest = 0.0 if (bgn and k == 1) else -(bal * i)
    prn = pmt - interest
    return interest, prn, bal + prn


def amort(inputs, p1, p2):
    """第 p1～p2 期的累計利息 INT、本金 PRN 與第 p2 期後餘額 BAL。"""
    prep = _prepare(inputs)
    if isinstance(prep, dict):
        return prep
    n, i, pv, pmt, bgn = prep
    for name, p in (("P1", p1), ("P2", p2)):
        if p is None:
            return err("缺少 %s" % name, name)
        if not _is_num(p):
            return err("%s 必須為有限數值" % name, name)
        if p != int(p):
            return err("%s 必須為整數期數" % name, name)
    if p1 < 1:
        return err("P1 必須 >= 1", "P1")
    if p2 < p1:
        return err("P2 必須 >= P1", "P2")
    if p2 > n:
        return err("P2 必須 <= N", "P2")
    bal = pv
    tot_int = tot_prn = 0.0
    try:
        for k in range(1, int(p2) + 1):
            interest, prn, bal = _step(bal, k, i, pmt, bgn)
            if k >= p1:
                tot_int += interest
                tot_prn += prn
    except OverflowError:
        return err("計算結果超出範圍（溢位）", "P2")
    return ok({"BAL": bal, "PRN": tot_prn, "INT": tot_int})


def schedule(inputs):
    """完整攤還表，列為 [期數, PMT, INT, PRN, BAL]；末期有尾差時加警告。"""
    prep = _prepare(inputs)
    if isinstance(prep, dict):
        return prep
    n, i, pv, pmt, bgn = prep
    rows = []
    bal = pv
    try:
        for k in range(1, n + 1):
            interest, prn, bal = _step(bal, k, i, pmt, bgn)
            rows.append([k, pmt, interest, prn, bal])
    except OverflowError:
        return err("計算結果超出範圍（溢位）", "N")
    warnings = []
    tail = bal + (inputs.get("FV") or 0)
    if abs(tail) > _TAIL_TOL:
        warnings.append("最後一期有尾差 %.2f" % tail)
    return ok({"rows": rows}, warnings)
