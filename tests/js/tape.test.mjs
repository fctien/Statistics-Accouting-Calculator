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
  t.setDisplay(0, "3.0000");
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
