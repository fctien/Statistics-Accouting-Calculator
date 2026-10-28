// 進位轉換畫面（views/base.js，不經 renderForm）與 sheets.js 的 base／base-bitwise 欄位定義一致：
// 畫面組出的請求鍵＋顯示的結果鍵＝SHEETS 欄位 id；位元運算畫面建立的輸入欄 id（BITWISE_INPUT_IDS）都在定義中。
import test from "node:test";
import assert from "node:assert/strict";

import { SHEETS } from "../../web/js/sheets.js";
import { BASES, BITWISE_INPUT_IDS, baseRequest, bitwiseRequest } from "../../web/js/eng.js";

const sorted = (xs) => [...xs].sort();
const outs = BASES.map((b) => b.id);

test("SHEETS.base 欄位＝base/convert 請求鍵＋四欄結果", () => {
  const req = baseRequest("DEC", "255", 8, false);
  assert.deepEqual(sorted(SHEETS.base.fields.map((f) => f.id)), sorted([...Object.keys(req.inputs), ...outs]));
  assert.deepEqual(SHEETS.base.fields.filter((f) => f.output).map((f) => f.id), outs);
});

test("SHEETS['base-bitwise'] 欄位＝base/bitwise 請求鍵＋四欄結果，畫面輸入欄 id 都在其中", () => {
  const req = bitwiseRequest({ op: "AND", a: "12", b: "10", fromId: "DEC", width: 8, signed: false });
  const ids = SHEETS["base-bitwise"].fields.map((f) => f.id);
  assert.deepEqual(sorted(ids), sorted([...Object.keys(req.inputs), ...outs]));
  assert.deepEqual(SHEETS["base-bitwise"].fields.filter((f) => f.output).map((f) => f.id), outs);
  for (const id of BITWISE_INPUT_IDS) assert.ok(ids.includes(id), id);
  assert.deepEqual(sorted(BITWISE_INPUT_IDS), ["A", "B", "OP"]);
});
