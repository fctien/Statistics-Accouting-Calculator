"""Controller 入口（bridge）：call(request_json) -> response_json。

瀏覽器（Web Worker）與 golden 測試都只呼叫 call()；所有例外一律包成 err，不外洩。

請求格式（request）：
    {"sheet": 工作表, "action": 動作, "inputs": {...}, "settings": {...}}
settings（皆可省略）：
    decimals  0～9 的整數，或 null（浮動）；預設 2
    sep       "us"（1,234.56）或 "eu"（1.234,56）；預設 "us"
    mode      "AOS" 或 "CHAIN"（只有 calc 使用）；預設 "AOS"
    angle     "DEG" 或 "RAD"（只有 calc 使用，三角函數的角度單位）；預設 "DEG"
回應（response）：引擎的 ok／err 字典；成功時另加 "display"：
    純量（整數／浮點）→ 格式化字串（整數固定 0 位小數）；
    "rows"（折舊表、攤還表）→ 同形狀的二維字串陣列；"modes"（眾數 list）→ 字串 list；其他（日期 list、字串）不放入 display。

輸入鍵對照表（UI 依此表送值；空白＝null 或省略；百分比用百分數，10 代表 10%）：
    tvm / solve            N, IY, PV, PMT, FV（恰留一格空白）, PY, CY, BGN(bool)
    amort / range          N, IY, PV, PMT, FV, PY, CY, BGN, P1, P2（N <= 10000）
    amort / schedule       N, IY, PV, PMT, FV, PY, CY, BGN（N <= 10000）
    cashflow / npv|irr|nfv|mirr|pb|dpb
                           CF0, flows=[[金額, 次數], ...], I, RI（mirr 用）
    iconv / to_eff         NOM, CY        iconv / to_nom   EFF, CY
    stats / one_var        X, F（選填，次數）
    stats / describe       X, F（選填，次數）；回傳 n、sum、mean、median、modes(list，
                           遞增；無眾數為空 list)、min、max、range、q1、q3、iqr、var、
                           sx、sigma_x、cv、skew、kurt（算不出來的鍵省略並附 warnings）
    stats / two_var        X, Y, model(LIN|LN|EXP|PWR)
    stats / predict        model, A, B, X 或 Y（恰給其一）
    bond / price           SDT, RDT([y,m,d]), CPN, RV, basis(ACT|360), freq(1|2), YLD
    bond / yield           同上，但給 PRI（不給 YLD）
    depr / year            method(SL|SYD|DB|DBX), CST, SAL, LIF, M01, DB, YR
    depr / schedule        同上，不需 YR（LIF <= 10000）；M01 預設 1、DB 預設 200
    date / solve           DT1, DT2([y,m,d]), DBD（恰留一格空白）, basis(ACT|360)
    business / profit      CST, SEL, MAR, MU
    business / breakeven   FC, VC, P, PFT, Q（恰留一格空白）
    business / pct_change  OLD, NEW, PCT, PD（恰留一格空白）
    business / tax         AMOUNT, RATE, MODE(exclusive|inclusive)
    calc / eval            EXPR, ANS（預設 0）, MEM（如 {"M3": 1.0}）；
                           settings.mode（AOS|CHAIN）、settings.angle（DEG|RAD）
                           函式 sin cos tan asin acos atan log cbrt，常數 pi（或 π）、e
    units / convert        VALUE, FROM, TO（單位 id，如 km、degC、psi；跨類別報錯）
    units / list           （無輸入）回傳 categories（含各類別的單位 id、中英文名）
    base / convert         TEXT(字串), FROM(2|8|10|16), WIDTH(8|16|32|64), SIGNED(bool)
                           回傳 BIN、OCT、DEC、HEX 四個字串；display 即字串本身（無千分位）
    base / bitwise         OP(AND|OR|XOR|NOT|SHL|SHR|SAR), A, B（皆為 FROM 進位的字串；
                           NOT 不需 B；移位的 B 為位移量 0..WIDTH）, FROM, WIDTH, SIGNED
    dist / normal          FUNC(pdf|cdf|inv), MU, SIGMA, X（pdf、cdf）或 PROB（inv）
    dist / t               FUNC(pdf|cdf|inv), DF（可非整數，0 < DF <= 1e5）, X 或 PROB
    dist / chi2            FUNC(pdf|cdf|inv), DF（可非整數，0 < DF <= 1e5）, X 或 PROB
    dist / binom           FUNC(pmf|cdf), N（整數 0..1e5）, P（0..1）, K（整數 0..N）
    dist / poisson         FUNC(pmf|cdf), LAMBDA（0 < LAMBDA <= 1e5）, K（整數 >= 0）
                           回傳 value（pdf／pmf、左尾 P(X<=x)，或 inv 的 x）；
                           cdf 另含 right（右尾 P(X>x)）；inv 另含 right（P(X>x)=PROB 的 x）；
                           常態與 t 另含 two（cdf：雙尾機率；inv：雙尾上側臨界值）；
                           卡方 inv 含 right；0 < PROB < 1

留一格空白規則（leave-one-blank）：
    tvm、date、breakeven、pct_change：可求解欄位中恰有一格 null 才求解，否則報錯。
    profit：可求解欄位為 CST、SEL、MAR、MU。
        - 恰一格空白 -> 該格為未知數；
        - 兩格空白且「一格屬 {CST, SEL}、另一格屬 {MAR, MU}」-> 求 CST／SEL 那一格
          （例：CST=80、MU=25、SEL 與 MAR 空白 -> 求 SEL）；
        - 兩格空白且恰為 {MAR, MU}（CST、SEL 已填）-> 同時算出 MAR 與 MU；
        - 其餘（0 格、{CST, SEL} 同空、3 格以上）一律報錯。
    pct_change：PD 與另一格同時空白時，PD 視為預設 1，求另一格。
"""
import json

