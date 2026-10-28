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


def _calc(cid, expr, formula, angle="DEG"):
    """計算機案例：bridge calc/eval，settings.angle 指定角度單位。"""
    return {"id": cid, "sheet": "calc",
            "call": {"sheet": "calc", "action": "eval",
                     "inputs": {"EXPR": expr},
                     "settings": {"angle": angle}},
            "excel": {"formula": formula}, "expect_key": "value",
            "tol": DEFAULT_TOL}


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
    # ---- calc（科學函式；角度預設 DEG，Excel 以 RADIANS／DEGREES 對應）----
    _calc("calc_sin_30", "sin(30)", "=SIN(RADIANS(30))"),
    _calc("calc_cos_60", "cos(60)", "=COS(RADIANS(60))"),
    _calc("calc_tan_45", "tan(45)", "=TAN(RADIANS(45))"),
    _calc("calc_asin_half", "asin(0.5)", "=DEGREES(ASIN(0.5))"),
    _calc("calc_acos_half", "acos(0.5)", "=DEGREES(ACOS(0.5))"),
    _calc("calc_atan_1", "atan(1)", "=DEGREES(ATAN(1))"),
    _calc("calc_sin_1_rad", "sin(1)", "=SIN(1)", "RAD"),
    _calc("calc_log_1000", "log(1000)", "=LOG10(1000)"),
    _calc("calc_ln_10", "ln(10)", "=LN(10)"),
    _calc("calc_cbrt_neg27", "cbrt(-27)", "=-POWER(27,1/3)"),
    _calc("calc_pi_times_2", "pi*2", "=PI()*2"),
    _calc("calc_pi_symbol", "π*2", "=PI()*2"),
    _calc("calc_exp_1", "e", "=EXP(1)"),
    _calc("calc_combo", "sin(30)+log(100)*2",
          "=SIN(RADIANS(30))+LOG10(100)*2"),
    _calc("calc_atan_rad", "atan(1)", "=ATAN(1)", "RAD"),
]


def _unit(cid, value, frm, to, formula):
    """單位換算案例：bridge units/convert，輸出鍵 value。
    id 含 units_def_ 者為「定義值」案例：出處標為定義值而非 Excel。"""
    extra = {"defined": True} if "units_def_" in cid else {}
    return _case(cid, "units", "convert",
                 {"VALUE": value, "FROM": frm, "TO": to}, formula, "value",
                 tol=1e-9, **extra)


