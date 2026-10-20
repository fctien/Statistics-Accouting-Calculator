// 測試輔助（由 tests/test_web_sheets.py 呼叫，不是 node --test 測試檔）：
// 用每個欄位的 example 組出表單值，經 input.js 的 collect() 轉成引擎 inputs，輸出 JSON。
// 用法：node sheet_examples.mjs '<{"sheet.action": ["留空欄位", ...]}>'
import { SHEETS, SHEET_ORDER, sendFields } from "../../../web/js/sheets.js";
import { collect } from "../../../web/js/input.js";

const blanks = JSON.parse(process.argv[2] || "{}");
const out = [];
for (const sheetId of SHEET_ORDER) {
  const sheet = SHEETS[sheetId];
  for (const action of sheet.actions) {
    const fields = sendFields(sheetId, action.id);
    const skip = new Set(blanks[`${sheetId}.${action.id}`] || []);
    const values = {};
    const kinds = {};
    for (const f of fields) {
      kinds[f.id] = f;
      const text = skip.has(f.id) ? "" : f.example;
      if (f.kind === "direction") values[f.id] = { text, direction: f.initialDirection || "in" };
      else if (f.kind === "bool") values[f.id] = text === "是";
      else values[f.id] = text;
    }
    const { inputs, errors } = collect(values, kinds, "us");
    out.push({
      sheet: sheetId, engine: sheet.engine, action: action.id, inputs, errors,
      fields: sheet.fields.map((f) => ({
        id: f.id, key: f.key || f.id, out: f.out || f.id, kind: f.kind,
        example: f.example, output: Boolean(f.output),
      })),
    });
  }
}
process.stdout.write(JSON.stringify(out));
