"""ICONV 名目／有效利率轉換測試。"""
from engine.iconv import eff_to_nom, nom_to_eff
from tests.conftest import rel_close


def test_iconv_golden(golden_cases):
    cases = golden_cases("iconv")
    assert cases
    for c in cases:
        inp = c["call"]["inputs"]
        if inp.get("NOM") is not None:
            r = nom_to_eff(inp["NOM"], inp["CY"])
        else:
            r = eff_to_nom(inp["EFF"], inp["CY"])
        assert r["ok"] and rel_close(
            r["values"][c["expect_key"]], c["expected"], c["tol"]), c["id"]


def test_roundtrip():
    for nom in (0.5, 12, 18, 36):
        for cy in (1, 4, 12, 365):
            eff = nom_to_eff(nom, cy)["values"]["EFF"]
            assert abs(eff_to_nom(eff, cy)["values"]["NOM"] - nom) < 1e-10


def test_cy_invalid():
    for f in (nom_to_eff, eff_to_nom):
        for cy in (0, -1):
            r = f(10, cy)
            assert not r["ok"] and r["field"] == "CY"