from engine import (amort, base, bond, business, calc, cashflow, dates, depr,
                    describe, dist, iconv, stats, tvm, units)
from engine.fmt import format_number
from engine.result import _all_finite, err, is_finite

_MAX_ABS = 1e300       # 超過視為數值過大，避免後續運算溢位
_MAX_PERIODS = 10000   # 攤還／折舊表的期數上限，防止 UI 卡死


class _InputError(Exception):
    """輸入驗證失敗（內部使用），帶中文訊息與欄位名。"""

    def __init__(self, message, field=None):
        super().__init__(message)  # MicroPython 相容：不可寫 Exception.__init__
        self.message = message
        self.field = field


# ---------------------------------------------------------------- 驗證工具

def _is_num(v):
    """有限的 int／float（bool 不算），且絕對值不超過上限。"""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return False
    return is_finite(v) and abs(v) <= _MAX_ABS


def _num(inp, key, required=False):
    """取數值欄位；空白回 None（required 時報錯）。"""
    v = inp.get(key)
    if v is None:
        if required:
            raise _InputError("請輸入 %s" % key, key)
        return None
    if not _is_num(v):
        raise _InputError("%s 必須是有限數字" % key, key)
    return v


def _int(inp, key, required=False):
    """取整數欄位（接受整數值的 float）。"""
    v = _num(inp, key, required)
    if v is not None and v != int(v):
        raise _InputError("%s 必須是整數" % key, key)
    return None if v is None else int(v)


def _str(inp, key, allowed=None, required=False):
    """取字串欄位；allowed 為合法值 tuple。"""
    v = inp.get(key)
    if v is None:
        if required:
            raise _InputError("請輸入 %s" % key, key)
        return None
    if not isinstance(v, str) or (allowed is not None and v not in allowed):
        raise _InputError("%s 不合法" % key, key)
    return v


def _bool(inp, key):
    """取布林欄位（BGN）；空白視為 False，非 bool 報錯。"""
    v = inp.get(key)
    if v is None:
        return False
    if not isinstance(v, bool):
        raise _InputError("%s 必須是 true 或 false" % key, key)
    return v


def _date(inp, key):
    """取日期 [y, m, d]（三個整數）；空白回 None。"""
    v = inp.get(key)
    if v is None:
        return None
    if (not isinstance(v, (list, tuple)) or len(v) != 3
            or any(isinstance(x, bool) or not isinstance(x, int) for x in v)):
        raise _InputError("%s 必須是 [年, 月, 日] 三個整數" % key, key)
    return list(v)


