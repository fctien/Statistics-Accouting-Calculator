"""商業與稅務（business）測試。"""
from engine.business import profit, breakeven, pct_change, tax, TAX_PRESETS


def test_profit_margin_vs_markup():
    r = profit(cst=80, sel=100, unknown="MAR")
    assert r["ok"]
    assert abs(r["values"]["MAR"] - 20) < 1e-9
    assert abs(r["values"]["MU"] - 25) < 1e-9


def test_profit_solve_sel_and_cst():
    r = profit(cst=80, mar=20, unknown="SEL")
    assert abs(r["values"]["SEL"] - 100) < 1e-9
    r = profit(cst=80, mu=25, unknown="SEL")
    assert abs(r["values"]["SEL"] - 100) < 1e-9
    r = profit(sel=100, mu=25, unknown="CST")
    assert abs(r["values"]["CST"] - 80) < 1e-9
    r = profit(sel=100, mar=20, unknown="CST")
    assert abs(r["values"]["MU"] - 25) < 1e-9


def test_profit_inconsistent_and_zero_division():
    r = profit(cst=80, mar=20, mu=30, unknown="SEL")
    assert not r["ok"] and "不一致" in r["error"]
    r = profit(cst=80, mar=20, mu=25, unknown="SEL")
    assert r["ok"]
    assert not profit(cst=80, mar=100, unknown="SEL")["ok"]
    assert not profit(cst=0, sel=100, unknown="MU")["ok"]
    assert not profit(cst=80, sel=0, unknown="MAR")["ok"]
    r = profit(cst=80, unknown="MAR")
    assert not r["ok"] and r["field"] == "SEL"
    assert not profit(cst=True, sel=100, unknown="MAR")["ok"]
    assert not profit(cst=float("inf"), sel=100, unknown="MAR")["ok"]
    assert not profit(cst=80, sel=100, unknown="XX")["ok"]
    assert not profit(cst=80, unknown="SEL")["ok"]


def test_breakeven_q():
    r = breakeven(fc=10000, vc=6, p=10, pft=0, unknown="Q")
    assert abs(r["values"]["Q"] - 2500) < 1e-9


def test_breakeven_other_unknowns():
    assert abs(breakeven(vc=6, p=10, pft=0, q=2500,
                         unknown="FC")["values"]["FC"] - 10000) < 1e-9
    assert abs(breakeven(fc=10000, vc=6, p=10, q=3000,
                         unknown="PFT")["values"]["PFT"] - 2000) < 1e-9
    assert abs(breakeven(fc=10000, vc=6, pft=0, q=2500,
                         unknown="P")["values"]["P"] - 10) < 1e-9
    assert abs(breakeven(fc=10000, p=10, pft=0, q=2500,
                         unknown="VC")["values"]["VC"] - 6) < 1e-9


def test_breakeven_errors():
    r = breakeven(fc=1, vc=10, p=10, pft=0, unknown="Q")
    assert r["error"] == "售價等於變動成本，無法損益兩平" and r["field"] == "P"
    r = breakeven(fc=1, vc=10, pft=0, q=0, unknown="P")
    assert not r["ok"] and r["field"] == "Q"
    r = breakeven(fc=1, p=10, pft=0, q=0, unknown="VC")
    assert not r["ok"] and r["field"] == "Q"
    assert not breakeven(fc=None, vc=1, p=2, pft=0, unknown="Q")["ok"]


def test_pct_change_compound():
    r = pct_change(old=100, pct=10, pd=2, unknown="NEW")
    assert abs(r["values"]["NEW"] - 121) < 1e-9
    r = pct_change(old=100, pct=10, unknown="NEW")
    assert abs(r["values"]["NEW"] - 110) < 1e-9 and r["values"]["PD"] == 1


def test_pct_change_inverse():
    assert abs(pct_change(new=121, pct=10, pd=2,
                          unknown="OLD")["values"]["OLD"] - 100) < 1e-9
    assert abs(pct_change(old=100, new=121, pd=2,
                          unknown="PCT")["values"]["PCT"] - 10) < 1e-9
    assert abs(pct_change(old=100, new=121, pct=10,
                          unknown="PD")["values"]["PD"] - 2) < 1e-9


def test_pct_change_errors():
    assert not pct_change(old=0, new=5, unknown="PCT")["ok"]
    assert not pct_change(old=100, new=-5, pct=10, unknown="PD")["ok"]
    assert not pct_change(old=100, new=121, pct=0, unknown="PD")["ok"]
    assert not pct_change(old=0, new=121, pct=10, unknown="PD")["ok"]
    assert not pct_change(old=100, pct=-150, pd=0.5, unknown="NEW")["ok"]
    assert not pct_change(old=100, pct=10, pd=1e9, unknown="NEW")["ok"]


def test_tax_inclusive_vs_exclusive():
    r = tax(100, 5, "exclusive")
    assert r["values"] == {"net": 100.0, "tax": 5.0, "gross": 105.0}
    r = tax(105, 5, "inclusive")
    assert r["values"] == {"net": 100.0, "tax": 5.0, "gross": 105.0}
    r = tax(100, 5, "inclusive")
    v = r["values"]
    assert abs(v["net"] + v["tax"] - 100) < 1e-9 and v["net"] == 95.24


def test_tax_errors():
    assert tax(100, -100, "exclusive")["field"] == "rate"
    assert tax(100, float("inf"), "exclusive")["field"] == "rate"
    assert tax(100, 5, "x")["field"] == "mode"
    assert tax(float("nan"), 5, "exclusive")["field"] == "amount"
    assert tax(True, 5, "exclusive")["field"] == "amount"


def test_presets_have_source():
    assert TAX_PRESETS["營業稅"]["rate"] == 5
    assert TAX_PRESETS
    for name, p in TAX_PRESETS.items():
        assert p["source_url"].startswith("https://"), name
        assert len(p["checked"]) == 10 and p["checked"][4] == "-", name
