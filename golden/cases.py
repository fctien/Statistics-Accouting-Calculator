"""golden 案例定義（對照 Excel 公式）。

每筆：{"id", "sheet", "call"(bridge 請求), "excel": {"formula": ...},
       "expect_key", "tol"}。公式以字面數字寫成，產生器 tools/make_golden_excel.py
在獨立的 Excel 實例中求值。百分比輸出（IY、IRR、MIRR、EFF、NOM、YLD）為百分數。
amort 案例的 PMT 由 excel["pmt_formula"] 在同一次 Excel 執行中算出後填入 call，
公式中的 {PMT} 會被代換為該數值（字面全精度）。
"""

DEFAULT_TOL = 1e-9

_XS = [1, 2, 3, 4, 5, 6]
_YS = [2.1, 3.9, 6.2, 7.8, 10.1, 12.2]


def _arr(v):
    """Python list 轉 Excel 陣列常數字串，例如 {1,2,3}。"""
    return "{" + ",".join(repr(x) for x in v) + "}"


def _case(cid, sheet, action, inputs, formula, key, tol=DEFAULT_TOL, **extra):
    """組一筆案例。"""
    excel = {"formula": formula}
    excel.update(extra)
    return {"id": cid, "sheet": sheet,
            "call": {"sheet": sheet, "action": action, "inputs": inputs,
                     "settings": {}},
            "excel": excel, "expect_key": key, "tol": tol}


def _tvm(**kw):
    """TVM 輸入（未指定欄位為 None；PY=CY=12、END）。"""
    d = {"N": None, "IY": None, "PV": None, "PMT": None, "FV": None,
         "PY": 12, "CY": 12, "BGN": False}
    d.update(kw)
    return d


def _cf(cf0, flows, i, ri=None):
    return {"CF0": cf0, "flows": flows, "I": i, "RI": ri}


def _stats(model):
    """model 為 None 代表單變數統計（Y 為 None）。"""
    return {"X": list(_XS), "Y": None if model is None else list(_YS),
            "model": model}


def _bond(**kw):
    d = {"SDT": [2026, 6, 12], "RDT": [2036, 1, 1], "CPN": 7.0, "RV": 100.0,
         "basis": "ACT", "freq": 2, "YLD": None, "PRI": None}
    d.update(kw)
    return d


def _depr(method, yr, db=200):
    return {"method": method, "CST": 10000, "SAL": 1000, "LIF": 5, "M01": 1,
            "DB": db, "YR": yr}


def _date(d1, d2, basis, dbd=None):
    return {"DT1": d1, "DT2": d2, "DBD": dbd, "basis": basis}


_AM = _tvm(N=360, IY=6, PV=300000, FV=0, PMT=None)  # PMT 由 Excel 填入
_PMT = "=PMT(0.06/12,360,300000,0,0)"
_B = "DATE(2026,6,12),DATE(2036,1,1)"
_CF4 = [[3000, 1], [4200, 1], [6800, 1], [-1500, 1]]

