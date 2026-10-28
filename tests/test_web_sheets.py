"""web/js/sheets.js 欄位定義 × engine/bridge.py：端到端（end-to-end）檢查。

每張工作表、每個動作：用欄位 example 填表（留空欄位見 BLANKS），經 input.js collect()
轉成 inputs，實際呼叫 bridge.call，必須 ok；回傳值所對應欄位的 example 也必須與結果相符
（說明文字裡的範例不能是錯的數字）。欄位 id／key 拼錯會讓 bridge 報「請輸入 …」而失敗。
"""
import json

import pytest

from engine.bridge import call
from tests._node import run_node

# 留一格空白求解的工作表：留空哪幾格（其餘動作全部欄位都填 example）
BLANKS = {
    "tvm.solve": ["PMT"],
    "stats.predict": ["YP"],
    "business-profit.profit": ["SEL", "MAR"],
    "business-breakeven.breakeven": ["Q"],
    "business-pct.pct_change": ["PCT"],
    "date.solve": ["DBD"],
}


@pytest.fixture(scope="module")
def requests():
    proc = run_node(["tests/js/helpers/sheet_examples.mjs",
                     json.dumps(BLANKS)])
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def _num(text):
    """把 US 格式數字字串轉成 float（去掉千分位）。"""
    return float(text.replace(",", ""))


def _with_commas(example):
    """"98771.99" -> "98,771.99"（說明文字可用千分位寫法）。"""
    sign = "-" if example.startswith("-") else ""
    body = example.lstrip("-")
    ip, _, fp = body.partition(".")
    return sign + "{:,}".format(int(ip)) + ("." + fp if fp else "")


def test_every_engine_sheet_and_action_present(requests):
    pairs = {(r["sheet"], r["action"]) for r in requests}
    assert ("tvm", "solve") in pairs and ("cashflow", "dpb") in pairs
    assert len(pairs) == len(requests)


def test_examples_parse_without_errors(requests):
    bad = {"%s.%s" % (r["sheet"], r["action"]): r["errors"]
           for r in requests if r["errors"]}
    assert not bad


def test_examples_solve_in_engine_and_match_outputs(requests):
    problems = []
    for r in requests:
        if r["engine"] is None:  # 設定頁不經引擎
            continue
        name = "%s.%s" % (r["sheet"], r["action"])
        req = {"sheet": r["engine"], "action": r["action"],
               "inputs": r["inputs"], "settings": {}}
        res = json.loads(call(json.dumps(req)))
        if not res.get("ok"):
            problems.append("%s：%s（field=%s）" % (name, res.get("error"),
                                                 res.get("field")))
            continue
        by_out = {f["out"]: f for f in r["fields"]}
        for key, val in res["values"].items():
            f = by_out.get(key)
            if f is None or key == "rows":
                continue
            ex = f["example"]
            if f["kind"] == "text":
                ok = val == ex
            elif f["kind"] == "date":
                ok = val == [int(x) for x in ex.split("-")]
            else:
                # 範例必須等於引擎的 2 位小數顯示（display），不允許誤差
                shown = res["display"][key]
                if f["kind"] == "direction":
                    shown = shown.lstrip("-")
                ok = _num(ex) == _num(shown)
                val = shown
            if not ok:
                problems.append("%s：%s 範例 %r，引擎顯示 %r" % (name, key, ex, val))
    assert not problems, "\n".join(problems)


def test_sheet_actions_cover_bridge_routes(requests):
    """bridge 的每個路由都有對應的工作表動作（UI 不會漏功能）。"""
    from engine.bridge import ROUTES
    have = {(r["engine"], r["action"]) for r in requests if r["engine"]}
    # units 路由的 UI（工程頁）由後續任務加入，屆時移除此豁免
    routes = {r for r in ROUTES if r[0] != "units"}
    assert routes <= have, sorted(routes - have)


def test_help_text_quotes_the_example(requests):
    """說明文字中的數字範例必須就是 example（已由上一個測試對過引擎）。"""
    proc = run_node(["-e", (
        "import('./web/js/sheets.js').then(m => process.stdout.write("
        "JSON.stringify(m.SHEET_ORDER.flatMap(id => m.SHEETS[id].fields"
        ".map(f => [id, f.id, f.kind, f.example, f.help])))))")])
    assert proc.returncode == 0, proc.stderr
    bad = []
    for sheet, fid, kind, ex, helptext in json.loads(proc.stdout):
        numeric = ex.lstrip("-").replace(".", "").isdigit()
        if kind in ("number", "percent", "direction") and numeric:
            if ex not in helptext and _with_commas(ex) not in helptext:
                bad.append("%s.%s：說明 %r 未包含範例 %r"
                           % (sheet, fid, helptext, ex))
    assert not bad, "\n".join(bad)


