// csv.js 單元測試：RFC 4180 跳脫、CRLF、BOM、空列。
import test from "node:test";
import assert from "node:assert/strict";

import { toCSV, csvField, BOM } from "../../web/js/csv.js";

test("一般欄位不加引號，列以 CRLF 分隔且結尾有 CRLF", () => {
  assert.equal(toCSV([["1", "2"], ["3", "4"]], ["a", "b"]), "a,b\r\n1,2\r\n3,4\r\n");
});

test("含逗號、雙引號、換行的欄位加引號，引號重複一次", () => {
  assert.equal(csvField("1,234.50"), '"1,234.50"');
  assert.equal(csvField('say "hi"'), '"say ""hi"""');
  assert.equal(csvField("a\nb"), '"a\nb"');
  assert.equal(csvField("a\rb"), '"a\rb"');
  assert.equal(csvField("plain"), "plain");
});

test("千分位數字在 toCSV 中被正確引號包住", () => {
  assert.equal(toCSV([["1", "1,234.50"]], ["期", "餘額"]), '期,餘額\r\n1,"1,234.50"\r\n');
});

test("bom 選項加上 UTF-8 BOM（U+FEFF）", () => {
  const s = toCSV([["1"]], ["期"], { bom: true });
  assert.equal(s.charCodeAt(0), 0xfeff);
  assert.equal(s, BOM + "期\r\n1\r\n");
  assert.equal(toCSV([["1"]], ["期"]).charCodeAt(0), "期".charCodeAt(0));
});

test("沒有資料列時只輸出標頭；沒有標頭也沒有列時為空字串", () => {
  assert.equal(toCSV([], ["a", "b"]), "a,b\r\n");
  assert.equal(toCSV([], []), "");
  assert.equal(toCSV([], null), "");
  assert.equal(toCSV([], [], { bom: true }), BOM);
});

test("null／undefined 當空欄位，數字轉字串", () => {
  assert.equal(toCSV([[1, null, undefined, 2.5]], null), "1,,,2.5\r\n");
});

test("標頭也會跳脫", () => {
  assert.equal(toCSV([], ['a,"b"']), '"a,""b"""\r\n');
});