def _num_list(inp, key, required=True):
    """取數值 list（每個元素皆為有限數）。"""
    v = inp.get(key)
    if v is None:
        if required:
            raise _InputError("請輸入 %s" % key, key)
        return None
    if not isinstance(v, (list, tuple)) or any(not _is_num(x) for x in v):
        raise _InputError("%s 必須是有限數字的清單" % key, key)
    return list(v)


def _flows(inp):
    """取現金流群組 [[金額, 次數], ...]。"""
    v = inp.get("flows")
    if v is None:
        return []
    if not isinstance(v, (list, tuple)):
        raise _InputError("flows 必須是 [[金額, 次數], ...]", "flows")
    out = []
    for item in v:
        if (not isinstance(item, (list, tuple)) or len(item) != 2
                or not _is_num(item[0]) or not _is_num(item[1])):
            raise _InputError("flows 每筆須為 [金額, 次數]（有限數字）",
                              "flows")
        out.append([item[0], item[1]])
    return out


def _blank_error(blanks):
    """留一格空白的錯誤。"""
    return _InputError("請只留一格空白（目前空白：%s）"
                       % ("、".join(blanks) if blanks else "無"), None)


def _one_blank(values, names):
    """names 中恰一格為 None 則回傳該欄位名，否則擲 _InputError。"""
    blanks = [n for n in names if values.get(n) is None]
    if len(blanks) != 1:
        raise _blank_error(blanks)
    return blanks[0]


# ---------------------------------------------------------------- 路由處理

def _tvm_inputs(inp):
    """TVM 與 AMORT 共用的輸入組裝與驗證。"""
    out = {}
    for k in ("N", "IY", "PV", "PMT", "FV", "PY", "CY"):
        out[k] = _num(inp, k)
    out["BGN"] = _bool(inp, "BGN")
    return out


def _limit_n(d):
    """攤還期數上限檢查。"""
    if d["N"] is not None and d["N"] > _MAX_PERIODS:
        raise _InputError("N 不可超過 %d" % _MAX_PERIODS, "N")


def _r_tvm(inp, st):
    d = _tvm_inputs(inp)
    unknown = _one_blank(d, ("N", "IY", "PV", "PMT", "FV"))
    return tvm.solve(d, unknown)


def _r_amort_range(inp, st):
    d = _tvm_inputs(inp)
    _limit_n(d)
    p1 = _int(inp, "P1", True)
    p2 = _int(inp, "P2", True)
    return amort.amort(d, p1, p2)


def _r_amort_schedule(inp, st):
    d = _tvm_inputs(inp)
    _limit_n(d)
    return amort.schedule(d)


def _cf_route(fn):
    """建立現金流路由：驗證後把 inputs 字典交給 cashflow 函式。"""
    def handler(inp, st):
        return fn({"CF0": _num(inp, "CF0", True), "flows": _flows(inp),
                   "I": _num(inp, "I"), "RI": _num(inp, "RI")})
    return handler


def _r_to_eff(inp, st):
    return iconv.nom_to_eff(_num(inp, "NOM", True), _num(inp, "CY", True))


def _r_to_nom(inp, st):
    return iconv.eff_to_nom(_num(inp, "EFF", True), _num(inp, "CY", True))


def _r_one_var(inp, st):
    return stats.one_var(_num_list(inp, "X"), _num_list(inp, "F", False))


def _r_describe(inp, st):
    return describe.describe(_num_list(inp, "X"), _num_list(inp, "F", False))


def _r_two_var(inp, st):
    model = _str(inp, "model", stats.MODELS, True)
    return stats.two_var(_num_list(inp, "X"), _num_list(inp, "Y"), model)


def _r_predict(inp, st):
    model = _str(inp, "model", stats.MODELS, True)
    return stats.predict(model, _num(inp, "A", True), _num(inp, "B", True),
                         _num(inp, "X"), _num(inp, "Y"))


def _bond_inputs(inp):
    return {"SDT": _date(inp, "SDT"), "RDT": _date(inp, "RDT"),
            "CPN": _num(inp, "CPN"), "RV": _num(inp, "RV"),
            "basis": _str(inp, "basis", ("ACT", "360")),
            "freq": _int(inp, "freq"),
            "YLD": _num(inp, "YLD"), "PRI": _num(inp, "PRI")}


