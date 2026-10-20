"""bridge 統一入口測試。"""
import json

from engine.bridge import call
from golden import runner


def _call(req):
    return json.loads(call(json.dumps(req)))


def _tvm(**kw):
    inp = {"N": 360, "IY": 6, "PV": 300000, "PMT": None, "FV": 0,
           "PY": 12, "CY": 12, "BGN": False}
    inp.update(kw)
    return {"sheet": "tvm", "action": "solve", "inputs": inp, "settings": {}}


def test_bridge_all_golden(golden_cases):
    cases = []
    for sheet in ("tvm", "amort", "cashflow", "iconv", "stats", "bond",
                  "depr", "date", "business", "calc"):
        cases += golden_cases(sheet)
    assert len(cases) >= 51
    assert runner.run(cases, _call) == []


def test_bridge_blank_count():
    r = _call(_tvm(PMT=-1800))
    assert not r["ok"] and "只留一格" in r["error"]
    r = _call(_tvm(PMT=None, FV=None))
    assert not r["ok"] and "只留一格" in r["error"]
    assert _call(_tvm())["ok"]


def test_bridge_profit_blank_rule():
    def prof(**kw):
        inp = {"CST": None, "SEL": None, "MAR": None, "MU": None}
        inp.update(kw)
        return _call({"sheet": "business", "action": "profit",
                      "inputs": inp})
    r = prof(CST=80, MU=25)
    assert r["ok"] and abs(r["values"]["SEL"] - 100) < 1e-9
    assert prof(CST=80, SEL=100)["ok"]
    r = prof(MAR=20, MU=25)
    assert not r["ok"] and "只留一格" in r["error"]
    assert not prof(CST=1, SEL=2, MAR=3, MU=4)["ok"]


def test_bridge_unknown_route():
    assert _call({"sheet": "nope", "action": "x", "inputs": {}})["ok"] is False
    assert _call({"sheet": "tvm", "action": "zzz", "inputs": {}})["ok"] is False


def test_bridge_never_raises():
    bad = ["not json", "[1,2]", "null", "{}", '{"sheet": []}',
           '{"sheet":"tvm","action":"solve","inputs":5}',
           '{"sheet":"tvm","action":"solve","inputs":{"N":"abc"}}',
           '{"sheet":"tvm","action":"solve","inputs":{"N":1e999}}',
           '{"sheet":"tvm","action":"solve","inputs":{"N":NaN}}',
           '{"sheet":"tvm","action":"solve","settings":[]}',
           '{"sheet":"stats","action":"one_var","inputs":{"X":[1,"a"]}}',
           '{"sheet":"cashflow","action":"npv","inputs":{"CF0":1,"flows":3}}',
           '{"sheet":"date","action":"solve","inputs":{"DT1":[1,2]}}',
           "[" * 100000, None, 5]
    for text in bad:
        r = json.loads(call(text))
        assert r["ok"] is False, text
    assert _call(_tvm(PV=10 ** 400))["ok"] is False
    assert "ok" in _call(_tvm(PV=1e300, FV=1e300, N=1e300, PMT=None))
    assert _call({"sheet": "amort", "action": "schedule",
                  "inputs": {"N": 100000, "IY": 5, "PV": 1, "PMT": 1,
                             "PY": 12, "CY": 12}})["ok"] is False
    assert _call({"sheet": "depr", "action": "schedule",
                  "inputs": {"method": "SL", "CST": 1, "SAL": 0,
                             "LIF": 100000}})["ok"] is False


def test_display_uses_settings():
    base = _call(_tvm())
    assert base["display"]["PMT"] == "-1,798.65"
    r = _call(dict(_tvm(), settings={"decimals": 4, "sep": "eu"}))
    assert r["display"]["PMT"] == "-1.798,6516"
    assert _call(dict(_tvm(), settings={"decimals": 12}))["ok"] is False


def test_schedule_and_calc():
    r = _call({"sheet": "depr", "action": "schedule",
               "inputs": {"method": "SL", "CST": 10000, "SAL": 1000,
                          "LIF": 5}})
    assert r["ok"] and len(r["display"]["rows"]) == 5
    r = _call({"sheet": "calc", "action": "eval",
               "inputs": {"EXPR": "1+2*3"}, "settings": {"mode": "AOS"}})
    assert r["ok"] and r["values"]["value"] == 7
    r = _call({"sheet": "calc", "action": "eval",
               "inputs": {"EXPR": "1+2*3"}, "settings": {"mode": "CHAIN"}})
    assert r["values"]["value"] == 9