# ---- units（Excel CONVERT；引擎單位 id 與 Excel 代碼不同者見公式）----
# 「定義值」案例：Excel CONVERT 不支援（或定義不同）的單位，公式以
# 國際／法定定義值字面寫成（例：台斤 0.6 kg），仍由 Excel 求算術值。
CASES += [
    # 長度
    _unit("units_len_mi_km", 1, "mi", "km", '=CONVERT(1,"mi","km")'),
    _unit("units_len_nmi_m", 3, "nmi", "m", '=CONVERT(3,"Nmi","m")'),
    _unit("units_len_in_mm", 10, "in", "mm", '=CONVERT(10,"in","mm")'),
    _unit("units_len_um_m", 250, "um", "m", '=CONVERT(250,"um","m")'),
    # 質量
    _unit("units_mass_lb_kg", 150, "lb", "kg", '=CONVERT(150,"lbm","kg")'),
    _unit("units_mass_oz_g", 7, "oz", "g", '=CONVERT(7,"ozm","g")'),
    _unit("units_mass_kg_lb", 1, "kg", "lb", '=CONVERT(1,"kg","lbm")'),
    _unit("units_mass_mg_g", 2500, "mg", "g", '=CONVERT(2500,"mg","g")'),
    _unit("units_def_mass_catty_kg", 3, "catty", "kg", "=3*0.6"),
    _unit("units_def_mass_tael_g", 2, "tael", "g", "=2*37.5"),
    _unit("units_def_mass_t_kg", 1.5, "t", "kg", "=1.5*1000"),
    # 溫度
    _unit("units_temp_c_f", 100, "degC", "degF", '=CONVERT(100,"C","F")'),
    _unit("units_temp_f_c_m40", -40, "degF", "degC", '=CONVERT(-40,"F","C")'),
    _unit("units_temp_k_c", 0, "K", "degC", '=CONVERT(0,"K","C")'),
    _unit("units_temp_f_k", 98.6, "degF", "K", '=CONVERT(98.6,"F","K")'),
    # 壓力
    _unit("units_pres_atm_psi", 1, "atm", "psi", '=CONVERT(1,"atm","psi")'),
    _unit("units_pres_mpa_pa", 2.5, "MPa", "Pa", '=CONVERT(2.5,"MPa","Pa")'),
    _unit("units_pres_kpa_atm", 202.65, "kPa", "atm",
          '=CONVERT(202.65,"kPa","atm")'),
    _unit("units_def_pres_bar_pa", 3, "bar", "Pa", "=3*100000"),
    _unit("units_def_pres_mmhg_pa", 100, "mmHg", "Pa", "=100*133.322387415"),
    # 能量（cal 為熱化學卡，對應 Excel 代碼 "c"）
    _unit("units_en_kwh_j", 1, "kWh", "J", '=CONVERT(1,"kWh","J")'),
    _unit("units_en_cal_j", 10, "cal", "J", '=CONVERT(10,"c","J")'),
    _unit("units_en_kcal_j", 2, "kcal", "J", '=CONVERT(2,"kc","J")'),
    _unit("units_en_btu_j", 1, "BTU", "J", '=CONVERT(1,"BTU","J")'),
    _unit("units_en_wh_kj", 500, "Wh", "kJ", '=CONVERT(500,"Wh","J")/1000'),
    # 面積
    _unit("units_area_ha_m2", 2.5, "ha", "m2", '=CONVERT(2.5,"ha","m2")'),
    _unit("units_area_ft2_m2", 100, "ft2", "m2", '=CONVERT(100,"ft2","m2")'),
    _unit("units_area_acre_m2", 1, "acre", "m2",
          '=CONVERT(1,"uk_acre","m2")'),
    _unit("units_area_in2_cm2", 4, "in2", "cm2",
          '=CONVERT(4,"in2","m2")*10000'),
    _unit("units_def_area_ping_m2", 30, "ping", "m2", "=30*400/121"),
    # 體積
    _unit("units_vol_gal_l", 1, "gal", "L", '=CONVERT(1,"gal","l")'),
    _unit("units_vol_ft3_l", 2, "ft3", "L", '=CONVERT(2,"ft3","l")'),
    _unit("units_vol_in3_ml", 10, "in3", "mL", '=CONVERT(10,"in3","ml")'),
    _unit("units_vol_m3_l", 0.75, "m3", "L", '=CONVERT(0.75,"m3","l")'),
    # 速度
    _unit("units_spd_mph_ms", 60, "mph", "m/s", '=CONVERT(60,"mph","m/s")'),
    _unit("units_spd_knot_ms", 10, "knot", "m/s", '=CONVERT(10,"kn","m/s")'),
    _unit("units_spd_kmh_ms", 90, "km/h", "m/s", '=CONVERT(90,"km/h","m/s")'),
    _unit("units_def_spd_fts_ms", 100, "ft/s", "m/s", "=100*0.3048"),
    # 時間（yr = 365 天，Excel "yr" 為 365.25 天故用定義值）
    _unit("units_time_day_h", 3, "day", "h", '=CONVERT(3,"day","hr")'),
    _unit("units_time_min_s", 90, "min", "s", '=CONVERT(90,"mn","sec")'),
    _unit("units_time_h_min", 2.5, "h", "min", '=CONVERT(2.5,"hr","mn")'),
    _unit("units_def_time_week_day", 2, "week", "day", "=2*7"),
    _unit("units_def_time_yr_day", 1, "yr", "day", "=1*365"),
]


