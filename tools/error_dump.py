"""錯誤路徑案例（error cases）的 CPython 參考回應產生器。

用法：
    python tools/error_dump.py            印出 {id: 回應 dict}（stdout，JSON）
    python tools/error_dump.py --write    把回應寫回 tests/golden/error_cases.json 的 expected
    python tools/error_dump.py --init     重建 error_cases.json 的請求清單（含 expected）
案例格式：{"id", "raw"（原樣字串）或 "request"（物件）, "expected"}。
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine.bridge import call  # noqa: E402

PATH = os.path.join(ROOT, "tests", "golden", "error_cases.json")


def _req(sheet, action, inputs, settings=None):
    """組出標準請求物件。"""
    return {"sheet": sheet, "action": action, "inputs": inputs,
            "settings": settings or {}}


_TVM = {"N": 10, "IY": 5, "PV": -100, "PMT": 0, "FV": None}
_CF = [[3000, 1], [4200, 1]]
_BOND = {"SDT": [2026, 6, 12], "RDT": [2036, 1, 1], "CPN": 7.0, "RV": 100.0,
         "basis": "ACT", "freq": 2, "YLD": 8.0, "PRI": None}
_DEPR = {"method": "SL", "CST": 10000, "SAL": 1000, "LIF": 5, "M01": 1,
         "DB": 200, "YR": 1}

# (id, raw 字串或 None, 請求物件或 None)
CASES = [
    ("invalid_json", "not json", None),
    ("non_dict_list", "[1, 2]", None),
    ("non_dict_number", "42", None),
    ("unknown_route", None, _req("nope", "x", {})),
    ("unknown_action", None, _req("tvm", "nope", {})),
    ("tvm_two_blanks", None, _req("tvm", "solve", dict(_TVM, PMT=None))),
    ("tvm_all_filled", None, _req("tvm", "solve", dict(_TVM, FV=0))),
    ("tvm_string_field", None, _req("tvm", "solve", dict(_TVM, N="abc"))),
    ("tvm_bool_field", None, _req("tvm", "solve", dict(_TVM, IY=True))),
    ("tvm_string_numeric_text", None, _req("tvm", "solve", dict(_TVM, PV="100"))),
    ("amort_N_noninteger", None, _req("amort", "schedule", {
        "N": 12.5, "IY": 5, "PV": 100, "PMT": -10, "FV": 0,
        "PY": 12, "CY": 12, "BGN": False})),
    ("irr_no_sign_change", None, _req("cashflow", "irr", {
        "CF0": 100, "flows": _CF, "I": 10, "RI": None})),
    ("payback_cf0_nonneg", None, _req("cashflow", "pb", {
        "CF0": 100, "flows": _CF, "I": 10, "RI": None})),
    ("calc_div_zero", None, _req("calc", "eval", {"EXPR": "1/0"})),
    ("calc_ln_zero", None, _req("calc", "eval", {"EXPR": "ln(0)"})),
    ("calc_unclosed_paren", None, _req("calc", "eval", {"EXPR": "(1+2"})),
    ("calc_1e999", None, _req("calc", "eval", {"EXPR": "1e999"})),
    ("calc_dollar_char", None, _req("calc", "eval", {"EXPR": "$"})),  # π 已改為常數
    ("calc_asin_domain", None, _req("calc", "eval", {"EXPR": "asin(2)"})),
    ("calc_acos_domain", None, _req("calc", "eval", {"EXPR": "acos(-1.5)"})),
    ("calc_tan_90_deg", None, _req("calc", "eval", {"EXPR": "tan(90)"})),
    ("calc_tan_pi_half_rad", None, _req(
        "calc", "eval", {"EXPR": "tan(pi/2)"}, {"angle": "RAD"})),
    ("calc_log_zero", None, _req("calc", "eval", {"EXPR": "log(0)"})),
    ("calc_log_negative", None, _req("calc", "eval", {"EXPR": "log(-1)"})),
    ("calc_implicit_2e", None, _req("calc", "eval", {"EXPR": "2e"})),
    ("calc_bad_angle", None, _req(
        "calc", "eval", {"EXPR": "sin(1)"}, {"angle": "GRAD"})),
    ("stats_exp_negative_y", None, _req("stats", "two_var", {
        "X": [1, 2, 3], "Y": [2, -3, 4], "model": "EXP"})),
    ("bond_sdt_ge_rdt", None, _req("bond", "price", dict(
        _BOND, SDT=[2036, 1, 1], RDT=[2026, 6, 12]))),
    ("depr_syd_m01_7", None, _req("depr", "year", dict(
        _DEPR, method="SYD", M01=7))),
    ("tax_amount_1e14", None, _req("business", "tax", {
        "AMOUNT": 1e14, "RATE": 5, "MODE": "exclusive"})),
    ("date_invalid_feb30", None, _req("date", "solve", {
        "DT1": [2026, 2, 30], "DT2": [2026, 3, 1], "DBD": None, "basis": "ACT"})),
    ("units_cross_category", None, _req("units", "convert", {
        "VALUE": 1, "FROM": "m", "TO": "kg"})),
    ("units_unknown_from", None, _req("units", "convert", {
        "VALUE": 1, "FROM": "zz", "TO": "m"})),
    ("units_unknown_to", None, _req("units", "convert", {
        "VALUE": 1, "FROM": "m", "TO": "zz"})),
    ("units_below_absolute_zero", None, _req("units", "convert", {
        "VALUE": -300, "FROM": "degC", "TO": "degF"})),
    ("units_value_string", None, _req("units", "convert", {
        "VALUE": "1", "FROM": "m", "TO": "km"})),
    ("units_missing_to", None, _req("units", "convert", {
        "VALUE": 1, "FROM": "m"})),
    ("settings_bad_decimals", None, _req("tvm", "solve", _TVM, {"decimals": 12})),
]


def run_case(entry):
    """用 bridge.call 跑單一案例，回傳解析後的回應 dict。"""
    raw = entry["raw"] if "raw" in entry else json.dumps(entry["request"])
    return json.loads(call(raw))


def _entries():
    """由 CASES 建立不含 expected 的案例清單。"""
    out = []
    for cid, raw, req in CASES:
        e = {"id": cid}
        if raw is not None:
            e["raw"] = raw
        else:
            e["request"] = req
        out.append(e)
    return out


def main():
    """依參數輸出或寫入參考回應。"""
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "--init":
        entries = _entries()
    else:
        with open(PATH, encoding="utf-8") as f:
            entries = json.load(f)
    if mode in ("--init", "--write"):
        for e in entries:
            e["expected"] = run_case(e)
        with open(PATH, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=1, sort_keys=True)
            f.write("\n")
        return
    # ensure_ascii=True：避免 Windows 主控台編碼（cp950）弄壞中文
    print(json.dumps({e["id"]: run_case(e) for e in entries}, sort_keys=True))


if __name__ == "__main__":
    main()
