// 純函式：可編輯表格（CF、STAT）的資料處理（不碰 DOM，可用 node --test 測試）。
// 表格內容以字串二維陣列 cells[列][欄] 表示（與畫面輸入框一致）；
// 數字解析重用 input.js 的 parseNumber，貼上的解析在 paste.js。
// 所有錯誤都回傳 {error, row, col}（1 起算）；不略過、不補預設值，避免看似正常卻錯誤的結果。
import { parseNumber } from "./input.js";

/** 畫面上表格列數上限（引擎沒有上限，這是避免 UI 卡死的保護）。 */
export const MAX_ROWS = 500;

const MAX_COUNT = 9999; // 與 engine/cashflow.py 的 _MAX_COUNT 相同

/** 數字轉成輸入框文字：EU 模式的小數點用逗號，讓同一個 sep 解析回來得到相同數值。 */
export function numToText(v, sep = "us") {
  const s = String(v);
  return sep === "eu" ? s.replace(".", ",") : s;
}

function fail(error, row, col) {
  return { error, row, col };
}

/**
 * 把貼上的數字矩陣寫進表格，回傳 {cells: 新的二維陣列}（不改動原陣列）或 {error}。
 * cells：現有內容；r0、c0：起始列、欄（0 起算）；matrix：parsePastedTable 的 rows。
 * opts.width：表格欄數；opts.sep；opts.maxRows（預設 MAX_ROWS）；
 * opts.fill：{欄索引: 文字}，矩陣沒有涵蓋的欄寫入此預設（例：CF 只貼一欄金額時，次數欄填 "1"）。
 * 欄數超出表格、列數超出上限都整批拒絕（不貼一半）。
 */
export function applyPaste(cells, r0, c0, matrix, opts = {}) {
  const { width = 1, sep = "us", maxRows = MAX_ROWS, fill = {} } = opts;
  const mw = matrix.length ? matrix[0].length : 0;
  if (mw === 0) return { error: "沒有可貼上的資料" };
  if (c0 + mw > width) {
    return { error: `貼上的資料有 ${mw} 欄，從這一欄開始放不下（表格共 ${width} 欄）` };
  }
  const need = r0 + matrix.length;
  if (need > maxRows) {
    return { error: `貼上後會有 ${need} 列，超過上限 ${maxRows} 列，未貼上任何資料` };
  }
  const out = cells.map((r) => r.slice());
  while (out.length < need) out.push(new Array(width).fill(""));
  matrix.forEach((row, i) => {
    row.forEach((v, j) => { out[r0 + i][c0 + j] = numToText(v, sep); });
    for (const [col, text] of Object.entries(fill)) {
      const c = Number(col);
      if (c < c0 || c >= c0 + mw) out[r0 + i][c] = text;
    }
  });
  return { cells: out };
}

const blank = (s) => String(s ?? "").trim() === "";

/**
 * 讀 CF 表格 [金額 CFj, 次數 Fj] → {flows: [[金額, 次數], ...]}。
 * 結尾的空白列忽略；中間的空白列是錯誤（期別會錯位，沒有現金流的期請輸入 0）。
 * 次數空白視為 1（TI 預設），否則須為 1～9999 的整數；金額空白但次數有填（不是 1）是錯誤。
 */
export function readCfTable(cells, sep = "us") {
  const isBlankRow = (r) => blank(r[0]) && (blank(r[1]) || String(r[1]).trim() === "1");
  let last = cells.length - 1;
  while (last >= 0 && isBlankRow(cells[last])) last--;
  const flows = [];
  for (let i = 0; i <= last; i++) {
    const n = i + 1;
    const [a, c] = cells[i];
    if (isBlankRow(cells[i])) {
      return fail(`第 ${n} 列是空白，請輸入金額（這一期沒有現金流請輸入 0）`, n, 1);
    }
    if (blank(a)) return fail(`第 ${n} 列請輸入金額`, n, 1);
    const amount = parseNumber(a, sep);
    if (amount === null) return fail(`第 ${n} 列金額「${String(a).trim()}」不是數字`, n, 1);
    const count = blank(c) ? 1 : parseNumber(c, sep); // 次數空白＝1（TI 預設）
    if (count === null) return fail(`第 ${n} 列次數「${String(c).trim()}」不是數字`, n, 2);
    if (!Number.isInteger(count) || count < 1 || count > MAX_COUNT) {
      return fail(`第 ${n} 列次數須為 1～${MAX_COUNT} 的整數`, n, 2);
    }
    flows.push([amount, count]);
  }
  return { flows };
}

/**
 * 讀 STAT 表格 [X, Y, 次數] → {X: [...], Y: [...] 或 null, F: [...] 或 null}。
 * mode "one_var"：只用 X 與（選填的）次數；次數欄有填就每一列都要填，且為 ≥ 1 的整數。
 * mode "two_var"：用 X 與 Y；次數欄必須空白（迴歸不使用次數，不默默忽略）。
 * 全空的列略過（資料點的先後不影響統計）。
 */
export function readStatTable(cells, mode, sep = "us") {
  const X = [];
  const Y = [];
  const F = [];
  let blankFreqRow = null;
  for (let i = 0; i < cells.length; i++) {
    const n = i + 1;
    const [x, y, f] = cells[i];
    if (blank(x) && blank(y) && blank(f)) continue;
    if (blank(x)) return fail(`第 ${n} 列請輸入 X`, n, 1);
    const xv = parseNumber(x, sep);
    if (xv === null) return fail(`第 ${n} 列 X「${String(x).trim()}」不是數字`, n, 1);
    X.push(xv);
    if (mode === "two_var") {
      if (blank(y)) return fail(`第 ${n} 列請輸入 Y`, n, 2);
      const yv = parseNumber(y, sep);
      if (yv === null) return fail(`第 ${n} 列 Y「${String(y).trim()}」不是數字`, n, 2);
      Y.push(yv);
      if (!blank(f)) {
        return fail(`第 ${n} 列有填次數，但迴歸不使用次數；請清空次數欄，或改用單變數 1-V`, n, 3);
      }
    } else if (blank(f)) {
      if (blankFreqRow === null) blankFreqRow = n;
    } else {
      const fv = parseNumber(f, sep);
      if (fv === null) return fail(`第 ${n} 列次數「${String(f).trim()}」不是數字`, n, 3);
      if (!Number.isInteger(fv) || fv < 1) return fail(`第 ${n} 列次數須為 ≥ 1 的整數`, n, 3);
      F.push(fv);
    }
  }
  if (mode === "two_var") return { X, Y, F: null };
  if (F.length > 0 && F.length !== X.length) {
    return fail(`次數欄有填時每一列都要填（第 ${blankFreqRow} 列沒有次數）`, blankFreqRow, 3);
  }
  return { X, Y: null, F: F.length ? F : null };
}
