"""單位換算（engine/units.py）與 bridge units 路由測試。"""
import json

import pytest

from engine import units
from engine.bridge import call
from golden import runner
from tests.conftest import rel_close


def _call(req):
    return json.loads(call(json.dumps(req)))


def _conv(value, frm, to):
    return _call({"sheet": "units", "action": "convert",
                  "inputs": {"VALUE": value, "FROM": frm, "TO": to},
                  "settings": {}})


def test_units_golden(golden_cases):
    cases = golden_cases("units")
    assert len(cases) >= 36
    assert runner.run(cases, _call) == []


def test_units_golden_covers_every_category(golden_cases):
    cats = {}
    for u in units.list_units()["values"]["categories"]:
        for x in u["units"]:
            cats[x["id"]] = u["id"]
    seen = {}
    for c in golden_cases("units"):
        k = cats[c["call"]["inputs"]["FROM"]]
        seen[k] = seen.get(k, 0) + 1
    assert len(seen) == 9
    assert min(seen.values()) >= 3


def test_list_units_structure():
    r = units.list_units()
    assert r["ok"]
    cats = r["values"]["categories"]
    assert [c["id"] for c in cats] == [
        "length", "mass", "temperature", "pressure", "energy", "area",
        "volume", "speed", "time"]
    ids = []
    for c in cats:
        assert c["zh"] and c["en"] and c["units"]
        for u in c["units"]:
            assert u["id"].isascii() and u["zh"] and u["en"]
            ids.append(u["id"])
    assert len(ids) == len(set(ids))
    for must in ("km", "mi", "degC", "degF", "K", "psi", "mmHg", "kWh",
                 "BTU", "catty", "tael", "ping", "acre", "gal", "knot",
                 "yr", "um", "nmi", "t"):
        assert must in ids
    assert _call({"sheet": "units", "action": "list", "inputs": {}})["ok"]


def _pairs():
    out = []
    for c in units.list_units()["values"]["categories"]:
        ids = [u["id"] for u in c["units"]]
        for a in ids:
            for b in ids:
                out.append((c["id"], a, b))
    return out


@pytest.mark.parametrize("cat,a,b", _pairs())
def test_round_trip(cat, a, b):
    x = 273.0 if cat == "temperature" else 12.3456
    r1 = units.convert(x, a, b)
    assert r1["ok"], r1
    r2 = units.convert(r1["values"]["value"], b, a)
    assert r2["ok"], r2
    assert rel_close(r2["values"]["value"], x, 1e-12)


def test_defined_values():
    v = lambda x, a, b: units.convert(x, a, b)["values"]["value"]  # noqa
    assert rel_close(v(1, "in", "m"), 0.0254, 1e-15)
    assert rel_close(v(1, "lb", "kg"), 0.45359237, 1e-15)
    assert rel_close(v(1, "atm", "Pa"), 101325, 1e-15)
    assert rel_close(v(1, "cal", "J"), 4.184, 1e-15)
    assert rel_close(v(1, "ping", "m2"), 400 / 121, 1e-15)
    assert rel_close(v(1, "yr", "day"), 365, 1e-15)
    assert abs(v(100, "degC", "degF") - 212) < 1e-9
    assert abs(v(-40, "degF", "degC") + 40) < 1e-9


def test_cross_category_error():
    r = units.convert(1, "m", "kg")
    assert not r["ok"] and r["field"] == "TO"
    r = _conv(1, "degC", "psi")
    assert not r["ok"]


def test_unknown_units():
    r = units.convert(1, "xx", "m")
    assert not r["ok"] and r["field"] == "FROM"
    r = units.convert(1, "m", "xx")
    assert not r["ok"] and r["field"] == "TO"
    assert units.convert(1, None, "m")["field"] == "FROM"


def test_non_finite_value():
    for bad in (float("inf"), float("nan"), True, "1", None):
        r = units.convert(bad, "m", "km")
        assert not r["ok"] and r["field"] == "VALUE"
    r = units.convert(1e305, "yr", "s")
    assert not r["ok"]


def test_absolute_zero():
    assert units.convert(-273.15, "degC", "K")["values"]["value"] == 0.0
    assert units.convert(-459.67, "degF", "K")["values"]["value"] == 0.0
    assert units.convert(0, "K", "degC")["ok"]
    for frm, v in (("degC", -273.16), ("degF", -459.68), ("K", -0.001)):
        r = units.convert(v, frm, "K")
        assert not r["ok"] and r["field"] == "VALUE"
    # 目標單位不影響來源的絕對零度檢查
    assert not units.convert(-300, "degC", "degF")["ok"]


def test_bridge_validation():
    assert not _call({"sheet": "units", "action": "convert",
                      "inputs": {"VALUE": 1, "FROM": "m"}})["ok"]
    assert not _call({"sheet": "units", "action": "convert",
                      "inputs": {"VALUE": None, "FROM": "m", "TO": "km"}})["ok"]
    r = _conv(1000, "m", "km")
    assert r["ok"] and r["display"]["value"] == "1.00"


def test_mmhg_is_conventional_not_torr():
    v = units.convert(100, "mmHg", "Pa")["values"]["value"]
    assert rel_close(v, 13332.2387415, 1e-12)
    assert not rel_close(v, 100 * 101325 / 760, 1e-8)


def test_list_has_sym_and_zh_error():
    cats = units.list_units()["values"]["categories"]
    sym = {u["id"]: u["sym"] for c in cats for u in c["units"]}
    assert sym["um"] == "µm" and sym["m2"] == "m²" and sym["degC"] == "°C"
    assert sym["in3"] == "in³" and sym["km"] == "km"
    r = units.convert(1, "m", "kg")
    assert "長度" not in r["error"] and "公尺" in r["error"]