# ---- base（進位轉換／位元運算；expected 為字串）----
# Excel 的 DEC2BIN 等不補零，故以 RIGHT(REPT("0",n)&...,n) 補到本 App 的位寬格式；
# 負數與 64 位元邊界 Excel 的位寬規則不同（負數固定 10 位元／40 位元），
# 一律用「定義值」案例（id 含 base_def_，公式以字面定義值寫成）。
def _base_conv(cid, text, frm, width, signed, key, formula):
    """進位轉換案例：bridge base/convert，輸出鍵 key（BIN／OCT／DEC／HEX）。"""
    extra = {"string": True}
    if "base_def_" in cid:
        extra["defined"] = True
    return _case(cid, "base", "convert",
                 {"TEXT": text, "FROM": frm, "WIDTH": width, "SIGNED": signed},
                 formula, key, tol=0, **extra)


def _base_bw(cid, op, a, b, frm, width, signed, key, formula):
    """位元運算案例：bridge base/bitwise。"""
    extra = {"string": True}
    if "base_def_" in cid:
        extra["defined"] = True
    return _case(cid, "base", "bitwise",
                 {"OP": op, "A": a, "B": b, "FROM": frm, "WIDTH": width,
                  "SIGNED": signed}, formula, key, tol=0, **extra)


CASES += [
    _base_conv("base_dec2bin_10", "10", 10, 8, False, "BIN",
               '=RIGHT("00000000"&DEC2BIN(10),8)'),
    _base_conv("base_dec2hex_255", "255", 10, 16, False, "HEX",
               '=RIGHT("0000"&DEC2HEX(255),4)'),
    _base_conv("base_dec2oct_64", "64", 10, 16, False, "OCT",
               '=RIGHT("000000"&DEC2OCT(64),6)'),
    _base_conv("base_hex2dec_ff", "FF", 16, 16, False, "DEC",
               '=TEXT(HEX2DEC("FF"),"0")'),
    _base_conv("base_hex2dec_lower", "1a2b", 16, 16, False, "DEC",
               '=TEXT(HEX2DEC("1A2B"),"0")'),
    _base_conv("base_oct2dec_777", "777", 8, 16, False, "DEC",
               '=TEXT(OCT2DEC("777"),"0")'),
    _base_conv("base_bin2hex_ff", "11111111", 2, 8, False, "HEX",
               '=RIGHT("00"&BIN2HEX("11111111"),2)'),
    _base_conv("base_bin2dec_1011", "1011", 2, 8, False, "DEC",
               '=TEXT(BIN2DEC("1011"),"0")'),
    _base_conv("base_def_m1_bin8", "-1", 10, 8, True, "BIN",
               '="11111111"'),
    _base_conv("base_def_m1_hex8", "-1", 10, 8, True, "HEX", '="FF"'),
    _base_conv("base_def_m128_hex8", "-128", 10, 8, True, "HEX", '="80"'),
    _base_conv("base_def_hex80_dec_signed", "80", 16, 8, True, "DEC",
               '="-128"'),
    _base_conv("base_def_m2_bin16", "-2", 10, 16, True, "BIN",
               '="1111111111111110"'),
    _base_conv("base_def_i63max_hex", str(2 ** 63 - 1), 10, 64, True, "HEX",
               '="7FFFFFFFFFFFFFFF"'),
    _base_conv("base_def_u64max_dec", "FFFFFFFFFFFFFFFF", 16, 64, False,
               "DEC", '="18446744073709551615"'),
    _base_conv("base_def_i64min_dec", "8000000000000000", 16, 64, True,
               "DEC", '="-9223372036854775808"'),
    _base_conv("base_def_i64min_oct", "-9223372036854775808", 10, 64, True,
               "OCT", '="1000000000000000000000"'),
    _base_bw("base_and_12_10", "AND", "12", "10", 10, 8, False, "DEC",
             '=TEXT(BITAND(12,10),"0")'),
    _base_bw("base_or_12_10", "OR", "12", "10", 10, 8, False, "DEC",
             '=TEXT(BITOR(12,10),"0")'),
    _base_bw("base_xor_12_10", "XOR", "12", "10", 10, 8, False, "DEC",
             '=TEXT(BITXOR(12,10),"0")'),
    _base_bw("base_xor_hex", "XOR", "F0F0", "0FF0", 16, 16, False, "HEX",
             '=RIGHT("0000"&DEC2HEX(BITXOR(HEX2DEC("F0F0"),HEX2DEC("0FF0"))),4)'),
    _base_bw("base_shl_1_4", "SHL", "1", "4", 10, 8, False, "DEC",
             '=TEXT(BITLSHIFT(1,4),"0")'),
    _base_bw("base_shr_256_4", "SHR", "256", "4", 10, 16, False, "DEC",
             '=TEXT(BITRSHIFT(256,4),"0")'),
    _base_bw("base_def_shl_masked", "SHL", "129", "1", 10, 8, False, "DEC",
             '=TEXT(MOD(129*2,256),"0")'),
    _base_bw("base_def_not_u8", "NOT", "12", None, 10, 8, False, "DEC",
             '=TEXT(255-12,"0")'),
    _base_bw("base_def_not_s8", "NOT", "12", None, 10, 8, True, "DEC",
             '=TEXT(-12-1,"0")'),
    _base_bw("base_def_sar_m16_2", "SAR", "-16", "2", 10, 8, True, "DEC",
             '=TEXT(-16/4,"0")'),
    _base_bw("base_def_shr_logical_m16", "SHR", "-16", "2", 10, 8, True,
             "DEC", '=TEXT(INT(240/4),"0")'),
    _base_bw("base_def_shl_1_63_u64", "SHL", "1", "63", 10, 64, False, "HEX",
             '="8000000000000000"'),
    _base_bw("base_def_and_64", "AND", "FFFFFFFFFFFFFFFF",
             "0F0F0F0F0F0F0F0F", 16, 64, False, "HEX",
             '="0F0F0F0F0F0F0F0F"'),
]


