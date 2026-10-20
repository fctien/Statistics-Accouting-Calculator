"""pytest 共用設定：golden 案例讀取（fixture）與相對誤差比較（helper）。"""
import json
import os

import pytest

GOLDEN_PATH = os.path.join(os.path.dirname(__file__), "golden", "excel.json")


def rel_close(a, b, tol):
    """相對誤差比較（relative tolerance）：abs(a-b) <= tol * max(1, abs(b))。"""
    return abs(a - b) <= tol * max(1, abs(b))


@pytest.fixture
def golden_cases():
    """回傳函式 golden_cases(sheet) -> list[dict]，讀 excel.json 並依 sheet 過濾。"""
    if not os.path.exists(GOLDEN_PATH):
        pytest.skip("tests/golden/excel.json 尚未產生")

    def _load(sheet):
        with open(GOLDEN_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return [c for c in data if c.get("sheet") == sheet]

    return _load
