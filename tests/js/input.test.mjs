// input.js 單元測試（node --test，不需 DOM）：
// collect 空白→null、US／EU 千分位、全形數字、百分比、錯誤訊息、方向（收到／付出）轉換。
import test from "node:test";
import assert from "node:assert/strict";

import {
  collect, parseNumber, parsePercent, parseDate, parseList, toSigned, fromSigned, splitSign,
  resolveBlanks,
} from "../../web/js/input.js";

const NUM = { kind: "number", label: "期數" };

test("collect：空白、只有空白字元、undefined 都變成 null", () => {
  const { inputs, errors } = collect(
    { N: "", IY: "   ", PV: undefined, FV: null },
    { N: "number", IY: "percent", PV: "number", FV: "number" },
  );
  assert.deepEqual(inputs, { N: null, IY: null, PV: null, FV: null });
  assert.deepEqual(errors, {});
});

test("collect：US 分隔（預設）", () => {
  const { inputs, errors } = collect(
    { A: "1,000", B: "1,234.56", C: "1e3", D: "-0.5", E: ".5", F: "+7" },
    { A: NUM, B: NUM, C: NUM, D: NUM, E: NUM, F: NUM },
  );
  assert.deepEqual(errors, {});
  assert.deepEqual(inputs, { A: 1000, B: 1234.56, C: 1000, D: -0.5, E: 0.5, F: 7 });
});

test("collect：EU 分隔（1.234,56）", () => {
  const { inputs, errors } = collect(
    { A: "1.234,56", B: "1000", C: "2,5" },
    { A: "number", B: "number", C: "number" }, "eu",
  );
  assert.deepEqual(errors, {});
  assert.deepEqual(inputs, { A: 1234.56, B: 1000, C: 2.5 });
  // US 寫法在 EU 模式下不合法（1,234.56 → 小數點是逗號）
  assert.ok("A" in collect({ A: "1,234.56" }, { A: "number" }, "eu").errors);
});

test("collect：全形數字與全形負號", () => {
  const { inputs, errors } = collect(
    { A: "１２３", B: "－１，０００．５" },
    { A: "number", B: "number" },
  );
  assert.equal(inputs.A, 123);
  assert.ok(!("A" in errors));
  // 全形逗號／句點不在引擎規則內 → 錯誤（與 fmt.parse_number 一致）
  assert.ok("B" in errors);
  assert.equal(collect({ C: "－１０００" }, { C: "number" }).inputs.C, -1000);
});

test("collect：百分比有無 % 都代表百分數", () => {
  const { inputs, errors } = collect(
    { A: "5", B: "5%", C: " 6.5 % ", D: "５％", E: "" },
    { A: "percent", B: "percent", C: "percent", D: "percent", E: "percent" },
  );
  assert.deepEqual(errors, {});
  assert.deepEqual(inputs, { A: 5, B: 5, C: 6.5, D: 5, E: null });
});

test("collect：無法解析的文字 → errors[id] 中文訊息，inputs 不含錯誤值", () => {
  const { inputs, errors } = collect(
    { N: "abc", IY: "5%%", PV: "1,00", FV: "12" },
    { N: { kind: "number", label: "期數" }, IY: "percent", PV: "number", FV: "number" },
  );
  assert.deepEqual(Object.keys(errors).sort(), ["IY", "N", "PV"]);
  assert.match(errors.N, /期數/);
  assert.match(errors.N, /[一-鿿]/);
  assert.equal(inputs.FV, 12);
  assert.equal(inputs.N, null);
});

test("collect：欄位限制 positive／integer", () => {
  const kinds = {
    PY: { kind: "number", label: "每年付款次數", positive: true },
    YR: { kind: "number", label: "年度", integer: true },
  };
  const bad = collect({ PY: "0", YR: "1.5" }, kinds);
  assert.ok("PY" in bad.errors && "YR" in bad.errors);
  const good = collect({ PY: "12", YR: "3" }, kinds);
  assert.deepEqual(good.errors, {});
});

test("collect：direction 欄位用收到／付出決定正負號", () => {
  const kinds = { PV: "direction", PMT: "direction", FV: "direction" };
  const { inputs, errors } = collect({
    PV: { text: "100,000", direction: "in" },
    PMT: { text: "599.55", direction: "out" },
    FV: { text: "", direction: "out" },
  }, kinds);
  assert.deepEqual(errors, {});
  assert.deepEqual(inputs, { PV: 100000, PMT: -599.55, FV: null });
  // 純字串（TI 正負號）也接受
  assert.equal(collect({ PV: "-5" }, kinds).inputs.PV, -5);
});

test("collect：select、bool、date、list、key 別名", () => {
  const kinds = {
    basis: { kind: "select", options: [{ value: "ACT" }, { value: "360" }] },
    freq: { kind: "select", options: [{ value: 1 }, { value: 2 }] },
    BGN: "bool",
    SDT: "date",
    X: "list",
    XP: { kind: "number", key: "X'" },
  };
  const { inputs, errors } = collect({
    basis: "360", freq: "2", BGN: true, SDT: "2026-10-20", X: "1, 2\n3;4", XP: "9",
  }, kinds);
  assert.deepEqual(errors, {});
  assert.deepEqual(inputs, {
    basis: "360", freq: 2, BGN: true, SDT: [2026, 10, 20], X: [1, 2, 3, 4], "X'": 9,
  });
  const bad = collect({ basis: "XYZ", SDT: "2026-02-30" }, kinds);
  assert.ok("basis" in bad.errors && "SDT" in bad.errors);
});

