// sheets.js 結構測試：每張工作表、每個欄位都有完整的說明資料，動作引用的欄位都存在。
// 欄位 id 與 engine/bridge.py 鍵對照表是否一致，由 tests/test_web_sheets.py 實際呼叫 bridge 驗證。
import test from "node:test";
import assert from "node:assert/strict";

import { SHEETS, SHEET_ORDER, PRIMARY_SHEETS, KINDS, fieldMap, sendFields } from "../../web/js/sheets.js";

const REQUIRED_SHEETS = [
  "tvm", "amort", "cashflow", "iconv", "stats", "bond", "depr", "business-profit",
  "business-breakeven", "business-pct", "tax", "date", "calc", "settings",
];

test("所有規定的工作表都存在，順序表與主要分頁一致", () => {
  assert.deepEqual([...SHEET_ORDER].sort(), [...REQUIRED_SHEETS].sort());
  assert.deepEqual(Object.keys(SHEETS).sort(), [...REQUIRED_SHEETS].sort());
  assert.equal(PRIMARY_SHEETS.length, 5);
  for (const id of PRIMARY_SHEETS) assert.ok(id in SHEETS, id);
});

test("路由（hash）唯一且為小寫英數", () => {
  const routes = SHEET_ORDER.map((id) => SHEETS[id].route);
  assert.equal(new Set(routes).size, routes.length);
  for (const r of routes) assert.match(r, /^[a-z][a-z0-9-]*$/);
  assert.equal(SHEETS.cashflow.route, "cf");
  assert.equal(SHEETS.tvm.route, "tvm");
});

test("每個欄位都有 id、繁中 label、abbr、kind、help（含範例）、example", () => {
  for (const id of SHEET_ORDER) {
    const sheet = SHEETS[id];
    assert.ok(sheet.title && sheet.short, `${id} 缺 title/short`);
    const seen = new Set();
    for (const f of sheet.fields) {
      const where = `${id}.${f.id}`;
      assert.ok(!seen.has(f.id), `${where} 重複`);
      seen.add(f.id);
      assert.match(f.id, /^[A-Za-z][A-Za-z0-9_]*$/, where);
      assert.match(f.label, /[一-鿿]/, `${where} label 要繁中`);
      assert.ok(typeof f.abbr === "string" && f.abbr.length > 0, `${where} abbr`);
      assert.ok(KINDS.includes(f.kind), `${where} kind=${f.kind}`);
      assert.ok(typeof f.unit === "string", `${where} unit`);
      assert.match(f.help, /例/, `${where} help 要有具體例子`);
      assert.ok(!f.help.includes("\n"), `${where} help 一行`);
      assert.ok(typeof f.example === "string" && f.example.length > 0, `${where} example`);
      if (f.kind === "select") {
        assert.ok(Array.isArray(f.options) && f.options.length > 0, `${where} options`);
        for (const o of f.options) assert.ok("value" in o && o.label, `${where} option`);
      }
    }
  }
});

test("每張工作表恰有一個主要動作（Enter），動作引用的欄位都存在", () => {
  for (const id of SHEET_ORDER) {
    const sheet = SHEETS[id];
    assert.ok(sheet.actions.length >= 1, id);
    assert.equal(sheet.actions.filter((a) => a.primary).length, 1, `${id} primary`);
    const fm = fieldMap(id);
    for (const a of sheet.actions) {
      assert.ok(a.id && a.label, `${id} action`);
      for (const fid of a.send || []) assert.ok(fid in fm, `${id}.${a.id} 送出未知欄位 ${fid}`);
      const keys = sendFields(id, a.id).map((f) => f.key || f.id);
      for (const k of a.solve || []) assert.ok(keys.includes(k), `${id}.${a.id} solve 未知鍵 ${k}`);
      for (const f of sendFields(id, a.id)) assert.ok(!f.output, `${id}.${a.id} 不可送出輸出欄位 ${f.id}`);
    }
  }
});

test("TVM 欄位 id 與 bridge 鍵對照表完全相同", () => {
  const ids = SHEETS.tvm.fields.map((f) => f.id);
  assert.deepEqual(ids, ["N", "IY", "PV", "PMT", "FV", "PY", "CY", "BGN"]);
  const fm = fieldMap("tvm");
  assert.equal(fm.IY.kind, "percent");
  for (const k of ["PV", "PMT", "FV"]) assert.equal(fm[k].kind, "direction");
  assert.equal(fm.BGN.kind, "bool");
  assert.equal(SHEETS.tvm.engine, "tvm");
});

test("留一格空白的動作都標了 solve", () => {
  assert.deepEqual(SHEETS.tvm.actions[0].solve, ["N", "IY", "PV", "PMT", "FV"]);
  for (const id of ["business-profit", "business-breakeven", "business-pct", "date"]) {
    assert.ok(Array.isArray(SHEETS[id].actions[0].solve), id);
  }
});
