// tape.js 測試：500 筆上限、歷史瀏覽、JSON 還原。
import test from "node:test";
import assert from "node:assert/strict";

import { createTape, createWalker, MAX_ENTRIES } from "../../web/js/tape.js";

const add = (t, n) => t.add({ expr: `${n}+0`, value: n, display: String(n), ts: n });

test("上限 500：超過時捨棄最舊", () => {
  assert.equal(MAX_ENTRIES, 500);
  const t = createTape();
  for (let i = 1; i <= 505; i++) add(t, i);
  assert.equal(t.length, 500);
  assert.equal(t.at(0).value, 6);
  assert.equal(t.last().value, 505);
});

test("自訂上限、clear、setDisplay", () => {
  const t = createTape(3);
  for (let i = 1; i <= 5; i++) add(t, i);
  assert.deepEqual(t.list().map((e) => e.value), [3, 4, 5]);
  assert.equal(t.setDisplayById(t.at(0).id, "3.0000"), true);
  assert.equal(t.at(0).display, "3.0000");
  t.clear();
  assert.equal(t.length, 0);
  assert.equal(t.last(), null);
});

test("walker：上鍵往舊、下鍵往新並回到草稿", () => {
  const t = createTape();
  const w = createWalker(t);
  assert.equal(w.prev("abc"), null); // 空紙帶
  add(t, 1);
  add(t, 2);
  add(t, 3);
  assert.equal(w.prev("draft"), "3+0");
  assert.equal(w.prev("ignored"), "2+0");
  assert.equal(w.prev("ignored"), "1+0");
  assert.equal(w.prev("ignored"), null); // 已到最舊
  assert.equal(w.next(), "2+0");
  assert.equal(w.next(), "3+0");
  assert.equal(w.next(), "draft");
  assert.equal(w.next(), null); // 已在草稿位置
});

test("walker.reset：新增項目後重新從最新開始", () => {
  const t = createTape();
  const w = createWalker(t);
  add(t, 1);
  assert.equal(w.prev("x"), "1+0");
  add(t, 2);
  w.reset();
  assert.equal(w.prev("y"), "2+0");
  assert.equal(w.next(), "y");
});

test("toJSON／init 還原；壞項目略過", () => {
  const t = createTape();
  add(t, 1);
  add(t, 2);
  const j = JSON.parse(JSON.stringify(t.toJSON()));
  const t2 = createTape(500, [...j, { expr: 5, value: 1 }, { expr: "x", value: NaN }, null]);
  assert.deepEqual(t2.toJSON(), t.toJSON());
});

test("setDisplayById：以編號認人，項目被裁掉或清除後不會寫到別的項目", () => {
  const t = createTape(2);
  const a = add(t, 1);
  add(t, 2);
  add(t, 3); // 裁掉 a
  assert.equal(t.setDisplayById(a.id, "WRONG"), false);
  assert.deepEqual(t.list().map((e) => e.display), ["2", "3"]);
  const b = t.at(0);
  t.clear();
  const c = add(t, 9);
  assert.equal(t.setDisplayById(b.id, "WRONG"), false);
  assert.equal(c.display, "9");
  assert.notEqual(b.id, c.id);
});

test("toJSON 不含內部編號", () => {
  const t = createTape();
  add(t, 1);
  assert.deepEqual(Object.keys(t.toJSON()[0]).sort(), ["display", "expr", "ts", "value"]);
});

test("角度：只有含三角函數的算式記 angle；toJSON／還原保留合法值、丟掉不合法值", () => {
  const t = createTape();
  const a = t.add({ expr: "sin(30)", value: 0.5, display: "0.50", ts: 1, angle: "DEG" });
  const b = t.add({ expr: "2+3", value: 5, display: "5.00", ts: 2, angle: "RAD" });
  const c = t.add({ expr: "atan(1)", value: 0.785, display: "0.79", ts: 3, angle: "GRAD" });
  assert.equal(a.angle, "DEG");
  assert.equal(b.angle, undefined, "沒有三角函數：角度無關");
  assert.equal(c.angle, undefined, "不合法的角度不存");
  const json = t.toJSON();
  assert.deepEqual(json[0], { expr: "sin(30)", value: 0.5, display: "0.50", ts: 1, angle: "DEG" });
  assert.ok(!("angle" in json[1]));
  const back = createTape(MAX_ENTRIES, [...json, { expr: "cos(0)", value: 1, display: "1", ts: 4, angle: 5 }]);
  assert.equal(back.at(0).angle, "DEG");
  assert.equal(back.at(3).angle, undefined);
});

test("usesTrig 與 angleStatus：無關／角度未知／過期／目前", async () => {
  const { usesTrig, angleStatus } = await import("../../web/js/tape.js");
  assert.equal(usesTrig("sin(30)"), true);
  assert.equal(usesTrig("2×asin(0.5)"), true);
  assert.equal(usesTrig("ATAN (1)"), false, "引擎識別字區分大小寫");
  assert.equal(usesTrig("cosh"), false);
  assert.equal(usesTrig("√(2)+ln(e)"), false);
  assert.equal(angleStatus({ expr: "2+3" }, "RAD"), null);
  assert.equal(angleStatus({ expr: "sin(30)" }, "RAD"), "unknown", "舊紙帶沒有 angle");
  assert.equal(angleStatus({ expr: "sin(30)", angle: "DEG" }, "RAD"), "stale");
  assert.equal(angleStatus({ expr: "sin(30)", angle: "RAD" }, "RAD"), "current");
});
