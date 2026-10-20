// 純函式：解析從 Excel／試算表複製的貼上文字（不碰 DOM，可用 node --test 測試）。
// 數字解析一律重用 input.js 的 parseNumber（含千分位 US／EU、全形數字、1e3），不另寫一份。
//
// 接受的格式：
//   - 有 tab：tab 分隔欄、換行（LF／CRLF／CR）分隔列（Excel 複製的標準格式）
//   - 沒有 tab：單欄的清單，以換行或空白分隔（「1 2 3」或每行一個）；
//     多行且每行都有多個以空白分隔的值時，視為空白分隔的多欄表格
//   - 允許結尾的空行與每列結尾的 tab（Excel 常見）
// 任何一格無法解析（含中間的空列、空白格）就整體回傳錯誤，並指出列與欄（1 起算），不猜測、不略過。
import { parseNumber } from "./input.js";

function fail(error, row = null, col = null) {
  return { error, row, col };
}

function splitTabs(line) {
  const cells = line.split("\t").map((c) => c.trim());
  while (cells.length && cells[cells.length - 1] === "") cells.pop(); // 結尾 tab
  return cells;
}

/**
 * 解析貼上的文字。
 * 成功回傳 {rows: number[][]}（每列欄數一致）；失敗回傳 {error, row, col}（row、col 為 1 起算，
 * 空輸入時為 null）。sep："us"（1,234.56）或 "eu"（1.234,56）。
 */
export function parsePastedTable(text, sep = "us") {
  if (typeof text !== "string") return fail("沒有可貼上的資料");
  const lines = text.split(/\r\n|\n|\r/);
  while (lines.length && lines[lines.length - 1].trim() === "") lines.pop(); // 結尾空行
  if (lines.length === 0) return fail("貼上的內容是空的");

  let grid = lines.map(splitTabs);
  if (Math.max(...grid.map((r) => r.length)) <= 1) {
    // 沒有真正的多欄 tab：單欄清單（結尾 tab 已去掉），值可用換行或空白分隔
    const toks = lines.map((l) => (l.trim() === "" ? [] : l.trim().split(/\s+/)));
    if (lines.length === 1) grid = toks[0].map((t) => [t]); // 一行多值：視為一欄
    else grid = toks; // 每行一個值＝一欄；每行多個值＝空白分隔的多欄
  }

  const width = Math.max(...grid.map((r) => r.length));
  const rows = [];
  for (let i = 0; i < grid.length; i++) {
    const out = [];
    for (let j = 0; j < width; j++) {
      const cell = grid[i][j] ?? "";
      if (cell === "") {
        return fail(`第 ${i + 1} 列第 ${j + 1} 欄是空白，請補上數字或刪除該列`, i + 1, j + 1);
      }
      const v = parseNumber(cell, sep);
      if (v === null) {
        return fail(`第 ${i + 1} 列第 ${j + 1} 欄「${cell}」不是數字`, i + 1, j + 1);
      }
      out.push(v);
    }
    rows.push(out);
  }
  return { rows };
}
