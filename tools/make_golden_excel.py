"""用 Excel 產生 golden 值，寫入 tests/golden/excel.json。

只開「新的」隱藏 Excel 實例（DispatchEx），不接管使用者已開啟的 Excel；
使用暫存活頁簿、不存檔，結束時只 Quit() 自己的實例。
用法：python tools/make_golden_excel.py
"""
import copy
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from golden.cases import CASES  # noqa: E402

OUT = os.path.join(ROOT, "tests", "golden", "excel.json")


def _evaluate_list(xl, formula):
    """求值陣列公式（如 MODE.MULT），攤平成遞增排序的數值 list。"""
    v = xl.Evaluate(formula.lstrip("="))
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        v = ((v,),)
    if not isinstance(v, (tuple, list)):
        raise RuntimeError("Excel 回傳非陣列 %r（公式 %s）" % (v, formula))
    flat = [c for row in v for c in (row if isinstance(row, (tuple, list))
                                     else (row,))]
    if not flat or any(isinstance(c, bool) or not isinstance(c, (int, float))
                       for c in flat):
        raise RuntimeError("Excel 回傳非數值陣列 %r（公式 %s）" % (v, formula))
    return sorted(float(c) for c in flat)


def _evaluate(xl, formula, string=False):
    """以 Application.Evaluate 求值（可處理陣列常數）；錯誤值視為失敗。
    string=True 時結果必須是字串（base 案例），否則必須是數值。"""
    v = xl.Evaluate(formula.lstrip("="))
    if string:
        if isinstance(v, str):
            return v
        raise RuntimeError("Excel 回傳非字串 %r（公式 %s）" % (v, formula))
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    raise RuntimeError("Excel 回傳非數值 %r（公式 %s）" % (v, formula))


def _expected(xl, excel, formula):
    """依案例型態求期望值：literal（定義值 list）、as_list（陣列）、字串或數值。"""
    if "literal" in excel:
        return copy.deepcopy(excel["literal"])
    if excel.get("as_list"):
        return _evaluate_list(xl, formula)
    return _evaluate(xl, formula, excel.get("string", False))


def build(xl):
    """逐案求值，回傳 golden 資料 list。"""
    out = []
    for case in CASES:
        call = copy.deepcopy(case["call"])
        formula = case["excel"]["formula"]
        if "pmt_formula" in case["excel"]:
            pmt = _evaluate(xl, case["excel"]["pmt_formula"])
            call["inputs"]["PMT"] = pmt
            formula = formula.replace("{PMT}", repr(pmt))
        out.append({
            "id": case["id"], "sheet": case["sheet"], "call": call,
            "expect_key": case["expect_key"],
            "expected": _expected(xl, case["excel"], formula),
            "source": ("定義值：" if case["excel"].get("defined")
                       else "Excel 16: ") + formula,
            "tol": case["tol"],
        })
    return out


def main():
    import win32com.client
    xl = win32com.client.DispatchEx("Excel.Application")
    try:
        xl.Visible = False
        xl.DisplayAlerts = False
        wb = xl.Workbooks.Add()  # 暫存活頁簿，不存檔
        try:
            data = build(xl)
        finally:
            wb.Close(False)
    finally:
        xl.Quit()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("已產生 %d 筆 golden 案例 → %s" % (len(data), OUT))


if __name__ == "__main__":
    main()
