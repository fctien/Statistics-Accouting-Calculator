// 測試輔助（由 tests/test_web_input.py 呼叫）：從 stdin 讀 [[文字, sep], ...]，
// 以 input.js 的 parseNumber 解析，輸出結果陣列（JSON；無法解析為 null）。
import { parseNumber } from "../../../web/js/input.js";

let buf = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (c) => { buf += c; });
process.stdin.on("end", () => {
  const cases = JSON.parse(buf);
  process.stdout.write(JSON.stringify(cases.map(([t, sep]) => parseNumber(t, sep))));
});