# ---- stats / describe（敘述統計；眾數 expected 為數值 list）----
# 三組資料：A 單一眾數；B 含負數與小數、無眾數（定義值，MODE.MULT 在 Excel 為 #N/A）；
# C 多眾數。MODE.MULT 在 Evaluate 回傳陣列，產生器會攤平並遞增排序後存入 list。
_DESC_SETS = {
    "a": [2, 4, 4, 4, 5, 5, 7, 9],
    "b": [-3.5, 2.25, 0.5, -1.75, 8, 4.125, -0.5, 6.75, 1.0],
    "c": [3, 1, 3, 1, 2, 5, 5, 9, 4],
}
_DESC_FUNCS = (
    ("mean", "AVERAGE({a})"), ("median", "MEDIAN({a})"),
    ("q1", "QUARTILE.INC({a},1)"), ("q3", "QUARTILE.INC({a},3)"),
    ("skew", "SKEW({a})"), ("kurt", "KURT({a})"),
    ("sx", "STDEV.S({a})"), ("sigma_x", "STDEV.P({a})"),
    ("var", "VAR.S({a})"),
)


def _describe_cases():
    out = []
    for name, data in _DESC_SETS.items():
        arr = _arr(data)
        for key, tpl in _DESC_FUNCS:
            out.append(_case("stats_desc_%s_%s" % (name, key), "stats",
                             "describe", {"X": list(data), "F": None},
                             "=" + tpl.format(a=arr), key))
    return out


