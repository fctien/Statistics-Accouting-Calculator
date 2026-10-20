// keypad.js、datefmt.js 測試：插入、退格、日期顯示格式。
import test from "node:test";
import assert from "node:assert/strict";

import { insertAt, backspaceAt, KEY_ROWS } from "../../web/js/keypad.js";
import { formatDate, formatIso } from "../../web/js/datefmt.js";

test("insertAt：游標處插入、取代選取、夾在範圍內", () => {
  assert.deepEqual(insertAt("12", 1, 1, "+"), { text: "1+2", caret: 2 });
  assert.deepEqual(insertAt("1234", 1, 3, "x"), { text: "1x4", caret: 2 });
  assert.deepEqual(insertAt("12", 99, 99, "3"), { text: "123", caret: 3 });
  assert.deepEqual(insertAt("12", -5, -5, "0"), { text: "012", caret: 1 });
  assert.deepEqual(insertAt("12", 2, 0, "-"), { text: "-", caret: 1 });
  assert.deepEqual(insertAt("", null, null, "√("), { text: "√(", caret: 2 });
});

test("backspaceAt", () => {
  assert.deepEqual(backspaceAt("123", 3, 3), { text: "12", caret: 2 });
  assert.deepEqual(backspaceAt("123", 0, 0), { text: "123", caret: 0 });
  assert.deepEqual(backspaceAt("1234", 1, 3), { text: "14", caret: 1 });
});

test("按鍵：數字 0～9 都有，插入字串皆非空", () => {
  const keys = KEY_ROWS.flat();
  for (const d of "0123456789") assert.ok(keys.some((k) => k.insert === d), d);
  for (const k of keys) assert.ok(k.insert.length > 0 && k.label.length > 0);
  for (const need of ["(", ")", "%", "√(", "²", "inv(", "^", "!", "ANS"]) {
    assert.ok(keys.some((k) => k.insert === need), need);
  }
});

test("日期顯示：美式與歐式", () => {
  assert.equal(formatDate(2026, 3, 5, "us"), "03/05/2026");
  assert.equal(formatDate(2026, 3, 5, "eu"), "05.03.2026");
  assert.equal(formatIso("2026-12-31", "us"), "12/31/2026");
  assert.equal(formatIso("2026-12-31", "eu"), "31.12.2026");
  assert.equal(formatIso("", "us"), null);
  assert.equal(formatIso("2026-1-1", "us"), null);
  assert.equal(formatIso(null, "eu"), null);
});