test("parseNumber 與引擎 fmt.parse_number 規則一致（代表案例）", () => {
  const cases = [
    ["1,000", "us", 1000], ["1,0000", "us", null], ["12,345,678.9", "us", 12345678.9],
    ["1e3", "us", 1000], ["1E-2", "us", 0.01], ["1e", "us", null], ["e5", "us", null],
    ["1.2.3", "us", null], ["", "us", null], ["-", "us", null], ["1e400", "us", null],
    ["1.000.000,25", "eu", 1000000.25], ["0,5", "eu", 0.5], ["abc", "us", null],
    ["  42  ", "us", 42], ["5.", "us", 5], ["1 000", "us", null], ["Infinity", "us", null],
  ];
  for (const [text, sep, want] of cases) {
    assert.equal(parseNumber(text, sep), want, `${text} (${sep})`);
  }
});

test("parsePercent、parseDate、parseList 個別行為", () => {
  assert.equal(parsePercent("12.5%"), 12.5);
  assert.equal(parsePercent("%"), null);
  assert.deepEqual(parseDate("2024/2/29"), [2024, 2, 29]);
  assert.equal(parseDate("2023-02-29"), null);
  assert.equal(parseDate("2026-13-01"), null);
  assert.deepEqual(parseList("1,5 2,5", "eu"), [1.5, 2.5]);
  assert.deepEqual(parseList("1,000 2,000", "us"), [1000, 2000]);
  assert.deepEqual(parseList("300 x 2; 400", "us", true), [[300, 2], [400, 1]]);
  assert.equal(parseList("1 abc", "us"), null);
});

test("toSigned／fromSigned：收到為正、付出為負", () => {
  assert.equal(toSigned(100, "in"), 100);
  assert.equal(toSigned(100, "out"), -100);
  assert.equal(toSigned(-100, "in"), 100);
  assert.equal(toSigned(-100, "out"), -100);
  assert.ok(Object.is(toSigned(0, "out"), 0));
  assert.equal(toSigned(null, "out"), null);
  assert.deepEqual(fromSigned(-599.55), { value: 599.55, direction: "out" });
  assert.deepEqual(fromSigned(250), { value: 250, direction: "in" });
  assert.deepEqual(fromSigned(0), { value: 0, direction: "in" });
  assert.deepEqual(fromSigned(null), { value: null, direction: null });
  for (const v of [-3.25, 0, 7]) {
    const { value, direction } = fromSigned(v);
    assert.equal(toSigned(value, direction), v);
  }
  assert.throws(() => toSigned(1, "sideways"));
});

test("resolveBlanks：沒有空白時，上次求出且未改動的欄位再次當未知數", () => {
  const solve = ["N", "IY", "PV", "PMT", "FV"];
  const full = { N: 240, IY: 6, PV: 100000, PMT: -599.55, FV: 0, PY: 12 };
  assert.deepEqual(resolveBlanks(full, solve, ["PMT"]), { ...full, PMT: null });
  // 使用者已留空另一格：照使用者的意思，不動
  const oneBlank = { ...full, N: null };
  assert.deepEqual(resolveBlanks(oneBlank, solve, ["PMT"]), oneBlank);
  // 沒有求出過的欄位：不動（引擎會回「請只留一格空白」）
  assert.deepEqual(resolveBlanks(full, solve, []), full);
  // 求出欄位不在可求解清單（例：PY）：不動
  assert.deepEqual(resolveBlanks(full, solve, ["PY"]), full);
  // 沒有 solve 規則的動作：不動；不改原物件
  assert.equal(resolveBlanks(full, undefined, ["PMT"]), full);
  assert.equal(full.PMT, -599.55);
  // PROFIT 一次求出兩格（SEL、MAR）
  const p = { CST: 80, SEL: 100, MAR: 20, MU: 25 };
  assert.deepEqual(resolveBlanks(p, ["CST", "SEL", "MAR", "MU"], ["SEL", "MAR"]),
    { CST: 80, SEL: null, MAR: null, MU: 25 });
});

test("collect：direction 欄位打入的正負號優先於方向鈕（Enter 直接送出也一樣）", () => {
  // 重現：PV 打「-100000」按 Enter，方向鈕仍是「收到」→ 以前被 Math.abs 翻成 +100000
  const kinds = { PV: "direction", FV: "direction", PMT: "direction" };
  const { inputs, errors, directions } = collect({
    PV: { text: "-500", direction: "in" },
    FV: { text: "+250", direction: "out" },
    PMT: { text: "－1,000", direction: "in" }, // 全形負號
  }, kinds);
  assert.deepEqual(errors, {});
  assert.equal(inputs.PV, -500);
  assert.equal(inputs.FV, 250);
  assert.equal(inputs.PMT, -1000);
  assert.deepEqual(directions, { PV: "out", FV: "in", PMT: "out" });
  // 沒有打正負號：仍由方向鈕決定，directions 不列出
  const r2 = collect({ PV: { text: "500", direction: "out" } }, { PV: "direction" });
  assert.equal(r2.inputs.PV, -500);
  assert.deepEqual(r2.directions, {});
  // 只有符號或兩個符號：格式錯誤，不可默默變成某個數字
  for (const text of ["-", "--5", "-+5", "+ -5"]) {
    const r = collect({ PV: { text, direction: "in" } }, { PV: "direction" });
    assert.ok(r.errors.PV, text);
    assert.equal(r.inputs.PV, null, text);
  }
});

test("splitSign：拆出開頭的正負號（含全形）與其後空白", () => {
  assert.deepEqual(splitSign("-100000"), { text: "100000", direction: "out" });
  assert.deepEqual(splitSign("  + 5"), { text: "5", direction: "in" });
  assert.deepEqual(splitSign("－3"), { text: "3", direction: "out" });
  assert.deepEqual(splitSign("42"), { text: "42", direction: null });
});
