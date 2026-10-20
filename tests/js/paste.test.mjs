// paste.js 單元測試：tab／換行／CRLF、千分位 US／EU、錯誤指出列與欄、空輸入、結尾 tab。
import test from "node:test";
import assert from "node:assert/strict";

import { parsePastedTable } from "../../web/js/paste.js";

test("tab 分隔兩欄、換行分隔列", () => {
  assert.deepEqual(parsePastedTable("100\t2\n200\t3"), { rows: [[100, 2], [200, 3]] });
});

test("CRLF 與 CR 換行，結尾空行被忽略", () => {
  assert.deepEqual(parsePastedTable("1\t2\r\n3\t4\r\n\r\n"), { rows: [[1, 2], [3, 4]] });
  assert.deepEqual(parsePastedTable("1\r2\r"), { rows: [[1], [2]] });
});

test("每列結尾多一個 tab 仍可解析", () => {
  assert.deepEqual(parsePastedTable("1\t2\t\n3\t4\t\n"), { rows: [[1, 2], [3, 4]] });
});

test("單欄：換行分隔、空白分隔、單行多值", () => {
  assert.deepEqual(parsePastedTable("5\n6\n7"), { rows: [[5], [6], [7]] });
  assert.deepEqual(parsePastedTable("1 2 3"), { rows: [[1], [2], [3]] });
  assert.deepEqual(parsePastedTable("  1   2\t"), { rows: [[1], [2]] });
});

test("沒有 tab 的多行多值視為空白分隔的多欄", () => {
  assert.deepEqual(parsePastedTable("1 2\n3 4"), { rows: [[1, 2], [3, 4]] });
});

test("千分位：US 逗號、EU 點，小數點依 sep", () => {
  assert.deepEqual(parsePastedTable("1,234.5\t-2,000", "us"), { rows: [[1234.5, -2000]] });
  assert.deepEqual(parsePastedTable("1.234,5\t-2.000", "eu"), { rows: [[1234.5, -2000]] });
});

test("EU 模式下 US 格式的小數點不合法（不猜測）", () => {
  const r = parsePastedTable("1,234.5", "eu");
  assert.equal(r.rows, undefined);
  assert.equal(r.row, 1);
  assert.equal(r.col, 1);
});

test("非數字格：整體失敗並指出列與欄（1 起算）", () => {
  const r = parsePastedTable("1\t2\n3\tabc\n5\t6");
  assert.equal(r.rows, undefined);
  assert.equal(r.row, 2);
  assert.equal(r.col, 2);
  assert.match(r.error, /第 2 列第 2 欄.*abc/);
});

test("中間的空列與空白格都是錯誤（不默默略過，避免期別錯位）", () => {
  const mid = parsePastedTable("1\t2\n\n3\t4");
  assert.equal(mid.row, 2);
  assert.equal(mid.col, 1);
  const cell = parsePastedTable("1\t\t3");
  assert.equal(cell.row, 1);
  assert.equal(cell.col, 2);
  assert.match(cell.error, /空白/);
});

test("某列比其他列短：缺的格視為空白錯誤", () => {
  const r = parsePastedTable("1\t2\n3");
  assert.equal(r.row, 2);
  assert.equal(r.col, 2);
});

test("空輸入：錯誤，沒有列與欄", () => {
  for (const t of ["", "   ", "\n\n", "\t\n"]) {
    const r = parsePastedTable(t);
    assert.ok(r.error, JSON.stringify(t));
    assert.equal(r.rows, undefined);
    assert.equal(r.row, null);
    assert.equal(r.col, null);
  }
  assert.ok(parsePastedTable(undefined).error);
});

test("全形數字與科學記號沿用 parseNumber", () => {
  assert.deepEqual(parsePastedTable("１２３\t1e3"), { rows: [[123, 1000]] });
});