CASES = [
    # ---- tvm ----
    _case("tvm_pmt_mortgage", "tvm", "solve",
          _tvm(N=360, IY=6, PV=300000, FV=0),
          "=PMT(0.06/12,360,300000,0,0)", "PMT"),
    _case("tvm_fv_annuity_due", "tvm", "solve",
          _tvm(N=60, IY=3, PV=0, PMT=-500, BGN=True),
          "=FV(0.03/12,60,-500,0,1)", "FV"),
    _case("tvm_iy_loan", "tvm", "solve",
          _tvm(N=48, PV=20000, PMT=-480, FV=0),
          "=RATE(48,-480,20000,0,0)*12*100", "IY"),
    _case("tvm_n_lump", "tvm", "solve",
          _tvm(IY=5, PV=-1000, PMT=0, FV=2000, PY=1, CY=1),
          "=NPER(0.05,0,-1000,2000)", "N"),
    _case("tvm_pv_py12_cy4", "tvm", "solve",
          _tvm(N=120, IY=8, PMT=-200, FV=0, PY=12, CY=4),
          "=PV((1+0.08/4)^(4/12)-1,120,-200,0,0)", "PV"),
    # ---- amort（PMT 取自同次 Excel 計算；BAL=-FV(rate,P2,PMT,PV)，與 PV 同號）----
    _case("amort_int_y1", "amort", "range", dict(_AM, P1=1, P2=12),
          "=CUMIPMT(0.005,360,300000,1,12,0)", "INT", pmt_formula=_PMT),
    _case("amort_prn_y1", "amort", "range", dict(_AM, P1=1, P2=12),
          "=CUMPRINC(0.005,360,300000,1,12,0)", "PRN", pmt_formula=_PMT),
    _case("amort_bal_y1", "amort", "range", dict(_AM, P1=1, P2=12),
          "=-FV(0.005,12,{PMT},300000)", "BAL", pmt_formula=_PMT),
    _case("amort_int_y2", "amort", "range", dict(_AM, P1=13, P2=24),
          "=CUMIPMT(0.005,360,300000,13,24,0)", "INT", pmt_formula=_PMT),
    _case("amort_bal_y2", "amort", "range", dict(_AM, P1=13, P2=24),
          "=-FV(0.005,24,{PMT},300000)", "BAL", pmt_formula=_PMT),
    # ---- cashflow ----
    _case("cf_npv", "cashflow", "npv", _cf(-10000, _CF4, 10),
          "=-10000+NPV(0.1,3000,4200,6800,-1500)", "NPV"),
    _case("cf_irr", "cashflow", "irr", _cf(-10000, _CF4, 10),
          "=IRR({-10000,3000,4200,6800,-1500})*100", "IRR"),
    _case("cf_mirr", "cashflow", "mirr", _cf(-10000, _CF4, 10, 12),
          "=MIRR({-10000,3000,4200,6800,-1500},0.1,0.12)*100", "MIRR"),
    _case("cf_nfv", "cashflow", "nfv", _cf(-10000, _CF4, 10),
          "=(-10000+NPV(0.1,3000,4200,6800,-1500))*(1+0.1)^4", "NFV"),
    _case("cf_irr_group", "cashflow", "irr", _cf(-7000, [[3000, 3]], 10),
          "=IRR({-7000,3000,3000,3000})*100", "IRR"),
    _case("cf_npv_group", "cashflow", "npv",
          _cf(-5000, [[1000, 2], [2500, 3]], 8),
          "=-5000+NPV(0.08,1000,1000,2500,2500,2500)", "NPV"),
    # ---- iconv ----
    _case("iconv_eff_12_12", "iconv", "to_eff",
          {"NOM": 12, "EFF": None, "CY": 12}, "=EFFECT(0.12,12)*100", "EFF"),
    _case("iconv_nom_10_4", "iconv", "to_nom",
          {"NOM": None, "EFF": 10, "CY": 4}, "=NOMINAL(0.1,4)*100", "NOM"),
    _case("iconv_eff_18_365", "iconv", "to_eff",
          {"NOM": 18, "EFF": None, "CY": 365}, "=EFFECT(0.18,365)*100", "EFF"),
    # ---- stats ----
    _case("stats_mean_x", "stats", "one_var", _stats(None),
          "=AVERAGE(" + _arr(_XS) + ")", "mean_x"),
    _case("stats_sx", "stats", "one_var", _stats(None),
          "=STDEV.S(" + _arr(_XS) + ")", "sx"),
    _case("stats_sigma_x", "stats", "one_var", _stats(None),
          "=STDEV.P(" + _arr(_XS) + ")", "sigma_x"),
    _case("stats_lin_a", "stats", "two_var", _stats("LIN"),
          "=INTERCEPT(%s,%s)" % (_arr(_YS), _arr(_XS)), "a"),
    _case("stats_lin_b", "stats", "two_var", _stats("LIN"),
          "=SLOPE(%s,%s)" % (_arr(_YS), _arr(_XS)), "b"),
    _case("stats_lin_r", "stats", "two_var", _stats("LIN"),
          "=CORREL(%s,%s)" % (_arr(_XS), _arr(_YS)), "r"),
    _case("stats_ln_a", "stats", "two_var", _stats("LN"),
          "=INTERCEPT(%s,LN(%s))" % (_arr(_YS), _arr(_XS)), "a"),
    _case("stats_ln_b", "stats", "two_var", _stats("LN"),
          "=SLOPE(%s,LN(%s))" % (_arr(_YS), _arr(_XS)), "b"),
    _case("stats_ln_r", "stats", "two_var", _stats("LN"),
          "=CORREL(LN(%s),%s)" % (_arr(_XS), _arr(_YS)), "r"),
    _case("stats_exp_a", "stats", "two_var", _stats("EXP"),
          "=EXP(INTERCEPT(LN(%s),%s))" % (_arr(_YS), _arr(_XS)), "a"),
    _case("stats_exp_b", "stats", "two_var", _stats("EXP"),
          "=EXP(SLOPE(LN(%s),%s))" % (_arr(_YS), _arr(_XS)), "b"),
    _case("stats_exp_r", "stats", "two_var", _stats("EXP"),
          "=CORREL(%s,LN(%s))" % (_arr(_XS), _arr(_YS)), "r"),
    _case("stats_pwr_a", "stats", "two_var", _stats("PWR"),
          "=EXP(INTERCEPT(LN(%s),LN(%s)))" % (_arr(_YS), _arr(_XS)), "a"),
    _case("stats_pwr_b", "stats", "two_var", _stats("PWR"),
          "=SLOPE(LN(%s),LN(%s))" % (_arr(_YS), _arr(_XS)), "b"),
    _case("stats_pwr_r", "stats", "two_var", _stats("PWR"),
          "=CORREL(LN(%s),LN(%s))" % (_arr(_XS), _arr(_YS)), "r"),
    # ---- bond（Excel basis 1=實際/實際、0=30/360 US）----
    _case("bond_pri_act", "bond", "price", _bond(YLD=8.0),
          "=PRICE(%s,0.07,0.08,100,2,1)" % _B, "PRI"),
    _case("bond_ai_act", "bond", "price", _bond(YLD=8.0),
          "=COUPDAYBS(%s,2,1)/COUPDAYS(%s,2,1)*0.07/2*100" % (_B, _B), "AI"),
    _case("bond_yld_360", "bond", "yield", _bond(basis="360", PRI=95.0),
          "=YIELD(%s,0.07,95,100,2,0)*100" % _B, "YLD"),
    _case("bond_pri_360", "bond", "price", _bond(basis="360", YLD=8.0),
          "=PRICE(%s,0.07,0.08,100,2,0)" % _B, "PRI"),
    _case("bond_ai_360", "bond", "price", _bond(basis="360", YLD=8.0),
          "=COUPDAYBS(%s,2,0)/COUPDAYS(%s,2,0)*0.07/2*100" % (_B, _B), "AI"),
    _case("bond_pri_annual", "bond", "price", _bond(YLD=6.5, freq=1),
          "=PRICE(%s,0.07,0.065,100,1,1)" % _B, "PRI"),
    # ---- depr ----
    _case("depr_sl", "depr", "year", _depr("SL", 1),
          "=SLN(10000,1000,5)", "DEP"),
    _case("depr_syd_y3", "depr", "year", _depr("SYD", 3),
          "=SYD(10000,1000,5,3)", "DEP"),
    _case("depr_db200_y2", "depr", "year", _depr("DB", 2),
          "=DDB(10000,1000,5,2,2)", "DEP"),
    _case("depr_db150_y3", "depr", "year", _depr("DB", 3, 150),
          "=DDB(10000,1000,5,3,1.5)", "DEP"),
    _case("depr_dbx200_y4", "depr", "year", _depr("DBX", 4),
          "=VDB(10000,1000,5,3,4,2,FALSE)", "DEP"),
    _case("depr_dbx200_y5", "depr", "year", _depr("DBX", 5),
          "=VDB(10000,1000,5,4,5,2,FALSE)", "DEP"),
    # ---- date ----
    _case("date_act_jan31_mar1", "date", "solve",
          _date([2026, 1, 31], [2026, 3, 1], "ACT"),
          "=DAYS(DATE(2026,3,1),DATE(2026,1,31))", "DBD"),
    _case("date_360_jan31_feb28", "date", "solve",
          _date([2026, 1, 31], [2026, 2, 28], "360"),
          "=DAYS360(DATE(2026,1,31),DATE(2026,2,28),FALSE)", "DBD"),
    _case("date_act_leap_2028", "date", "solve",
          _date([2028, 2, 1], [2028, 3, 1], "ACT"),
          "=DAYS(DATE(2028,3,1),DATE(2028,2,1))", "DBD"),
    _case("date_act_across_leap_day", "date", "solve",
          _date([2027, 12, 31], [2028, 3, 1], "ACT"),
          "=DAYS(DATE(2028,3,1),DATE(2027,12,31))", "DBD"),
    _case("date_360_across_leap", "date", "solve",
          _date([2027, 12, 31], [2028, 3, 1], "360"),
          "=DAYS360(DATE(2027,12,31),DATE(2028,3,1),FALSE)", "DBD"),
]
