"""金額（分整數）測試。"""
from engine.money import round_div, to_cents, tax_exclusive, tax_inclusive


def test_round_half_away():
    assert round_div(5, 2) == 3 and round_div(-5, 2) == -3 and round_div(4, 3) == 1


def test_to_cents_no_float_drift():
    assert to_cents(2.675) == 268 and to_cents(-0.005) == -1


def test_tax_exclusive_5pct():
    assert tax_exclusive(10000, 5) == {"net": 10000, "tax": 500, "gross": 10500}


def test_tax_inclusive_5pct():
    r = tax_inclusive(10500, 5)
    assert r == {"net": 10000, "tax": 500, "gross": 10500}
    r = tax_inclusive(100, 5)
    assert r["net"] + r["tax"] == 100 and r["net"] == 95
