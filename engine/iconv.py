"""名目／有效利率轉換（ICONV，nominal / effective interest rate）。

利率皆為百分比數字；CY 為每年複利次數（compounding periods per year）。
"""
from engine.result import err, ok

_OVERFLOW_MSG = "計算結果超出範圍（溢位）"


def nom_to_eff(nom, cy):
    """名目年利率 NOM(%) 轉有效年利率 EFF(%)。"""
    if not cy > 0:
        return err("C/Y 必須大於 0", "CY")
    if 1 + nom / 100 / cy <= 0:
        return err("NOM 數值不合理（利率低於 -100%）", "NOM")
    try:
        return ok({"EFF": ((1 + nom / 100 / cy) ** cy - 1) * 100})
    except OverflowError:
        return err(_OVERFLOW_MSG, "EFF")


def eff_to_nom(eff, cy):
    """有效年利率 EFF(%) 轉名目年利率 NOM(%)。"""
    if not cy > 0:
        return err("C/Y 必須大於 0", "CY")
    if 1 + eff / 100 <= 0:
        return err("EFF 數值不合理（利率低於 -100%）", "EFF")
    try:
        return ok({"NOM": cy * ((1 + eff / 100) ** (1 / cy) - 1) * 100})
    except OverflowError:
        return err(_OVERFLOW_MSG, "NOM")
