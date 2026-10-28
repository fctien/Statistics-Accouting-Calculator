// 工程頁（ENG）的純函式（不碰 DOM，可用 node --test 測試）：
//   - 科學計算機：組 calc/eval 請求（settings 含 angle）、角度模式標籤、舊結果過期判斷
//   - 單位換算：組 units/convert 請求（依千分位設定解析數值）、單位選項標籤、交換
//   - 進位轉換：四欄 BIN／OCT／DEC／HEX 的同步、BIN 每 4 位分組（只供顯示）、位元運算請求
//   - 序號防亂序（sequence guard）：沿用 ICONV 的寫法，較晚發出的請求才算數
// 數值格式化一律交給引擎（display）；這裡不自己算任何結果。
import { parseNumber, convertSepText } from "./input.js";
import { usesTrig } from "./tape.js";

/** 四種進位：id 同時是 base/convert 回傳值的鍵。 */
export const BASES = [
  { id: "BIN", radix: 2, label: "二進位 BIN" },
  { id: "OCT", radix: 8, label: "八進位 OCT" },
  { id: "DEC", radix: 10, label: "十進位 DEC" },
  { id: "HEX", radix: 16, label: "十六進位 HEX" },
];

/** 位寬（bit width）選項。 */
export const WIDTHS = [8, 16, 32, 64];

/** 位元運算（bitwise operation）。 */
export const BIT_OPS = ["AND", "OR", "XOR", "NOT", "SHL", "SHR", "SAR"];

/** 進位 id → 基數（radix）。 */
export function radixOf(id) {
  const b = BASES.find((x) => x.id === id);
  return b ? b.radix : null;
}

// ---------------------------------------------------------------- 科學計算機

/** calc/eval 請求；settings 為 settings.toEngine() 的結果（含 mode、angle），原樣送出。 */
export function evalRequest(expr, ans, mem, settings) {
  return {
    sheet: "calc", action: "eval",
    inputs: { EXPR: expr, ANS: ans, MEM: mem },
    settings,
  };
}

/** 角度模式的顯示文字。 */
export function angleLabel(angle) {
  return angle === "RAD" ? "RAD 弧度" : "DEG 度";
}

/**
 * 新結果（ANS）的角度標記：算式含三角函數 → 目前角度；引用 ANS → 沿用上一個 ANS 的標記；
 * 其餘與角度無關（null）。記憶 M0～M9 的來源不追蹤。
 */
export function ansAngleFor(expr, angle, prevAnsAngle) {
  if (usesTrig(expr)) return angle;
  if (/(^|[^A-Za-z0-9_])ANS([^A-Za-z0-9_]|$)/.test(String(expr))) return prevAnsAngle ?? null;
  return null;
}

/** 結果是在 resultAngle 模式算的，目前是 currentAngle：不同就是過期（沒有結果則否）。 */
export function resultIsStale(resultAngle, currentAngle) {
  return resultAngle !== null && resultAngle !== undefined && resultAngle !== currentAngle;
}

// ---------------------------------------------------------------- 單位換算

/**
 * 組 units/convert 請求。回傳 {empty: true}（空白，不送）、{error, field: "VALUE"}（不是數字）
 * 或 {request}。數值依使用者的千分位設定（sep）解析。
 */
export function unitsRequest(text, from, to, sep = "us") {
  if (typeof text !== "string" || text.trim() === "") return { empty: true };
  const v = parseNumber(text, sep);
  if (v === null) {
    return { error: `請輸入數字，例如 ${sep === "eu" ? "1,5" : "1.5"}`, field: "VALUE" };
  }
  return { request: { sheet: "units", action: "convert", inputs: { VALUE: v, FROM: from, TO: to } } };
}

/**
 * 千分位設定改變時，把 fromSep 下輸入的數值文字改寫成 toSep 的寫法（不重新解讀）。
 * 回傳 {text}，或 {error}（原本的寫法就解不出來，請使用者重新輸入）。
 */
export function rewriteForSep(text, fromSep, toSep) {
  const r = convertSepText(String(text ?? ""), { kind: "number" }, fromSep, toSep);
  return r.error ? { error: "千分位設定已改變，請重新輸入" } : { text: r.text };
}

/** 單位選項文字：中文名＋符號，例「公里 km」。 */
export function unitLabel(u) {
  return `${u.zh} ${u.sym}`;
}

/** 「⇄」：交換從單位與到單位。 */
export function swapUnits({ from, to }) {
  return { from: to, to: from };
}

// ---------------------------------------------------------------- 進位轉換

/** 去掉空白與底線（BIN 分組只供顯示；送引擎、複製時都去掉）。 */
export function stripSpaces(text) {
  return String(text ?? "").replace(/[\s_]/g, "");
}

/** BIN 每 4 位一組（由右往左），以空白分隔。 */
export function groupBin(bits) {
  const s = stripSpaces(bits);
  const out = [];
  for (let end = s.length; end > 0; end -= 4) out.unshift(s.slice(Math.max(0, end - 4), end));
  return out.join(" ");
}

/** 組 base/convert 請求：以來源欄位的進位解讀；去空白後是空字串回傳 null（不送）。 */
export function baseRequest(sourceId, text, width, signed) {
  const t = stripSpaces(text);
  if (t === "") return null;
  return {
    sheet: "base", action: "convert",
    inputs: { TEXT: t, FROM: radixOf(sourceId), WIDTH: width, SIGNED: signed },
  };
}

/**
 * 引擎回傳的四個字串 → 要寫進各欄的顯示文字（BIN 分組；不加千分位）。
 * sourceId 那一欄是使用者正在輸入的，不覆寫（null＝四欄都更新，例：位元運算結果）。
 */
export function baseFieldUpdates(sourceId, values) {
  const out = {};
  for (const b of BASES) {
    if (b.id === sourceId) continue;
    const v = String(values[b.id] ?? "");
    out[b.id] = b.id === "BIN" ? groupBin(v) : v;
  }
  return out;
}

/** 位元運算畫面建立的輸入欄位 id（與 sheets.js 的 base-bitwise 欄位 id 相同，測試比對）。 */
export const BITWISE_INPUT_IDS = ["A", "OP", "B"];

/** 這個運算需要 B 嗎（NOT 只要 A）。 */
export function needsB(op) {
  return op !== "NOT";
}

/** SAR（算術右移）只適用於有號數。 */
export function opAllowed(op, signed) {
  return op !== "SAR" || Boolean(signed);
}

/**
 * 組 base/bitwise 請求；A、B 以 fromId 的進位解讀（去空白）。
 * A 空白、或需要 B 而 B 空白：回傳 null（不送）。NOT 不送 B。
 */
export function bitwiseRequest({ op, a, b, fromId, width, signed }) {
  const A = stripSpaces(a);
  const B = stripSpaces(b);
  if (A === "" || (needsB(op) && B === "")) return null;
  const inputs = { OP: op, A };
  if (needsB(op)) inputs.B = B;
  Object.assign(inputs, { FROM: radixOf(fromId), WIDTH: width, SIGNED: signed });
  return { sheet: "base", action: "bitwise", inputs };
}

// ---------------------------------------------------------------- 序號防亂序

/**
 * 序號（sequence guard）：每次送出前 next() 取號；回應到達時 isCurrent(號碼) 為 true 才套用。
 * 輸入改變時 bump() 讓進行中的請求全部作廢（與 ICONV 的 seq 寫法相同）。
 */
export function createSeq() {
  let n = 0;
  return {
    next: () => ++n,
    bump: () => ++n,
    isCurrent: (token) => token === n,
  };
}
