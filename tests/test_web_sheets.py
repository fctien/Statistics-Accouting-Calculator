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


def _close(got, want):
    """example 是四捨五入過的數字：允許 0.05 或 0.5% 的差距。"""
    return abs(got - want) <= max(0.051, 0.005 * abs(want))


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
                want = float(ex.replace(",", ""))
                got = abs(val) if f["kind"] == "direction" else val
                ok = _close(got, want)
            if not ok:
                problems.append("%s：%s 範例 %r，引擎算出 %r" % (name, key, ex, val))
    assert not problems, "\n".join(problems)


def test_sheet_actions_cover_bridge_routes(requests):
    """bridge 的每個路由都有對應的工作表動作（UI 不會漏功能）。"""
    from engine.bridge import ROUTES
    have = {(r["engine"], r["action"]) for r in requests if r["engine"]}
    assert set(ROUTES) <= have, sorted(set(ROUTES) - have)