def _r_bond_price(inp, st):
    return bond.price(_bond_inputs(inp))


def _r_bond_yield(inp, st):
    return bond.yield_(_bond_inputs(inp))


def _depr_args(inp):
    """折舊共用參數：(method, cst, sal, lif, m01, db_pct)。"""
    m01 = _num(inp, "M01")
    db = _num(inp, "DB")
    lif = _num(inp, "LIF")
    if lif is not None and lif > _MAX_PERIODS:
        raise _InputError("LIF 不可超過 %d" % _MAX_PERIODS, "LIF")
    return (_str(inp, "method", depr.METHODS, True), _num(inp, "CST"),
            _num(inp, "SAL"), lif, 1 if m01 is None else m01,
            200 if db is None else db)


def _r_depr_year(inp, st):
    args = _depr_args(inp)
    return depr.year(*args, yr=_int(inp, "YR", True))


def _r_depr_schedule(inp, st):
    return depr.schedule(*_depr_args(inp))


def _r_date(inp, st):
    d1, d2 = _date(inp, "DT1"), _date(inp, "DT2")
    dbd = _num(inp, "DBD")
    basis = _str(inp, "basis", ("ACT", "360"), True)
    unknown = _one_blank({"DT1": d1, "DT2": d2, "DBD": dbd},
                         ("DBD", "DT1", "DT2"))
    return dates.date_sheet(d1, d2, dbd, basis, unknown)


def _r_profit(inp, st):
    names = ("CST", "SEL", "MAR", "MU")
    v = {k: _num(inp, k) for k in names}
    blanks = [k for k in names if v[k] is None]
    base = [k for k in blanks if k in ("CST", "SEL")]
    rate = [k for k in blanks if k in ("MAR", "MU")]
    if len(blanks) == 1:
        unknown = blanks[0]
    elif len(base) == 1 and len(rate) == 1:
        unknown = base[0]
    elif not base and len(rate) == 2:
        unknown = "MAR"
    else:
        raise _blank_error(blanks)
    res = business.profit(v["CST"], v["SEL"], v["MAR"], v["MU"], unknown)
    if res.get("ok") and unknown in ("MAR", "MU"):
        # CST、SEL 皆已知時，若使用者另給的比率與算出值不符，不可默默覆蓋
        other = "MU" if unknown == "MAR" else "MAR"
        if v[other] is not None:
            got = res["values"][other]
            if abs(got - v[other]) > 1e-9 * max(1.0, abs(got)):
                return err("MAR 與 MU 不一致", other)
    return res


def _r_breakeven(inp, st):
    names = ("FC", "VC", "P", "PFT", "Q")
    v = {k: _num(inp, k) for k in names}
    return business.breakeven(v["FC"], v["VC"], v["P"], v["PFT"], v["Q"],
                              _one_blank(v, names))


def _r_pct(inp, st):
    names = ("OLD", "NEW", "PCT", "PD")
    v = {k: _num(inp, k) for k in names}
    blanks = [k for k in names if v[k] is None]
    if len(blanks) == 2 and "PD" in blanks:
        unknown = blanks[0] if blanks[1] == "PD" else blanks[1]
    else:
        unknown = _one_blank(v, names)
    return business.pct_change(v["OLD"], v["NEW"], v["PCT"], v["PD"],
                               unknown)


def _r_tax(inp, st):
    return business.tax(_num(inp, "AMOUNT", True), _num(inp, "RATE", True),
                        _str(inp, "MODE", ("exclusive", "inclusive"), True))


def _r_calc(inp, st):
    expr = inp.get("EXPR")
    if not isinstance(expr, str):
        raise _InputError("EXPR 必須是字串", "EXPR")
    ans = _num(inp, "ANS")
    mem = inp.get("MEM")
    if mem is not None:
        if not isinstance(mem, dict) or any(
                not isinstance(k, str) or not _is_num(x)
                for k, x in mem.items()):
            raise _InputError("MEM 必須是 {名稱: 有限數字}", "MEM")
    return calc.evaluate(expr, st["mode"], 0.0 if ans is None else ans, mem,
                         st["angle"])


def _r_units_convert(inp, st):
    value = _num(inp, "VALUE", required=True)
    frm = _str(inp, "FROM", required=True)
    to = _str(inp, "TO", required=True)
    return units.convert(value, frm, to)


