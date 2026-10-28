// eng.js 測試（工程頁純函式）：計算請求組裝（含 angle）、單位換算請求、
// 進位欄位同步、BIN 分組、位元運算請求、序號防亂序（sequence guard）、± 切換。
import test from "node:test";
import assert from "node:assert/strict";

import {
  BASES, WIDTHS, BIT_OPS, evalRequest, angleLabel, resultIsStale,
  unitsRequest, unitLabel, swapUnits,
  stripSpaces, groupBin, baseRequest, baseFieldUpdates, bitwiseRequest,
  needsB, opAllowed, createSeq,
} from "../../web/js/eng.js";
import { toggleSign, SCI_ROWS, KEY_ROWS } from "../../web/js/keypad.js";

test("evalRequest：settings 原樣送出（含 angle），ANS 與 MEM 放進 inputs", () => {
  const st = { decimals: 2, sep: "us", mode: "AOS", angle: "RAD" };
  const r = evalRequest("sin(π/6)", 3, { M1: 2 }, st);
  assert.deepEqual(r, {
    sheet: "calc", action: "eval",
    inputs: { EXPR: "sin(π/6)", ANS: 3, MEM: { M1: 2 } },
    settings: st,
  });
  assert.equal(r.settings.angle, "RAD");
});

test("角度模式：標籤與舊結果是否過期", () => {
  assert.equal(angleLabel("DEG"), "DEG 度");
  assert.equal(angleLabel("RAD"), "RAD 弧度");
  assert.equal(resultIsStale("DEG", "RAD"), true);
  assert.equal(resultIsStale("RAD", "RAD"), false);
  assert.equal(resultIsStale(null, "RAD"), false, "沒有結果就沒有過期");
});

test("unitsRequest：空白、非數值、正常（依千分位設定解析）", () => {
  assert.deepEqual(unitsRequest("", "mi", "km", "us"), { empty: true });
  assert.deepEqual(unitsRequest("   ", "mi", "km", "us"), { empty: true });
  const bad = unitsRequest("abc", "mi", "km", "us");
  assert.equal(bad.field, "VALUE");
  assert.match(bad.error, /數字/);
  assert.deepEqual(unitsRequest("1,000.5", "m", "km", "us").request, {
    sheet: "units", action: "convert", inputs: { VALUE: 1000.5, FROM: "m", TO: "km" },
  });
  assert.equal(unitsRequest("1.000,5", "m", "km", "eu").request.inputs.VALUE, 1000.5);
  assert.equal(unitsRequest("-40", "degC", "degF", "us").request.inputs.VALUE, -40);
});

test("unitLabel 顯示中文＋符號；swapUnits 交換", () => {
  assert.equal(unitLabel({ id: "km", zh: "公里", sym: "km" }), "公里 km");
  assert.deepEqual(swapUnits({ from: "mi", to: "km" }), { from: "km", to: "mi" });
});

test("BIN 分組：每 4 位一組（由右往左），stripSpaces 去空白與底線", () => {
  assert.equal(groupBin("11111111"), "1111 1111");
  assert.equal(groupBin("101"), "101");
  assert.equal(groupBin("1101"), "1101");
  assert.equal(groupBin("110110"), "11 0110");
  assert.equal(groupBin(""), "");
  assert.equal(stripSpaces("1111 0000"), "11110000");
  assert.equal(stripSpaces(" 1_0 1\t"), "101");
  assert.equal(stripSpaces(groupBin("1000000000000001")), "1000000000000001");
});

test("baseRequest：以來源欄位的進位送出；空白回 null", () => {
  assert.deepEqual(BASES.map((b) => [b.id, b.radix]), [["BIN", 2], ["OCT", 8], ["DEC", 10], ["HEX", 16]]);
  assert.deepEqual(WIDTHS, [8, 16, 32, 64]);
  assert.deepEqual(baseRequest("DEC", "255", 8, false), {
    sheet: "base", action: "convert", inputs: { TEXT: "255", FROM: 10, WIDTH: 8, SIGNED: false },
  });
  assert.equal(baseRequest("BIN", "1111 0000", 16, true).inputs.TEXT, "11110000");
  assert.equal(baseRequest("BIN", "1111 0000", 16, true).inputs.FROM, 2);
  assert.equal(baseRequest("HEX", "  ", 8, false), null);
});

