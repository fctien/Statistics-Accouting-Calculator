// View 輔助：輸入解析（純函式，不碰 DOM，可在 Node 測試）。
// 規則與引擎 engine/fmt.py 的 parse_number 相同（US／EU 千分位、全形數字、1e3），
// 在 Python 尚未載入前也能即時驗證；tests/test_web_input.py 逐案比對兩邊結果。
// 百分比欄位一律用「百分數」（5 或 5% 都代表 5，送給引擎的就是 5）。

const SEPS = { us: [",", "."], eu: [".", ","] }; // [千分位, 小數點]
const DIGITS = "0123456789";
const FULL_DIGITS = "０１２３４５６７８９";

/** 全形數字、全形負號（－）、全形空白轉半形（與 fmt._normalize 相同）。 */
function normalize(text) {
  let out = "";
  for (const ch of text) {
    const k = FULL_DIGITS.indexOf(ch);
    if (k >= 0) out += DIGITS[k];
    else if (ch === "－") out += "-";
    else if (ch === "　") out += " ";
    else out += ch;
  }
  return out;
}

function allDigits(s) {
  return s !== "" && /^[0-9]+$/.test(s);
}

/** 整數部分：純數字，或千分位分組正確（首組 1～3 位，其後每組 3 位）。 */
function validIntPart(s, tsep) {
  if (!s.includes(tsep)) return allDigits(s);
  const groups = s.split(tsep);
  if (groups[0].length < 1 || groups[0].length > 3 || !allDigits(groups[0])) return false;
  return groups.slice(1).every((g) => g.length === 3 && allDigits(g));
}

/**
 * 解析數字文字（parse number）；無法解析或結果非有限數回傳 null。
 * sep："us"（1,234.56）或 "eu"（1.234,56）。
 */
export function parseNumber(text, sep = "us") {
  if (!(sep in SEPS) || typeof text !== "string") return null;
  const [tsep, dsep] = SEPS[sep];
  // Python str.strip() 去除 Unicode 空白；JS trim() 範圍相近
  let s = normalize(text).trim();
  let sign = "";
  if (s[0] === "+" || s[0] === "-") {
    sign = s[0] === "-" ? "-" : "";
    s = s.slice(1);
  }
  let exp = "";
  const low = s.toLowerCase();
  const ei = low.indexOf("e");
  if (ei >= 0) {
    exp = low.slice(ei + 1);
    s = s.slice(0, ei);
    const body = exp[0] === "+" || exp[0] === "-" ? exp.slice(1) : exp;
    if (!allDigits(body)) return null;
  }
  if (s.split(dsep).length - 1 > 1) return null;
  let ip = s;
  let fp = "";
  if (s.includes(dsep)) [ip, fp] = s.split(dsep);
  if (ip === "" && fp === "") return null;
  if (ip !== "" && !validIntPart(ip, tsep)) return null;
  if (fp !== "" && !allDigits(fp)) return null;
  const clean = ip.split(tsep).join("") || "0";
  let literal = sign + clean + (fp ? "." + fp : "");
  if (exp) literal += "e" + exp;
  const v = Number(literal);
  return Number.isFinite(v) ? v : null;
}

/** 百分比：接受 "5" 或 "5%"（含全形 ％），回傳百分數 5；不合法回傳 null。 */
export function parsePercent(text, sep = "us") {
  if (typeof text !== "string") return null;
  let s = normalize(text).trim().replace(/％$/, "%");
  if (s.endsWith("%")) s = s.slice(0, -1).trimEnd();
  return parseNumber(s, sep);
}

