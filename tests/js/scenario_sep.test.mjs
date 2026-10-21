// 情境與千分位設定（separator, sep）：情境存的是使用者打的原始文字，換了 US／EU 設定後
// 不可用新設定重新解讀（"100,000" 在 EU 會變成 100）。prepareScenarioForLoad 依情境記錄的 sep
// 換算成目前設定的寫法；無法確定的值標為錯誤，絕不默默套用。
import test from "node:test";
import assert from "node:assert/strict";

import { prepareScenarioForLoad, normalizeData, emptyData } from "../../web/js/storage/backup.js";
import { collect, convertSepText } from "../../web/js/input.js";
import { SHEETS } from "../../web/js/sheets.js";
import { readStatTable } from "../../web/js/tables.js";

const kindsOf = (ws) => Object.fromEntries(SHEETS[ws].fields.filter((f) => !f.output).map((f) => [f.id, f]));
const valuesOf = (inputs) => Object.fromEntries(Object.entries(inputs)
  .filter(([k]) => k !== "__grid")
  .map(([k, st]) => [k, "direction" in st ? { text: st.text, direction: st.direction } : st.text]));

test("重現：US 存的 100,000 在 EU 設定下直接解讀會變成 100（修正前的行為）", () => {
  const { inputs } = collect({ PV: { text: "100,000", direction: "out" } }, { PV: "direction" }, "eu");
  assert.equal(inputs.PV, -100); // 這就是錯誤：所以載入時必須先換算
});

test("prepareScenarioForLoad：US 情境在 EU 設定下載入，文字換成 EU 寫法、數值不變", () => {
  const sc = {
    id: "a", worksheet: "tvm", name: "A", sep: "us", updated_at: "2026-10-21T10:00:00+08:00",
    inputs: {
      N: { text: "360" }, IY: { text: "6.5%" }, PV: { text: "100,000", direction: "out" },
      PMT: { text: "" , direction: "in" }, FV: { text: "1,234.5", direction: "in" }, BGN: { checked: false },
    },
  };
  const r = prepareScenarioForLoad(sc, "eu");
  assert.deepEqual(r.errors, {});
  assert.equal(r.gridError, null);
  assert.equal(r.inputs.PV.text, "100000");
  assert.equal(r.inputs.FV.text, "1234,5");
  assert.equal(r.inputs.IY.text, "6,5%");
  assert.deepEqual(r.inputs.BGN, { checked: false });
  const { inputs, errors } = collect(valuesOf(r.inputs), kindsOf("tvm"), "eu");
  assert.deepEqual(errors, {});
  assert.equal(inputs.PV, -100000);
  assert.equal(inputs.FV, 1234.5);
  assert.equal(inputs.IY, 6.5);
  // 同一設定：原樣，不改寫
  assert.equal(prepareScenarioForLoad(sc, "us").inputs.PV.text, "100,000");
});

test("prepareScenarioForLoad：EU 情境在 US 設定下載入；清單欄位也換算", () => {
  const sc = {
    id: "b", worksheet: "cashflow", name: "B", sep: "eu", updated_at: "x",
    inputs: { CF0: { text: "1.000,5", direction: "out" }, flows: { text: "300 x 2\n2,5" } },
  };
  const r = prepareScenarioForLoad(sc, "us");
  assert.deepEqual(r.errors, {});
  assert.equal(r.inputs.CF0.text, "1000.5");
  const { inputs, errors } = collect(valuesOf(r.inputs), kindsOf("cashflow"), "us");
  assert.deepEqual(errors, {});
  assert.equal(inputs.CF0, -1000.5);
});

test("prepareScenarioForLoad：情境 sep 下就解不出的值 → 該欄位標錯誤，不套用", () => {
  const sc = { id: "c", worksheet: "tvm", name: "C", sep: "us", updated_at: "x", inputs: { N: { text: "1,5" } } };
  const r = prepareScenarioForLoad(sc, "eu");
  assert.ok(r.errors.N, "1,5 在 US 不合法，不可在 EU 下變成 1.5");
});