CASES += _describe_cases()
CASES += [
    _case("stats_desc_a_modes", "stats", "describe",
          {"X": list(_DESC_SETS["a"]), "F": None},
          "=MODE.MULT(%s)" % _arr(_DESC_SETS["a"]), "modes", as_list=True),
    _case("stats_desc_c_modes", "stats", "describe",
          {"X": list(_DESC_SETS["c"]), "F": None},
          "=MODE.MULT(%s)" % _arr(_DESC_SETS["c"]), "modes", as_list=True),
    # B 組每個值都只出現一次：MODE.MULT 為 #N/A，本 App 定義為空 list
    _case("stats_desc_b_modes", "stats", "describe",
          {"X": list(_DESC_SETS["b"]), "F": None},
          "=MODE.MULT(%s)" % _arr(_DESC_SETS["b"]), "modes",
          defined=True, literal=[]),
]


# ---- dist（機率分配；Excel 公式）----
# Excel 的 T.DIST／T.INV／CHISQ.* 會把自由度「截成整數」（T.INV(0.975,2.5)＝T.INV(0.975,2)），
# 本 App 允許非整數 df，故非整數 df 的案例改用等價且不截斷的 Excel 公式：
#   t 雙尾機率 = BETA.DIST(df/(df+x^2), df/2, 1/2)
#   t 臨界值 = SQRT(df*(1/BETA.INV(雙尾機率, df/2, 1/2) - 1))
#   卡方 = GAMMA.DIST(x, df/2, 2, .)、GAMMA.INV(p, df/2, 2)
# 右尾（right）以 Excel 的 *.RT、對稱關係或不完全 Gamma 關係求得（避免 1-cdf 的相消誤差）。
def _dist(cid, dist, inputs, formula, key="value"):
    """機率分配案例：bridge dist/<分配>。"""
    return _case("dist_" + cid, "dist", dist, inputs, formula, key)


def _nm(func, mu=0, sigma=1, x=None, prob=None):
    return {"FUNC": func, "MU": mu, "SIGMA": sigma, "X": x, "PROB": prob}


def _tt(func, df, x=None, prob=None):
    return {"FUNC": func, "DF": df, "X": x, "PROB": prob}


def _bn(func, n, p, k):
    return {"FUNC": func, "N": n, "P": p, "K": k}


def _po(func, lam, k):
    return {"FUNC": func, "LAMBDA": lam, "K": k}