function isLeap(y) {
  return (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0;
}

function daysInMonth(y, m) {
  return [31, isLeap(y) ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1];
}

/**
 * 日期：接受 "2026-10-20"、"2026/10/20"、"2026.10.20"（年-月-日，input type=date 的值即此格式），
 * 回傳 [年, 月, 日]；不存在的日期（如 2023-02-29）回傳 null。
 */
export function parseDate(text) {
  if (typeof text !== "string") return null;
  const m = /^(\d{1,4})[-/.](\d{1,2})[-/.](\d{1,2})$/.exec(normalize(text).trim());
  if (!m) return null;
  const [y, mo, d] = [Number(m[1]), Number(m[2]), Number(m[3])];
  if (y < 1 || mo < 1 || mo > 12 || d < 1 || d > daysInMonth(y, mo)) return null;
  return [y, mo, d];
}

/**
 * 數列（list）：以換行、分號、空白分隔；US 模式另允許「1, 2」這種逗號後接空白的寫法。
 * pairs=true 時每一項（換行或分號分隔）為「金額」或「金額 x 次數」（x、×、* 皆可），
 * 回傳 [[金額, 次數], ...]（次數省略為 1）。空白回傳 []；任一項不合法回傳 null。
 */
export function parseList(text, sep = "us", pairs = false) {
  if (typeof text !== "string") return null;
  const s = normalize(text).trim();
  if (s === "") return [];
  if (pairs) {
    const out = [];
    for (const item of s.split(/[\n;；]+/).map((t) => t.trim()).filter(Boolean)) {
      const parts = item.split(/\s*[x×X*]\s*/);
      if (parts.length > 2) return null;
      const amt = parseNumber(parts[0], sep);
      const cnt = parts.length === 2 ? parseNumber(parts[1], sep) : 1;
      if (amt === null || cnt === null) return null;
      out.push([amt, cnt]);
    }
    return out;
  }
  // US：千分位是逗號，只有「逗號＋空白」才當分隔；EU：逗號是小數點，不當分隔
  const tokens = s.split(/[\s;；]+/).filter(Boolean)
    .map((t) => (sep === "us" && t.endsWith(",") ? t.slice(0, -1) : t));
  const out = [];
  for (const t of tokens) {
    const v = parseNumber(t, sep);
    if (v === null) return null;
    out.push(v);
  }
  return out;
}

/** 收到（in）為正、付出（out）為負；value 為 null 時回傳 null。 */
export function toSigned(value, direction) {
  if (direction !== "in" && direction !== "out") {
    throw new Error("direction 必須是 in 或 out：" + direction);
  }
  if (value === null || value === undefined) return null;
  const mag = Math.abs(value);
  if (mag === 0) return 0; // 避免 -0
  return direction === "out" ? -mag : mag;
}

/** 有號數 → {value: 絕對值, direction}；負數為付出 out，0 與正數為收到 in。 */
export function fromSigned(value) {
  if (value === null || value === undefined) return { value: null, direction: null };
  return { value: Math.abs(value), direction: value < 0 ? "out" : "in" };
}

/**
 * 拆出開頭的正負號（sign）：回傳 {text: 其餘文字, direction: "out"|"in"|null}。
 * 「-」（含全形「－」）→ 付出 out、「+」→ 收到 in；沒有正負號時 direction 為 null。
 * direction 欄位用：使用者打入的正負號優先於方向鈕（TI 正負號慣例）。
 */
export function splitSign(text) {
  const s = normalize(String(text ?? "")).trim();
  const m = /^([+-])\s*/.exec(s);
  if (!m) return { text: s, direction: null };
  return { text: s.slice(m[0].length), direction: m[1] === "-" ? "out" : "in" };
}

/** 欄位規格正規化：接受 "number" 這種字串，或 {kind, label, options, ...} 物件。 */
function specOf(id, k) {
  const spec = typeof k === "string" ? { kind: k } : { ...(k || {}) };
  spec.kind = spec.kind || "number";
  spec.label = spec.label || id;
  return spec;
}

function example(sep) {
  return sep === "eu" ? "1.234,5" : "1,234.5";
}

function isBlank(raw) {
  return raw === null || raw === undefined || (typeof raw === "string" && raw.trim() === "");
}

/** 解析單一欄位，回傳 {value} 或 {error}。 */
function parseOne(raw, spec, sep) {
  const L = spec.label;
  switch (spec.kind) {
    case "bool":
      if (raw === null || raw === undefined || raw === "") return { value: null };
      if (raw === true || raw === "true") return { value: true };
      if (raw === false || raw === "false") return { value: false };
      return { error: `${L}必須是「是」或「否」` };
    case "select": {
      if (isBlank(raw)) return { value: null };
      const opt = (spec.options || []).find((o) => String(o.value) === String(raw));
      return opt ? { value: opt.value } : { error: `${L}的選項不合法` };
    }
    case "date": {
      if (isBlank(raw)) return { value: null };
      const d = parseDate(String(raw));
      return d ? { value: d } : { error: `${L}不是有效日期，請用 年-月-日，例如 2026-10-20` };
    }
    case "list": {
      if (isBlank(raw)) return { value: null };
      const v = parseList(String(raw), sep, Boolean(spec.pairs));
      if (v === null) {
        return {
          error: spec.pairs
            ? `${L}格式錯誤：每行一筆「金額 x 次數」，例如 300 x 2`
            : `${L}格式錯誤：以空白或換行分隔數字，例如 1 2 3`,
        };
      }
      return { value: v };
    }
    case "text":
      return { value: isBlank(raw) ? null : String(raw).trim() };
    case "direction": {
      // {text, direction}：輸入框是絕對值，方向鈕決定正負；純字串則照 TI 正負號解讀。
      // 文字開頭打了正負號時，正負號優先（- → 付出、+ → 收到），並回報 direction 讓畫面更新方向鈕
      if (raw && typeof raw === "object") {
        if (isBlank(raw.text)) return { value: null };
        const sp = splitSign(raw.text);
        const bad = { error: `${L}格式錯誤：請輸入數字，例如 ${example(sep)}` };
        if (/^[+-]/.test(sp.text)) return bad; // 「--5」「-+5」：不猜
        const v = parseNumber(sp.text, sep);
        if (v === null) return bad;
        const dir = sp.direction || (raw.direction === "out" ? "out" : "in");
        return sp.direction ? { value: toSigned(v, dir), direction: dir } : { value: toSigned(v, dir) };
      }
      if (isBlank(raw)) return { value: null };
      const v = parseNumber(String(raw), sep);
      return v === null ? { error: `${L}格式錯誤：請輸入數字，例如 ${example(sep)}` } : { value: v };
    }
    case "percent": {
      if (isBlank(raw)) return { value: null };
      const v = parsePercent(String(raw), sep);
      return v === null ? { error: `${L}格式錯誤：請輸入百分比，例如 5 或 5%` } : { value: v };
    }
    default: {
      if (isBlank(raw)) return { value: null };
      const v = parseNumber(String(raw), sep);
      return v === null ? { error: `${L}格式錯誤：請輸入數字，例如 ${example(sep)}` } : { value: v };
    }
  }
}

/** 即時驗證（live validation）：positive（> 0）、min、integer。 */
function checkLimits(v, spec) {
  if (typeof v !== "number") return null;
  if (spec.positive && !(v > 0)) return `${spec.label}必須大於 0`;
  if (spec.min !== undefined && v < spec.min) return `${spec.label}不可小於 ${spec.min}`;
  if (spec.integer && !Number.isInteger(v)) return `${spec.label}必須是整數`;
  return null;
}

/**
 * 收集輸入（collect）：values 為 {欄位 id: 原始值}，kinds 為 {欄位 id: kind 字串或欄位定義}。
 * 回傳 {inputs, errors}：inputs 以引擎鍵（spec.key 或 id）為鍵、空白為 null、
 * 錯誤欄位亦為 null；errors 以欄位 id 為鍵、值為中文訊息。只處理 kinds 中列出的欄位。
 * directions：direction 欄位文字開頭打了正負號時 {欄位 id: "in"|"out"}（畫面據此更新方向鈕）。
 */
export function collect(values, kinds, sep = "us") {
  const inputs = {};
  const errors = {};
  const directions = {};
  for (const id of Object.keys(kinds)) {
    const spec = specOf(id, kinds[id]);
    const key = spec.key || id;
    const r = parseOne(values ? values[id] : undefined, spec, sep);
    const limit = r.error ? null : checkLimits(r.value, spec);
    if (r.error || limit) {
      errors[id] = r.error || limit;
      inputs[key] = null;
    } else {
      inputs[key] = r.value;
      if (r.direction) directions[id] = r.direction;
    }
  }
  return { inputs, errors, directions };
}

/**
 * 重新求解（re-solve）：留一格空白的工作表求出一格後，使用者改了別的欄位再按計算，
 * 此時已沒有空白；若「可求解欄位」（solveKeys）全都有值，就把上次引擎求出且未改動的
 * 欄位（solvedKeys，引擎鍵）視為空白，再求一次。使用者自己留了空白時不動。回傳新物件。
 */
export function resolveBlanks(inputs, solveKeys, solvedKeys) {
  if (!solveKeys || solveKeys.length === 0) return inputs;
  if (solveKeys.some((k) => inputs[k] === null || inputs[k] === undefined)) return inputs;
  const again = (solvedKeys || []).filter((k) => solveKeys.includes(k));
  if (again.length === 0) return inputs;
  const out = { ...inputs };
  for (const k of again) out[k] = null;
  return out;
}

// ---- 千分位設定（sep）換算：具名情境存的是原始文字，換了 US／EU 設定後要換寫法，不可重新解讀 ----

/** 會受 sep 影響的欄位種類（kind）。 */
export const SEP_KINDS = new Set(["number", "percent", "direction", "list"]);

/** 數值的標準寫法（canonical）：不加千分位；EU 的小數點用逗號（與 tables.numToText 相同）。 */
export function canonicalText(v, sep = "us") {
  const s = String(v);
  return sep === "eu" ? s.replace(".", ",") : s;
}

/**
 * 依欄位種類以 sep 解析文字；回傳數值（清單為陣列）或 null（無法解析）。
 * direction：開頭正負號照 TI 慣例（- 為負）。空白回傳 undefined。
 */
export function parseForSep(text, spec, sep) {
  if (typeof text !== "string" || text.trim() === "") return undefined;
  switch (spec.kind) {
    case "percent":
      return parsePercent(text, sep);
    case "list":
      return parseList(text, sep, Boolean(spec.pairs));
    case "direction": {
      const sp = splitSign(text);
      if (/^[+-]/.test(sp.text)) return null;
      const v = parseNumber(sp.text, sep);
      return v === null ? null : (sp.direction === "out" ? -v : v);
    }
    default:
      return parseNumber(text, sep);
  }
}

/**
 * 把 fromSep 寫的文字改寫成 toSep 的標準寫法；回傳 {text} 或 {error: true}（fromSep 下就解不出）。
 * 百分比保留 %、方向欄位保留開頭正負號、清單以空白（成對清單以換行與「x」）分隔。
 */
export function convertSepText(text, spec, fromSep, toSep) {
  if (typeof text !== "string" || text.trim() === "" || fromSep === toSep || !SEP_KINDS.has(spec.kind)) {
    return { text };
  }
  const c = (v) => canonicalText(v, toSep);
  switch (spec.kind) {
    case "percent": {
      const v = parsePercent(text, fromSep);
      if (v === null) return { error: true };
      return { text: c(v) + (/[%％]\s*$/.test(text) ? "%" : "") };
    }
    case "list": {
      const v = parseList(text, fromSep, Boolean(spec.pairs));
      if (v === null) return { error: true };
      if (spec.pairs) return { text: v.map(([a, n]) => (n === 1 ? c(a) : `${c(a)} x ${c(n)}`)).join("\n") };
      return { text: v.map(c).join(" ") };
    }
    case "direction": {
      const sp = splitSign(text);
      if (/^[+-]/.test(sp.text)) return { error: true };
      const v = parseNumber(sp.text, fromSep);
      if (v === null) return { error: true };
      const sign = sp.direction === "out" ? "-" : sp.direction === "in" ? "+" : "";
      return { text: sign + c(v) };
    }
    default: {
      const v = parseNumber(text, fromSep);
      return v === null ? { error: true } : { text: c(v) };
    }
  }
}

/** 文字在 US 與 EU 下解析結果是否相同（兩者都解不出也算相同：照樣是格式錯誤）。 */
export function sameUnderBothSeps(text, spec) {
  if (!SEP_KINDS.has(spec.kind)) return true;
  return JSON.stringify(parseForSep(text, spec, "us") ?? null)
    === JSON.stringify(parseForSep(text, spec, "eu") ?? null);
}