test("prepareScenarioForLoad：沒有 sep 的舊／匯入情境，兩種寫法同值才接受，否則標錯誤", () => {
  const sc = {
    id: "d", worksheet: "tvm", name: "D", updated_at: "x",
    inputs: { N: { text: "360" }, PV: { text: "100,000", direction: "out" }, FV: { text: "1.5", direction: "in" } },
  };
  for (const cur of ["us", "eu"]) {
    const r = prepareScenarioForLoad(sc, cur);
    assert.equal(r.inputs.N.text, "360");
    assert.ok(r.errors.PV, `${cur}: 100,000 意義不明`);
    assert.ok(r.errors.FV, `${cur}: 1.5 意義不明`);
    assert.equal(r.errors.N, undefined);
  }
  // 有引擎完整精度 exact 時用 exact 改寫，不需要猜
  const withExact = { ...sc, inputs: { PV: { text: "100,000.00", direction: "out", exact: -100000 } } };
  const r = prepareScenarioForLoad(withExact, "eu");
  assert.deepEqual(r.errors, {});
  assert.equal(r.inputs.PV.text, "100000");
  assert.equal(r.inputs.PV.exact, -100000);
});

test("prepareScenarioForLoad：表格（STAT／CF）依 sep 換算；無法確定時 gridError，不套用", () => {
  const grid = [["1,000", "2.5", ""], ["2", "4", ""]];
  const us = prepareScenarioForLoad({ id: "e", worksheet: "stats", name: "E", sep: "us", updated_at: "x", inputs: { __grid: grid } }, "eu");
  assert.equal(us.gridError, null);
  assert.deepEqual(us.inputs.__grid, [["1000", "2,5", ""], ["2", "4", ""]]);
  const t = readStatTable(us.inputs.__grid, "two_var", "eu");
  assert.ok(!t.error, JSON.stringify(t));
  assert.equal(t.X[0], 1000);
  const none = prepareScenarioForLoad({ id: "f", worksheet: "stats", name: "F", updated_at: "x", inputs: { __grid: grid } }, "eu");
  assert.ok(none.gridError);
  const bad = prepareScenarioForLoad({ id: "g", worksheet: "stats", name: "G", sep: "eu", updated_at: "x", inputs: { __grid: [["1.0.0"]] } }, "us");
  assert.ok(bad.gridError);
});

test("convertSepText：數字、百分比、方向（含正負號）、清單", () => {
  const num = { kind: "number" };
  assert.deepEqual(convertSepText("1,234.5", num, "us", "eu"), { text: "1234,5" });
  assert.deepEqual(convertSepText("1.234,5", num, "eu", "us"), { text: "1234.5" });
  assert.deepEqual(convertSepText("", num, "us", "eu"), { text: "" });
  assert.ok(convertSepText("abc", num, "us", "eu").error);
  assert.deepEqual(convertSepText("-1,000", { kind: "direction" }, "us", "eu"), { text: "-1000" });
  assert.deepEqual(convertSepText("5.25%", { kind: "percent" }, "us", "eu"), { text: "5,25%" });
  assert.deepEqual(convertSepText("1.5 2,000", { kind: "list" }, "us", "eu"), { text: "1,5 2000" });
});

test("normalizeData：情境的 sep 只留 us／eu", () => {
  const base = { ...emptyData() };
  const mk = (sep) => ({ id: "s" + sep, worksheet: "tvm", name: "n", inputs: {}, updated_at: "x", sep });
  const d = normalizeData({ ...base, scenarios: [mk("us"), mk("eu"), mk("xx")] });
  assert.equal(d.scenarios[0].sep, "us");
  assert.equal(d.scenarios[1].sep, "eu");
  assert.equal("sep" in d.scenarios[2], false);
});