CASES += [
    # ---- 常態 normal ----
    _dist("norm_pdf_std", "normal", _nm("pdf", x=1.5),
          "=NORM.DIST(1.5,0,1,FALSE)"),
    _dist("norm_pdf_100_15", "normal", _nm("pdf", 100, 15, 105),
          "=NORM.DIST(105,100,15,FALSE)"),
    _dist("norm_pdf_tiny", "normal", _nm("pdf", x=8),
          "=NORM.DIST(8,0,1,FALSE)"),
    _dist("norm_cdf_196", "normal", _nm("cdf", x=1.96),
          "=NORM.DIST(1.96,0,1,TRUE)"),
    _dist("norm_cdf_m8", "normal", _nm("cdf", x=-8),
          "=NORM.DIST(-8,0,1,TRUE)"),
    _dist("norm_cdf_100_15", "normal", _nm("cdf", 100, 15, 120),
          "=NORM.DIST(120,100,15,TRUE)"),
    _dist("norm_right_196", "normal", _nm("cdf", x=1.96),
          "=NORM.DIST(-1.96,0,1,TRUE)", "right"),
    _dist("norm_right_8", "normal", _nm("cdf", x=8),
          "=NORM.DIST(-8,0,1,TRUE)", "right"),
    _dist("norm_right_100_15", "normal", _nm("cdf", 100, 15, 80),
          "=1-NORM.DIST(80,100,15,TRUE)", "right"),
    _dist("norm_two_196", "normal", _nm("cdf", x=1.96),
          "=2*NORM.DIST(-1.96,0,1,TRUE)", "two"),
    _dist("norm_two_m3", "normal", _nm("cdf", x=-3),
          "=2*NORM.DIST(-3,0,1,TRUE)", "two"),
    _dist("norm_two_100_15", "normal", _nm("cdf", 100, 15, 130),
          "=2*NORM.DIST(70,100,15,TRUE)", "two"),
    _dist("norm_inv_975", "normal", _nm("inv", prob=0.975),
          "=NORM.INV(0.975,0,1)"),
    _dist("norm_inv_1em10", "normal", _nm("inv", prob=1e-10),
          "=NORM.INV(1E-10,0,1)"),
    _dist("norm_inv_50_10", "normal", _nm("inv", 50, 10, prob=0.3),
          "=NORM.INV(0.3,50,10)"),
    _dist("norm_inv_right_05", "normal", _nm("inv", prob=0.05),
          "=-NORM.INV(0.05,0,1)", "right"),
    _dist("norm_inv_right_100_15", "normal", _nm("inv", 100, 15, prob=0.9),
          "=NORM.INV(0.1,100,15)", "right"),
    _dist("norm_inv_right_tiny", "normal", _nm("inv", prob=1e-12),
          "=-NORM.INV(1E-12,0,1)", "right"),
    _dist("norm_inv_two_05", "normal", _nm("inv", prob=0.05),
          "=NORM.INV(0.975,0,1)", "two"),
    _dist("norm_inv_two_01", "normal", _nm("inv", prob=0.01),
          "=-NORM.INV(0.005,0,1)", "two"),
    _dist("norm_inv_two_100_15", "normal", _nm("inv", 100, 15, prob=0.1),
          "=NORM.INV(0.95,100,15)", "two"),
    # ---- t 分配 ----
    _dist("t_pdf_15_7", "t", _tt("pdf", 7, 1.5), "=T.DIST(1.5,7,FALSE)"),
    _dist("t_pdf_0_1", "t", _tt("pdf", 1, 0), "=T.DIST(0,1,FALSE)"),
    _dist("t_pdf_m3_4", "t", _tt("pdf", 4, -3), "=T.DIST(-3,4,FALSE)"),
    _dist("t_pdf_nonint", "t", _tt("pdf", 2.5, 1),
          "=GAMMA(1.75)/(SQRT(2.5*PI())*GAMMA(1.25))*(1+1/2.5)^(-1.75)"),
    _dist("t_cdf_2_10", "t", _tt("cdf", 10, 2.0), "=T.DIST(2.0,10,TRUE)"),
    _dist("t_cdf_m3_5", "t", _tt("cdf", 5, -3), "=T.DIST(-3,5,TRUE)"),
    _dist("t_cdf_m40_4", "t", _tt("cdf", 4, -40), "=T.DIST(-40,4,TRUE)"),
    _dist("t_cdf_nonint", "t", _tt("cdf", 2.5, 2),
          "=1-0.5*BETA.DIST(2.5/(2.5+4),1.25,0.5,TRUE)"),
    _dist("t_right_5_3", "t", _tt("cdf", 3, 5), "=T.DIST.RT(5,3)", "right"),
    _dist("t_right_200_10", "t", _tt("cdf", 10, 200), "=T.DIST.RT(200,10)",
          "right"),
    _dist("t_right_05_30", "t", _tt("cdf", 30, 0.5), "=T.DIST.RT(0.5,30)",
          "right"),
    _dist("t_two_2_10", "t", _tt("cdf", 10, 2), "=T.DIST.2T(2,10)", "two"),
    _dist("t_two_25_3", "t", _tt("cdf", 3, -2.5), "=T.DIST.2T(2.5,3)", "two"),
    _dist("t_two_nonint", "t", _tt("cdf", 2.5, 2),
          "=BETA.DIST(2.5/(2.5+4),1.25,0.5,TRUE)", "two"),
    _dist("t_inv_975_5", "t", _tt("inv", 5, prob=0.975), "=T.INV(0.975,5)"),
    _dist("t_inv_1em10_5", "t", _tt("inv", 5, prob=1e-10),
          "=T.INV(1E-10,5)"),
    _dist("t_inv_03_12", "t", _tt("inv", 12, prob=0.3), "=T.INV(0.3,12)"),
    _dist("t_inv_nonint", "t", _tt("inv", 2.5, prob=0.975),
          "=SQRT(2.5*(1/BETA.INV(0.05,1.25,0.5)-1))"),
    _dist("t_inv_right_05_8", "t", _tt("inv", 8, prob=0.05),
          "=T.INV(0.95,8)", "right"),
    _dist("t_inv_right_09_8", "t", _tt("inv", 8, prob=0.9),
          "=T.INV(0.1,8)", "right"),
    _dist("t_inv_right_tiny", "t", _tt("inv", 3, prob=1e-9),
          "=-T.INV(1E-9,3)", "right"),
    _dist("t_inv_two_05_10", "t", _tt("inv", 10, prob=0.05),
          "=T.INV.2T(0.05,10)", "two"),
    _dist("t_inv_two_01_3", "t", _tt("inv", 3, prob=0.01),
          "=T.INV.2T(0.01,3)", "two"),
    _dist("t_inv_two_1em8_20", "t", _tt("inv", 20, prob=1e-8),
          "=T.INV.2T(1E-8,20)", "two"),
    # ---- 卡方 chi-square ----
    _dist("chi2_pdf_25_4", "chi2", _tt("pdf", 4, 2.5),
          "=CHISQ.DIST(2.5,4,FALSE)"),
    _dist("chi2_pdf_05_1", "chi2", _tt("pdf", 1, 0.5),
          "=CHISQ.DIST(0.5,1,FALSE)"),
    _dist("chi2_pdf_10_3", "chi2", _tt("pdf", 3, 10),
          "=CHISQ.DIST(10,3,FALSE)"),
    _dist("chi2_pdf_nonint", "chi2", _tt("pdf", 2.5, 3),
          "=GAMMA.DIST(3,1.25,2,FALSE)"),
    _dist("chi2_cdf_384_1", "chi2", _tt("cdf", 1, 3.84),
          "=CHISQ.DIST(3.84,1,TRUE)"),
    _dist("chi2_cdf_0001_5", "chi2", _tt("cdf", 5, 0.001),
          "=CHISQ.DIST(0.001,5,TRUE)"),
    _dist("chi2_cdf_15_10", "chi2", _tt("cdf", 10, 15),
          "=CHISQ.DIST(15,10,TRUE)"),
    _dist("chi2_cdf_nonint", "chi2", _tt("cdf", 2.5, 3),
          "=GAMMA.DIST(3,1.25,2,TRUE)"),
    _dist("chi2_right_30_10", "chi2", _tt("cdf", 10, 30),
          "=CHISQ.DIST.RT(30,10)", "right"),
    _dist("chi2_right_200_10", "chi2", _tt("cdf", 10, 200),
          "=CHISQ.DIST.RT(200,10)", "right"),
    _dist("chi2_right_384_1", "chi2", _tt("cdf", 1, 3.84),
          "=CHISQ.DIST.RT(3.84,1)", "right"),
    _dist("chi2_inv_95_4", "chi2", _tt("inv", 4, prob=0.95),
          "=CHISQ.INV(0.95,4)"),
    _dist("chi2_inv_05_1", "chi2", _tt("inv", 1, prob=0.05),
          "=CHISQ.INV(0.05,1)"),
    _dist("chi2_inv_1em10_3", "chi2", _tt("inv", 3, prob=1e-10),
          "=CHISQ.INV(1E-10,3)"),
    _dist("chi2_inv_nonint", "chi2", _tt("inv", 3.5, prob=0.95),
          "=GAMMA.INV(0.95,1.75,2)"),
    _dist("chi2_inv_right_01_20", "chi2", _tt("inv", 20, prob=0.01),
          "=CHISQ.INV.RT(0.01,20)", "right"),
    _dist("chi2_inv_right_05_1", "chi2", _tt("inv", 1, prob=0.05),
          "=CHISQ.INV.RT(0.05,1)", "right"),
    _dist("chi2_inv_right_1em12_5", "chi2", _tt("inv", 5, prob=1e-12),
          "=CHISQ.INV.RT(1E-12,5)", "right"),
    # ---- 二項 binomial ----
    _dist("binom_pmf_3_10", "binom", _bn("pmf", 10, 0.3, 3),
          "=BINOM.DIST(3,10,0.3,FALSE)"),
    _dist("binom_pmf_500_1000", "binom", _bn("pmf", 1000, 0.5, 500),
          "=BINOM.DIST(500,1000,0.5,FALSE)"),
    _dist("binom_pmf_0_20", "binom", _bn("pmf", 20, 0.05, 0),
          "=BINOM.DIST(0,20,0.05,FALSE)"),
    _dist("binom_pmf_tiny", "binom", _bn("pmf", 100, 0.1, 50),
          "=BINOM.DIST(50,100,0.1,FALSE)"),
    _dist("binom_cdf_3_10", "binom", _bn("cdf", 10, 0.3, 3),
          "=BINOM.DIST(3,10,0.3,TRUE)"),
    _dist("binom_cdf_500_1000", "binom", _bn("cdf", 1000, 0.5, 500),
          "=BINOM.DIST(500,1000,0.5,TRUE)"),
    _dist("binom_cdf_tiny", "binom", _bn("cdf", 1000, 0.3, 0),
          "=BINOM.DIST(0,1000,0.3,TRUE)"),
    _dist("binom_cdf_all", "binom", _bn("cdf", 10, 0.4, 10),
          "=BINOM.DIST(10,10,0.4,TRUE)"),
    _dist("binom_right_3_10", "binom", _bn("cdf", 10, 0.3, 3),
          "=1-BINOM.DIST(3,10,0.3,TRUE)", "right"),
    _dist("binom_right_500_1000", "binom", _bn("cdf", 1000, 0.5, 500),
          "=1-BINOM.DIST(500,1000,0.5,TRUE)", "right"),
    _dist("binom_right_tiny", "binom", _bn("cdf", 1000, 0.3, 399),
          "=BINOM.DIST.RANGE(1000,0.3,400,1000)", "right"),
    # ---- Poisson ----
    _dist("pois_pmf_2_3", "poisson", _po("pmf", 3, 2),
          "=POISSON.DIST(2,3,FALSE)"),
    _dist("pois_pmf_0_30", "poisson", _po("pmf", 30, 0),
          "=POISSON.DIST(0,30,FALSE)"),
    _dist("pois_pmf_150_100", "poisson", _po("pmf", 100, 150),
          "=POISSON.DIST(150,100,FALSE)"),
    _dist("pois_pmf_5_05", "poisson", _po("pmf", 0.5, 5),
          "=POISSON.DIST(5,0.5,FALSE)"),
    _dist("pois_cdf_2_3", "poisson", _po("cdf", 3, 2),
          "=POISSON.DIST(2,3,TRUE)"),
    _dist("pois_cdf_10_3", "poisson", _po("cdf", 3, 10),
          "=POISSON.DIST(10,3,TRUE)"),
    _dist("pois_cdf_150_100", "poisson", _po("cdf", 100, 150),
          "=POISSON.DIST(150,100,TRUE)"),
    _dist("pois_cdf_tiny", "poisson", _po("cdf", 30, 0),
          "=POISSON.DIST(0,30,TRUE)"),
    _dist("pois_cdf_40_80", "poisson", _po("cdf", 80, 40),
          "=POISSON.DIST(40,80,TRUE)"),
    _dist("pois_right_2_3", "poisson", _po("cdf", 3, 2),
          "=1-POISSON.DIST(2,3,TRUE)", "right"),
    _dist("pois_right_150_100", "poisson", _po("cdf", 100, 150),
          "=1-POISSON.DIST(150,100,TRUE)", "right"),
    _dist("pois_right_tiny", "poisson", _po("cdf", 100, 200),
          "=GAMMA.DIST(100,201,1,TRUE)", "right"),
]
