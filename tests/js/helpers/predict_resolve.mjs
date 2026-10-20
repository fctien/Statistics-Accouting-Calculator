// 測試輔助（由 tests/test_web_sheets.py 呼叫）：模擬 STAT 預測兩次的表單讀值流程
// （與 views/form.js 的 readInputs 相同：collect → 求出值用完整精度 → resolveBlanks）。
// 用法：node predict_resolve.mjs <已知鍵 X|Y> [上次求出的值]
// 輸出 {first: 第一次 inputs, second: 改了已知格之後的 inputs（有給上次求出值時）}
import { SHEETS, sendFields } from "../../../web/js/sheets.js";
import { collect, resolveBlanks } from "../../../web/js/input.js";

const given = process.argv[2];
const solvedValue = process.argv[3];
const action = SHEETS.stats.actions.find((a) => a.id === "predict");
const fields = sendFields("stats", "predict");
const kinds = Object.fromEntries(fields.map((f) => [f.id, f]));
const givenId = given === "X" ? "XP" : "YP";
const otherId = given === "X" ? "YP" : "XP";
const otherKey = given === "X" ? "Y" : "X";

const base = { model: "LIN", A: "2.2", B: "0.6" };
const first = collect({ ...base, [givenId]: given === "X" ? "6" : "5.8", [otherId]: "" }, kinds).inputs;
let second = null;
if (solvedValue !== undefined) {
  // 已知格改成新值；另一格是上次引擎求出、未改動的值
  const { inputs } = collect({ ...base, [givenId]: given === "X" ? "7" : "6.4", [otherId]: "0" }, kinds);
  inputs[otherKey] = Number(JSON.parse(solvedValue));
  second = resolveBlanks(inputs, action.solve, [otherKey]);
}
process.stdout.write(JSON.stringify({ first, second }));
