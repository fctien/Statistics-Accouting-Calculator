// tables.js 單元測試：貼上套用、CF／STAT 表格讀取與錯誤的列欄。
import test from "node:test";
import assert from "node:assert/strict";

import { applyPaste, readCfTable, readStatTable, numToText, MAX_ROWS } from "../../web/js/tables.js";

const blankRows = (n, w) => Array.from({ length: n }, () => new Array(w).fill(""));

test("numToText：EU 用逗號當小數點，且能被同一 sep 解析回來", () => {
  assert.equal(numToText(1234.5, "us"), "1234.5");
  assert.equal(numToText(1234.5, "eu"), "1234,5");
  assert.equal(numToText(-3, "eu"), "-3");
});

test("applyPaste：兩欄貼進 CF，列數不足自動增加，不改動原陣列", () => {
  const cells = blankRows(1, 2);
  const r = applyPaste(cells, 0, 0, [[100, 2], [200, 3], [300, 1]], { width: 2 });
  assert.deepEqual(r.cells, [["100", "2"], ["200", "3"], ["300", "1"]]);
  assert.deepEqual(cells, [["", ""]]);
});

test("applyPaste：單欄金額貼進 CF，次數欄填 1（fill）", () => {
  const r = applyPaste(blankRows(2, 2), 0, 0, [[5], [6], [7]], { width: 2, fill: { 1: "1" } });
  assert.deepEqual(r.cells, [["5", "1"], ["6", "1"], ["7", "1"]]);
});

test("applyPaste：從中間列貼上只覆蓋該範圍；EU 小數點", () => {
  const cells = [["1", "1"], ["2", "1"], ["3", "1"]];
  const r = applyPaste(cells, 1, 0, [[9.5, 4]], { width: 2, sep: "eu" });
  assert.deepEqual(r.cells, [["1", "1"], ["9,5", "4"], ["3", "1"]]);
});

test("applyPaste：欄數放不下、超過列數上限都整批拒絕", () => {
  assert.match(applyPaste(blankRows(1, 2), 0, 1, [[1, 2]], { width: 2 }).error, /放不下/);
  const big = Array.from({ length: MAX_ROWS + 1 }, (_, i) => [i]);
  const r = applyPaste(blankRows(1, 2), 0, 0, big, { width: 2 });
  assert.match(r.error, /超過上限/);
  assert.equal(r.cells, undefined);
  assert.equal(applyPaste(blankRows(1, 2), 0, 0, [[1]], { width: 2, maxRows: 1 }).cells.length, 1);
});

test("readCfTable：正常、結尾空白列忽略、預設次數 1 的空列視為空白", () => {
  const r = readCfTable([["3,000", "1"], ["4200", "2"], ["", "1"], ["", ""]], "us");
  assert.deepEqual(r, { flows: [[3000, 1], [4200, 2]] });
  assert.deepEqual(readCfTable([["", "1"]]), { flows: [] });
});

test("readCfTable：中間空白列是錯誤（期別會錯位）", () => {
  const r = readCfTable([["100", "1"], ["", "1"], ["300", "1"]]);
  assert.equal(r.row, 2);
  assert.equal(r.col, 1);
  assert.match(r.error, /輸入 0/);
});

test("readCfTable：金額或次數不合法時指出列與欄", () => {
  assert.equal(readCfTable([["1", "1"], ["x", "1"]]).row, 2);
  const c = readCfTable([["1", "1"], ["5", "2.5"]]);
  assert.equal(c.row, 2);
  assert.equal(c.col, 2);
  assert.equal(readCfTable([["5", "0"]]).col, 2);
  assert.equal(readCfTable([["5", "10000"]]).col, 2);
  assert.equal(readCfTable([["5", ""]]).col, 2);
  assert.equal(readCfTable([["", "3"]]).col, 1); // 有次數沒金額
});

test("readStatTable：單變數，無次數欄", () => {
  const r = readStatTable([["1", "", ""], ["2", "9", ""], ["", "", ""], ["3", "", ""]], "one_var");
  assert.deepEqual(r, { X: [1, 2, 3], Y: null, F: null });
});

test("readStatTable：單變數次數欄，全有或全無", () => {
  assert.deepEqual(readStatTable([["1", "", "2"], ["2", "", "3"]], "one_var"), { X: [1, 2], Y: null, F: [2, 3] });
  const r = readStatTable([["1", "", "2"], ["2", "", ""]], "one_var");
  assert.equal(r.row, 2);
  assert.equal(r.col, 3);
  assert.equal(readStatTable([["1", "", "0"]], "one_var").col, 3);
  assert.equal(readStatTable([["1", "", "1.5"]], "one_var").col, 3);
});

test("readStatTable：迴歸要 X 與 Y，次數欄有值就報錯", () => {
  assert.deepEqual(readStatTable([["1", "2", ""], ["3", "4", ""]], "two_var"), { X: [1, 3], Y: [2, 4], F: null });
  const noY = readStatTable([["1", "2", ""], ["3", "", ""]], "two_var");
  assert.equal(noY.row, 2);
  assert.equal(noY.col, 2);
  const withF = readStatTable([["1", "2", "5"]], "two_var");
  assert.equal(withF.col, 3);
  assert.match(withF.error, /不使用次數/);
});

test("readStatTable：非數字指出列欄；全空表格回傳空陣列（由引擎說明）", () => {
  const r = readStatTable([["1", "", ""], ["a", "", ""]], "one_var");
  assert.equal(r.row, 2);
  assert.equal(r.col, 1);
  assert.deepEqual(readStatTable([["", "", ""]], "one_var"), { X: [], Y: null, F: null });
});

test("readStatTable：EU 小數逗號", () => {
  assert.deepEqual(readStatTable([["1,5", "2,5", ""]], "two_var", "eu"), { X: [1.5], Y: [2.5], F: null });
});
