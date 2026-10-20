"""統一回傳格式（result envelope）。

成功：{"ok": True, "values": {...}, "warnings": [...]}
失敗：{"ok": False, "error": <中文原因>, "field": <欄位或 None>}
僅用 CPython 與 MicroPython 都支援的功能。
"""

_INF = float("inf")


def is_finite(x):
    """判斷是否為有限數（finite）；不用 math.isfinite，MicroPython 亦可用。"""
    return x == x and x not in (_INF, -_INF)


def err(message, field=None):
    """建立失敗結果。"""
    return {"ok": False, "error": message, "field": field}


def _all_finite(v):
    """遞迴檢查數值（含巢狀 list／tuple／dict）是否皆為有限數。"""
    if isinstance(v, float):
        return is_finite(v)
    if isinstance(v, (list, tuple)):
        for item in v:
            if not _all_finite(item):
                return False
    elif isinstance(v, dict):
        for item in v.values():
            if not _all_finite(item):
                return False
    return True


def ok(values, warnings=None):
    """建立成功結果；任一數值非有限（inf／nan）時改回溢位錯誤。"""
    for key in values:
        if not _all_finite(values[key]):
            return err("計算結果超出範圍（溢位）", field=key)
    return {"ok": True, "values": values,
            "warnings": [] if warnings is None else warnings}