@pytest.mark.parametrize("given, solved", [("X", "Y"), ("Y", "X")])
def test_stats_predict_can_be_reused(given, solved):
    """預測後改已知那格再預測：上次求出的那格要重新當未知數（迴歸測試）。"""
    proc = run_node(["tests/js/helpers/predict_resolve.mjs", given])
    assert proc.returncode == 0, proc.stderr
    steps = json.loads(proc.stdout)
    first = json.loads(call(json.dumps(
        {"sheet": "stats", "action": "predict", "inputs": steps["first"]})))
    assert first["ok"], first
    # 把引擎結果（鍵為小寫 x／y）當成「上次求出」填回去，再改已知那格
    proc2 = run_node(["tests/js/helpers/predict_resolve.mjs", given,
                      json.dumps(first["values"][solved.lower()])])
    assert proc2.returncode == 0, proc2.stderr
    second_inputs = json.loads(proc2.stdout)["second"]
    assert second_inputs[solved] is None, second_inputs
    second = json.loads(call(json.dumps(
        {"sheet": "stats", "action": "predict", "inputs": second_inputs})))
    assert second["ok"], second
    model = {"X": lambda x: 2.2 + 0.6 * x, "Y": lambda y: (y - 2.2) / 0.6}
    assert abs(second["values"][solved.lower()]
               - model[given](second_inputs[given])) < 1e-9


def test_predict_error_field_maps_to_prediction_box():
    """X'、Y' 都填：bridge 回 field "X"，畫面要標在 X' 欄（XP），不是資料清單 X。"""
    res = json.loads(call(json.dumps({
        "sheet": "stats", "action": "predict",
        "inputs": {"model": "LIN", "A": 2.2, "B": 0.6, "X": 6, "Y": 5}})))
    assert not res["ok"]
    proc = run_node(["-e", (
        "import('./web/js/sheets.js').then(m => process.stdout.write("
        "JSON.stringify([m.fieldForKey('stats', %s, 'predict')?.id,"
        " m.fieldForKey('stats', %s, 'two_var')?.id])))")
        % (json.dumps(res["field"]), json.dumps(res["field"]))])
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout) == ["XP", "X"]


def test_tax_presets_mirror_engine():
    """sheets.js 的 TAX_PRESETS（bridge 沒有路由，故鏡射）必須與 engine/business.py 完全相同。"""
    from engine.business import TAX_PRESETS

    proc = run_node(["--input-type=module", "-e",
                     "import('./web/js/sheets.js').then(m =>"
                     " console.log(JSON.stringify(m.TAX_PRESETS)))"])
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout) == TAX_PRESETS
    for name, p in TAX_PRESETS.items():
        assert p["source_url"].startswith("https://"), name
        assert p["checked"], name


@pytest.mark.parametrize("sep", ["us", "eu"])
@pytest.mark.parametrize("decimals", [0, 2, 4])
def test_amort_csv_cells_are_plain_numbers(sep, decimals):
    """匯出 CSV：不論使用者的千分位設定，儲存格都是純數字（引擎以 sep=us 捨入，JS 只去逗號）。"""
    import re
    req = {"sheet": "amort", "action": "schedule",
           "inputs": {"N": 360, "IY": 6, "PV": 250000.0, "PMT": -1498.8757,
                      "FV": 0, "PY": 12, "CY": 12, "BGN": False},
           "settings": {"decimals": decimals, "sep": sep}}
    js = ("import {exportSettings, plainNumberRows} from './web/js/csv.js';"
          "const req = JSON.parse(process.argv[1]);"
          "req.settings = exportSettings(req.settings);"
          "console.log(JSON.stringify(req.settings));")
    proc = run_node(["--input-type=module", "-e", js, json.dumps(req)])
    assert proc.returncode == 0, proc.stderr
    settings = json.loads(proc.stdout)
    assert settings["sep"] == "us" and settings["decimals"] == decimals
    req["settings"] = settings
    resp = json.loads(call(json.dumps(req)))
    assert resp["ok"], resp
    js2 = ("import {plainNumberRows} from './web/js/csv.js';"
           "let t='';process.stdin.on('data',d=>t+=d).on('end',()=>"
           "console.log(JSON.stringify(plainNumberRows(JSON.parse(t)))));")
    proc = run_node(["--input-type=module", "-e", js2],
                    stdin=json.dumps(resp["display"]["rows"]))
    assert proc.returncode == 0, proc.stderr
    rows = json.loads(proc.stdout)
    assert len(rows) == 360
    for row in rows:
        for cell in row:
            assert re.fullmatch(r"-?\d+(\.\d+)?", cell), cell
