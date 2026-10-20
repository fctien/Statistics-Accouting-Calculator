"""金額（分整數）測試。"""
import pytest

from engine.money import (MAX_AMOUNT, round_div, to_cents, tax_exclusive,
                          tax_inclusive)


def test_round_half_away():
    assert round_div(5, 2) == 3 and round_div(-5, 2) == -3 and round_div(4, 3) == 1


def test_to_cents_no_float_drift():
    assert to_cents(2.675) == 268 and to_cents(-0.005) == -1


def test_to_cents_large_typed_amount():
    # 大金額仍以使用者輸入的十進位值進位（half away from zero）；
    # 舊作法 '%.6f' 在 ~1e9 元以上會看到二進位誤差（.18499755… → 少 1 分），MicroPython 也會不同
    assert to_cents(116455781560.185) == 11645578156019
    assert to_cents(-116455781560.185) == -11645578156019
    assert to_cents(1e-05) == 0 and to_cents(0.0049999999) == 0
    assert to_cents(0.0) == 0 and to_cents(-0.0) == 0 and to_cents(12) == 1200


def test_to_cents_bound():
    # 上限 1e13 元：'%.15g' 的 15 位有效數字 = 13 位整數 + 2 位小數，分位才不會被截掉
    assert MAX_AMOUNT == 1e13
    assert to_cents(9999999999999.99) == 999999999999999
    assert to_cents(-1234567890123.45) == -123456789012345
    assert to_cents(1157981314486.25) == 115798131448625
    for bad in (1e13, -1e13, 1e15, 1e26, float("inf"), float("-inf"), float("nan")):
        with pytest.raises(ValueError):
            to_cents(bad)


def test_tax_exclusive_5pct():
    assert tax_exclusive(10000, 5) == {"net": 10000, "tax": 500, "gross": 10500}


def test_tax_inclusive_5pct():
    r = tax_inclusive(10500, 5)
    assert r == {"net": 10000, "tax": 500, "gross": 10500}
    r = tax_inclusive(100, 5)
    assert r["net"] + r["tax"] == 100 and r["net"] == 95
