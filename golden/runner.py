"""golden 案例執行器（CPython 與 MicroPython 共用，僅用 json）。

call_fn(request: dict) -> 回應 dict（{"ok", "values", ...}）。
命令列入口在 tools/golden_dump.py（避免 golden/ 內 import sys）。
"""
import json


def rel_close(a, b, tol):
    """相對誤差比較（relative tolerance）：abs(a-b) <= tol * max(1, abs(b))。"""
    return abs(a - b) <= tol * max(1, abs(b))


def load(path):
    """讀取 excel.json，回傳案例 list。"""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _value(case, call_fn):
    """執行單一案例，回傳 (值或 None, 失敗訊息或 None)。"""
    resp = call_fn(case["call"])
    if not resp.get("ok"):
        return None, "%s: 引擎回報失敗 %s" % (case["id"], resp.get("error"))
    values = resp.get("values") or {}
    key = case["expect_key"]
    if key not in values:
        return None, "%s: 結果缺少欄位 %s" % (case["id"], key)
    return values[key], None


def run(cases, call_fn):
    """逐案比對（expected 為字串時完全相等，否則數值相對誤差），回傳失敗訊息清單（空 list 表示全部通過）。"""
    fails = []
    for case in cases:
        got, msg = _value(case, call_fn)
        if msg:
            fails.append(msg)
            continue
        exp = case["expected"]
        tol = case.get("tol", 1e-9)
        if isinstance(exp, str):  # 字串案例：完全相等（不容許型別轉換）
            if not isinstance(got, str) or got != exp:
                fails.append("%s: %s 期望 %r 實得 %r" % (
                    case["id"], case["expect_key"], exp, got))
            continue
        if not isinstance(got, (int, float)) or not rel_close(got, exp, tol):
            fails.append("%s: %s 期望 %r 實得 %r" % (
                case["id"], case["expect_key"], exp, got))
    return fails


def dump(cases, call_fn):
    """回傳 {id: 引擎算出的值或 None}，供跨環境（CPython／MicroPython）比對。"""
    out = {}
    for case in cases:
        got, msg = _value(case, call_fn)
        out[case["id"]] = None if msg else got
    return out
