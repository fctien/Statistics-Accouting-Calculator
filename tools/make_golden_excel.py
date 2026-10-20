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


def _evaluate(xl, formula):
    """以 Application.Evaluate 求值（可處理陣列常數）；錯誤值視為失敗。"""
    v = xl.Evaluate(formula.lstrip("="))
    if isinstance(v, (int, float)):
        return float(v)
    raise RuntimeError("Excel 回傳非數值 %r（公式 %s）" % (v, formula))


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
            "expected": _evaluate(xl, formula),
            "source": "Excel 16: " + formula,
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