test("baseFieldUpdates：更新其他三欄（BIN 分組、HEX 不加千分位），不動來源欄", () => {
  const values = { BIN: "11111111", OCT: "377", DEC: "255", HEX: "FF" };
  assert.deepEqual(baseFieldUpdates("DEC", values), { BIN: "1111 1111", OCT: "377", HEX: "FF" });
  assert.deepEqual(baseFieldUpdates("BIN", values), { OCT: "377", DEC: "255", HEX: "FF" });
  assert.deepEqual(baseFieldUpdates(null, values), { BIN: "1111 1111", OCT: "377", DEC: "255", HEX: "FF" });
  // 大數不得出現千分位
  const big = baseFieldUpdates("HEX", { BIN: "1".repeat(32), OCT: "37777777777", DEC: "4294967295", HEX: "FFFFFFFF" });
  assert.equal(big.DEC, "4294967295");
  assert.ok(!big.DEC.includes(","));
});

test("bitwiseRequest：NOT 不送 B；A、B 去空白；其餘送 B", () => {
  assert.deepEqual(BIT_OPS, ["AND", "OR", "XOR", "NOT", "SHL", "SHR", "SAR"]);
  assert.deepEqual(bitwiseRequest({ op: "AND", a: "12", b: "10", fromId: "DEC", width: 8, signed: false }), {
    sheet: "base", action: "bitwise",
    inputs: { OP: "AND", A: "12", B: "10", FROM: 10, WIDTH: 8, SIGNED: false },
  });
  const not = bitwiseRequest({ op: "NOT", a: "1100", b: "9", fromId: "BIN", width: 8, signed: false });
  assert.ok(!("B" in not.inputs));
  assert.equal(not.inputs.FROM, 2);
  assert.equal(bitwiseRequest({ op: "OR", a: "1100 0011", b: "1", fromId: "BIN", width: 8, signed: false }).inputs.A, "11000011");
  assert.equal(bitwiseRequest({ op: "OR", a: "", b: "1", fromId: "DEC", width: 8, signed: false }), null);
  assert.equal(bitwiseRequest({ op: "OR", a: "1", b: " ", fromId: "DEC", width: 8, signed: false }), null);
  assert.equal(needsB("NOT"), false);
  assert.equal(needsB("SHL"), true);
  assert.equal(opAllowed("SAR", false), false);
  assert.equal(opAllowed("SAR", true), true);
  assert.equal(opAllowed("SHR", false), true);
});

test("序號防亂序：較晚發出的請求才算數，bump 讓進行中的全部作廢", () => {
  const seq = createSeq();
  const a = seq.next();
  const b = seq.next();
  assert.equal(seq.isCurrent(a), false, "舊請求晚回來：丟棄");
  assert.equal(seq.isCurrent(b), true);
  seq.bump();
  assert.equal(seq.isCurrent(b), false, "輸入改了：進行中的請求作廢");
});

test("toggleSign（±）：切換游標所在數字的負號", () => {
  assert.deepEqual(toggleSign("12", 2), { text: "−12", caret: 3 });
  assert.deepEqual(toggleSign("−12", 3), { text: "12", caret: 2 });
  assert.deepEqual(toggleSign("3+45", 4), { text: "3+−45", caret: 5 });
  assert.deepEqual(toggleSign("3+−45", 5), { text: "3+45", caret: 4 });
  assert.deepEqual(toggleSign("3−45", 4), { text: "3−−45", caret: 5 }, "二元減號不是負號：加一個負號");
  assert.deepEqual(toggleSign("2×(7", 4), { text: "2×(−7", caret: 5 });
  assert.deepEqual(toggleSign("", 0), { text: "−", caret: 1 });
  assert.deepEqual(toggleSign("1.5", 1), { text: "−1.5", caret: 2 }, "游標在數字中間也可");
});

test("科學鍵：三角、反三角（2nd）、log、ln、∛、π、e、DEG／RAD 都在", () => {
  const keys = SCI_ROWS.flat();
  const ins = (k) => k.insert;
  for (const need of ["sin(", "cos(", "tan(", "log(", "ln(", "cbrt(", "π", "e"]) {
    assert.ok(keys.some((k) => ins(k) === need), need);
  }
  for (const need of ["asin(", "acos(", "atan(", "exp("]) {
    assert.ok(keys.some((k) => k.second && k.second.insert === need), `2nd ${need}`);
  }
  assert.ok(keys.some((k) => k.action === "second"), "2nd 鍵");
  assert.ok(keys.some((k) => k.action === "angle"), "DEG／RAD 鍵");
  assert.ok(keys.some((k) => k.action === "negate"), "± 鍵");
  const all = [...KEY_ROWS.flat(), ...keys];
  for (const need of ["^", "√(", "²", "inv(", "!", "(", ")"]) {
    assert.ok(all.some((k) => k.insert === need), need);
  }
  assert.ok(KEY_ROWS.flat().some((k) => k.label === "xʸ"), "次方鍵標為 xʸ");
});