def _r_units_list(inp, st):
    return units.list_units()


def _text(inp, key, required=True):
    """取字串欄位（進位文字）；空字串視為空白。"""
    v = inp.get(key)
    if v is None or v == "":
        if required:
            raise _InputError("請輸入 %s" % key, key)
        return None
    if not isinstance(v, str):
        raise _InputError("%s 必須是文字" % key, key)
    return v


def _base_params(inp):
    """base 路由共用：FROM、WIDTH、SIGNED。"""
    return (_int(inp, "FROM", required=True), _int(inp, "WIDTH", required=True),
            _bool(inp, "SIGNED"))


def _r_base_convert(inp, st):
    text = _text(inp, "TEXT")
    frm, width, signed = _base_params(inp)
    return base.convert_base(text, frm, width, signed)


def _parse_operand(inp, key, frm, width, signed):
    """把 A／B 字串依 FROM 解析為整數；錯誤標上欄位名。"""
    r = base.parse_int(_text(inp, key), frm, width, signed)
    if not r["ok"]:
        raise _InputError("%s：%s" % (key, r["error"]),
                          key if r["field"] in (None, "TEXT") else r["field"])
    return r["values"]["value"]


def _r_base_bitwise(inp, st):
    op = _str(inp, "OP", required=True)
    frm, width, signed = _base_params(inp)
    a = _parse_operand(inp, "A", frm, width, signed)
    b = 0 if op == "NOT" else _parse_operand(inp, "B", frm, width, signed)
    return base.bitwise(op, a, b, width, signed)


def _r_normal(inp, st):
    return dist.normal(_str(inp, "FUNC", ("pdf", "cdf", "inv"), True),
                       _num(inp, "MU", True), _num(inp, "SIGMA", True),
                       _num(inp, "X"), _num(inp, "PROB"))


def _r_t(inp, st):
    return dist.t_dist(_str(inp, "FUNC", ("pdf", "cdf", "inv"), True),
                       _num(inp, "DF", True), _num(inp, "X"),
                       _num(inp, "PROB"))


def _r_chi2(inp, st):
    return dist.chi2(_str(inp, "FUNC", ("pdf", "cdf", "inv"), True),
                     _num(inp, "DF", True), _num(inp, "X"), _num(inp, "PROB"))


def _r_binom(inp, st):
    return dist.binom(_str(inp, "FUNC", ("pmf", "cdf"), True),
                      _int(inp, "N", True), _num(inp, "P", True),
                      _int(inp, "K", True))


def _r_poisson(inp, st):
    return dist.poisson(_str(inp, "FUNC", ("pmf", "cdf"), True),
                        _num(inp, "LAMBDA", True), _int(inp, "K", True))


ROUTES = {
    ("tvm", "solve"): _r_tvm,
    ("amort", "range"): _r_amort_range,
    ("amort", "schedule"): _r_amort_schedule,
    ("cashflow", "npv"): _cf_route(cashflow.npv),
    ("cashflow", "irr"): _cf_route(cashflow.irr),
    ("cashflow", "nfv"): _cf_route(cashflow.nfv),
    ("cashflow", "mirr"): _cf_route(cashflow.mirr),
    ("cashflow", "pb"): _cf_route(cashflow.payback),
    ("cashflow", "dpb"): _cf_route(cashflow.dpayback),
    ("iconv", "to_eff"): _r_to_eff,
    ("iconv", "to_nom"): _r_to_nom,
    ("stats", "one_var"): _r_one_var,
    ("stats", "describe"): _r_describe,
    ("stats", "two_var"): _r_two_var,
    ("stats", "predict"): _r_predict,
    ("bond", "price"): _r_bond_price,
    ("bond", "yield"): _r_bond_yield,
    ("depr", "year"): _r_depr_year,
    ("depr", "schedule"): _r_depr_schedule,
    ("business", "profit"): _r_profit,
    ("business", "breakeven"): _r_breakeven,
    ("business", "pct_change"): _r_pct,
    ("business", "tax"): _r_tax,
    ("date", "solve"): _r_date,
    ("calc", "eval"): _r_calc,
    ("units", "convert"): _r_units_convert,
    ("units", "list"): _r_units_list,
    ("base", "convert"): _r_base_convert,
    ("base", "bitwise"): _r_base_bitwise,
    ("dist", "normal"): _r_normal,
    ("dist", "t"): _r_t,
    ("dist", "chi2"): _r_chi2,
    ("dist", "binom"): _r_binom,
    ("dist", "poisson"): _r_poisson,
}

