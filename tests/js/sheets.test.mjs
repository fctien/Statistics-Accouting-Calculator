// sheets.js 結構測試：每張工作表、每個欄位都有完整的說明資料，動作引用的欄位都存在。
// 欄位 id 與 engine/bridge.py 鍵對照表是否一致，由 tests/test_web_sheets.py 實際呼叫 bridge 驗證。
import test from "node:test";
import assert from "node:assert/strict";

import {
  SHEETS, SHEET_ORDER, PRIMARY_SHEETS, KINDS, fieldMap, sendFields, fieldForKey,
  staleBlock, staleAfterSuccess, staleAfterEdit,
} from "../../web/js/sheets.js";

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
  // STAT 預測：X'／Y' 恰給其一，求出的那格下次要重算（引擎鍵 X、Y）
  assert.deepEqual(SHEETS.stats.actions.find((x) => x.id === "predict").solve, ["X", "Y"]);
});

test("fieldForKey：先在剛執行的動作欄位中找，再全域找", () => {
  const id = (sheet, key, action) => fieldForKey(sheet, key, action)?.id ?? null;
  // STAT 預測的錯誤 field "X"／"Y" 指的是 X'／Y' 欄，不是資料清單
  assert.equal(id("stats", "X", "predict"), "XP");
  assert.equal(id("stats", "Y", "predict"), "YP");
  // 迴歸、單變數的 "X"／"Y" 是資料清單
  assert.equal(id("stats", "X", "two_var"), "X");
  assert.equal(id("stats", "Y", "two_var"), "Y");
  assert.equal(id("stats", "X", "one_var"), "X");
  // 回傳值鍵（out）：預測的 x／y、迴歸的 a／b（不在 two_var 的送出欄位 → 全域）
  assert.equal(id("stats", "y", "predict"), "YP");
  assert.equal(id("stats", "a", "two_var"), "A");
  // 沒給動作：維持全域順序
  assert.equal(id("stats", "X"), "X");
  // 別名與不分大小寫
  assert.equal(id("cashflow", "CF", "pb"), "CF0");
  assert.equal(id("tax", "amount", "tax"), "AMOUNT");
  assert.equal(id("calc", "expr", "eval"), "EXPR");
  assert.equal(id("tvm", "PMT", "solve"), "PMT");
  assert.equal(id("tvm", "nope", "solve"), null);
  assert.equal(id("tvm", null, "solve"), null);
});

test("STAT 預測：a、b 是過期（stale）的迴歸係數時拒絕計算，訊息要求重新計算迴歸", () => {
  // 重現：LIN 迴歸 a=2.2 b=0.6 → 改模型為 EXP（a、b 標過期）→ 預測會用 LIN 係數算出 Y'
  const block = staleBlock("stats", "predict", ["A", "B"]);
  assert.ok(block, "a、b 過期必須擋下");
  assert.match(block.message, /請先重新計算迴歸/);
  assert.deepEqual(block.fields, ["A", "B"]);
  assert.ok(staleBlock("stats", "predict", ["B"]), "只有 b 過期也要擋");
  assert.equal(staleBlock("stats", "predict", []), null);
  assert.equal(staleBlock("stats", "predict", ["XP"]), null, "X' 過期不影響：它會被重新求出");
  // 其他動作不受影響（迴歸本身就是重新計算 a、b）
  assert.equal(staleBlock("stats", "two_var", ["A", "B"]), null);
  assert.equal(staleBlock("tvm", "solve", ["PMT"]), null);
});

test("成功計算後只解除這次回應求出／填入欄位的過期標記", () => {
  // 以前 clearStale 把全部過期欄位都變回綠色：預測成功後 a、b 也被「洗白」
  assert.deepEqual(staleAfterSuccess(["A", "B", "YP"], ["YP"]), ["A", "B"]);
  assert.deepEqual(staleAfterSuccess(["PMT"], ["PMT"]), []);
  assert.deepEqual(staleAfterSuccess(["A"], []), ["A"]);
  assert.deepEqual(staleAfterSuccess([], ["A"]), []);
});

test("A0：成功計算後清除「送出欄位 ∪ 填入欄位」的過期標記（TVM 6 步驟）", () => {
  // 步驟 4～5：PMT 曾為過期，使用者手改後（onEdited 已移除標記）；
  // 即使殘留，PMT 在 solve 的送出欄位中，成功計算後必須解除
  const sent = sendFields("tvm", "solve").map((f) => f.id);
  assert.ok(sent.includes("PMT"));
  assert.deepEqual(staleAfterSuccess(["PMT"], ["FV"], sent), []);
  assert.deepEqual(staleAfterSuccess(["PMT", "N"], ["FV"], sent), []);
});

test("A0：STAT 防護不受影響——預測被擋，one_var 不洗白 A、B", () => {
  // 改 EXP 後 A、B 過期：預測仍被擋
  assert.ok(staleBlock("stats", "predict", ["A", "B"]));
  // one_var 只送出 X、F：A、B 不在送出欄位，成功後仍維持過期
  const sent = sendFields("stats", "one_var").map((f) => f.id);
  assert.deepEqual(staleAfterSuccess(["A", "B"], ["MEAN"], sent), ["A", "B"]);
  // two_var 送出 X、Y、model，A、B 由此次填入而解除
  const sent2 = sendFields("stats", "two_var").map((f) => f.id);
  assert.deepEqual(staleAfterSuccess(["A", "B"], ["A", "B"], sent2), []);
});

test("A0：使用者編輯欄位後，該欄位的過期標記移除，其他不動", () => {
  assert.deepEqual(staleAfterEdit(["PMT", "N"], "PMT"), ["N"]);
  assert.deepEqual(staleAfterEdit(["A", "B"], "XP"), ["A", "B"], "編輯別的欄位不洗白 A、B");
  assert.deepEqual(staleAfterEdit([], "PMT"), []);
});
