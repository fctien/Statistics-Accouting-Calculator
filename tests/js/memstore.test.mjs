// memstore.js 測試：語意須與 engine/memory.py 一致（STO／RCL／M±／M×／M÷、除以零不變、Σ）。
import test from "node:test";
import assert from "node:assert/strict";

import { createMemStore, fromJSON } from "../../web/js/memstore.js";

test("初始全 0；STO／RCL", () => {
  const m = createMemStore();
  assert.deepEqual(m.values(), new Array(10).fill(0));
  assert.deepEqual(m.store(3, 12.5), { ok: true, value: 12.5 });
  assert.deepEqual(m.recall(3), { ok: true, value: 12.5 });
  assert.equal(m.recall(4).value, 0);
});

test("M+ M− M× M÷", () => {
  const m = createMemStore();
  m.store(0, 10);
  assert.equal(m.add(0, 5).value, 15);
  assert.equal(m.sub(0, 3).value, 12);
  assert.equal(m.mul(0, 2).value, 24);
  assert.equal(m.div(0, 8).value, 3);
  assert.equal(m.recall(0).value, 3);
});

test("M÷0 回錯誤且記憶不變", () => {
  const m = createMemStore();
  m.store(2, 7);
  const r = m.div(2, 0);
  assert.equal(r.ok, false);
  assert.match(r.error, /除以零/);
  assert.equal(m.recall(2).value, 7);
});

test("溢位回錯誤且記憶不變", () => {
  const m = createMemStore();
  m.store(1, 1e300);
  const r = m.mul(1, 1e300);
  assert.equal(r.ok, false);
  assert.equal(m.recall(1).value, 1e300);
});

test("編號與數值驗證", () => {
  const m = createMemStore();
  for (const i of [-1, 10, 1.5, "1", null]) assert.equal(m.store(i, 1).ok, false, String(i));
  for (const x of [NaN, Infinity, "3", null, undefined]) assert.equal(m.store(0, x).ok, false, String(x));
  assert.equal(m.recall(10).ok, false);
  assert.equal(m.recall(0).value, 0);
});

test("累加器 Σ：sum 與 count；溢位不變", () => {
  const m = createMemStore();
  assert.deepEqual(m.accumulate(2.5), { ok: true, sum: 2.5, count: 1 });
  m.accumulate(-1);
  assert.equal(m.sum, 1.5);
  assert.equal(m.count, 2);
  m.accumulate(1.7e308);
  const r = m.accumulate(1.7e308);
  assert.equal(r.ok, false);
  assert.equal(m.count, 3);
  m.clearAccumulator();
  assert.equal(m.sum, 0);
  assert.equal(m.count, 0);
});

test("toEngineMem 形狀；toJSON／fromJSON 來回一致", () => {
  const m = createMemStore();
  m.store(5, 3.25);
  m.accumulate(4);
  const em = m.toEngineMem();
  assert.equal(Object.keys(em).length, 10);
  assert.equal(em.M5, 3.25);
  const j = JSON.parse(JSON.stringify(m.toJSON()));
  assert.deepEqual(j.ACC, { sum: 4, count: 1 });
  const back = fromJSON(j);
  assert.deepEqual(back.toJSON(), m.toJSON());
});

test("fromJSON：壞資料忽略、保持 0", () => {
  const m = fromJSON({ M0: "x", M1: NaN, M2: 4, M99: 1, ACC: { sum: 1, count: -2 } });
  assert.equal(m.recall(0).value, 0);
  assert.equal(m.recall(1).value, 0);
  assert.equal(m.recall(2).value, 4);
  assert.equal(m.count, 0);
  assert.equal(fromJSON(null).recall(0).value, 0);
  assert.equal(fromJSON(42).count, 0);
});

test("clearAll", () => {
  const m = createMemStore();
  m.store(9, 1);
  m.accumulate(1);
  m.clearAll();
  assert.deepEqual(m.values(), new Array(10).fill(0));
  assert.equal(m.count, 0);
});