# 值為字串、display 直接等於字串本身的路由（不經 format_number 加千分位）
_STRING_DISPLAY = (("base", "convert"), ("base", "bitwise"))


# ---------------------------------------------------------------- 設定與顯示

def _settings(raw):
    """驗證 settings，回傳 {"decimals", "sep", "mode", "angle"}。"""
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise _InputError("settings 必須是物件", "settings")
    dec = raw["decimals"] if "decimals" in raw else 2
    if dec is not None and (isinstance(dec, bool) or not isinstance(dec, int)
                            or not 0 <= dec <= 9):
        raise _InputError("decimals 必須是 0～9 的整數或 null", "decimals")
    sep = raw.get("sep", "us")
    if not isinstance(sep, str) or sep not in ("us", "eu"):
        raise _InputError("sep 必須是 us 或 eu", "sep")
    mode = raw.get("mode", "AOS")
    if not isinstance(mode, str) or mode not in ("AOS", "CHAIN"):
        raise _InputError("mode 必須是 AOS 或 CHAIN", "mode")
    angle = raw.get("angle", "DEG")
    if not isinstance(angle, str) or angle not in ("DEG", "RAD"):
        raise _InputError("angle 必須是 DEG 或 RAD", "angle")
    return {"decimals": dec, "sep": sep, "mode": mode, "angle": angle}


def _is_scalar(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _fmt_scalar(v, st):
    """格式化單一數值；整數固定 0 位小數。"""
    dec = 0 if isinstance(v, int) else st["decimals"]
    return format_number(v, dec, st["sep"])


def _display(values, st):
    """產生 display：純量與 rows 的格式化字串。"""
    out = {}
    for key, v in values.items():
        if _is_scalar(v):
            out[key] = _fmt_scalar(v, st)
        elif key == "modes" and isinstance(v, list):
            out[key] = [_fmt_scalar(c, st) for c in v]
        elif key == "rows" and isinstance(v, list):
            out[key] = [[_fmt_scalar(c, st) if _is_scalar(c) else str(c)
                         for c in row] for row in v]
    return out


# ---------------------------------------------------------------- 入口

def _handle(request_json):
    """解析、驗證、路由，回傳結果 dict。"""
    try:
        req = json.loads(request_json)
    except (ValueError, TypeError, RuntimeError):
        return err("請求不是合法的 JSON", None)
    if not isinstance(req, dict):
        return err("請求必須是 JSON 物件", None)
    sheet, action = req.get("sheet"), req.get("action")
    if not isinstance(sheet, str) or not isinstance(action, str):
        return err("缺少 sheet 或 action", None)
    handler = ROUTES.get((sheet, action))
    if handler is None:
        return err("未知的功能：%s / %s" % (sheet, action), None)
    inputs = req.get("inputs")
    if inputs is None:
        inputs = {}
    if not isinstance(inputs, dict):
        return err("inputs 必須是物件", "inputs")
    try:
        st = _settings(req.get("settings"))
        result = handler(inputs, st)
    except _InputError as e:
        return err(e.message, e.field)
    if result.get("ok"):
        result = dict(result)
        if (sheet, action) in _STRING_DISPLAY:
            result["display"] = dict(result["values"])
        else:
            result["display"] = _display(result.get("values") or {}, st)
    return result


def call(request_json):
    """統一入口：JSON 字串進、JSON 字串出，永不擲例外。"""
    try:
        result = _handle(request_json)
    except Exception as e:  # 任何未預期例外都包成 err
        result = err("內部錯誤：" + type(e).__name__, None)
    try:
        if not _all_finite(result):  # MicroPython 會把 inf／nan 寫成非法 JSON
            result = err("計算結果超出範圍（溢位）", None)
        return json.dumps(result)
    except Exception as e:
        return json.dumps(err("內部錯誤：" + type(e).__name__, None))
