// Model：JSON 備份的匯出、驗證、合併（純函式，可用 node --test 測試；不碰 DOM 與 IndexedDB）。
// 匯出檔形狀：{app:"BACalc", schema:1, exported_at, data:{settings, scenarios, tape, memory}}。
// 匯入的資料一律不盲信：驗證結構之後，設定經 settings.sanitize、記憶經 memstore.fromJSON、
// 紙帶經 tape.createTape，不合格的項目在這裡被丟棄（normalizeData）。
import { fromJSON as memFromJSON } from "../memstore.js";
import { createTape, MAX_ENTRIES } from "../tape.js";
import { sanitize as sanitizeSettings } from "../settings.js";
import { SHEETS, fieldMap } from "../sheets.js";
import { SEP_KINDS, canonicalText, convertSepText, sameUnderBothSeps } from "../input.js";

export const APP_NAME = "BACalc";
export const SCHEMA = 1;
export const MAX_TAPE = MAX_ENTRIES;
export const MAX_SCENARIOS = 1000;
export const MAX_NAME = 80;
export const MAX_GRID_ROWS = 500;
export const MAX_GRID_COLS = 10;
export const GRID_KEY = "__grid"; // 情境 inputs 內存放表格（CF、STAT）內容的鍵

const isObj = (v) => v !== null && typeof v === "object" && !Array.isArray(v);
const toMs = (now) => (now instanceof Date ? now.getTime() : Number(now));

/** 台北時間（+08:00）的 ISO 字串，例：2026-10-19T10:00:00+08:00。不使用地區格式化。 */
export function isoTaipei(now = Date.now()) {
  return new Date(toMs(now) + 8 * 3600 * 1000).toISOString().slice(0, 19) + "+08:00";
}

/** 本機時間的 "YYYY-MM-DD HH:MM"（用 ISO 字串切片，不用 toLocale*）。 */
export function localStamp(now = Date.now()) {
  const d = new Date(toMs(now));
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16).replace("T", " ");
}

/** 備份檔名：bacalc-backup-YYYYMMDD.json（本機日期）。 */
export function backupFilename(now = Date.now()) {
  return `bacalc-backup-${localStamp(now).slice(0, 10).replace(/-/g, "")}.json`;
}

/** 空資料。 */
export function emptyData() {
  return { settings: {}, scenarios: [], tape: [], memory: {} };
}

/** 組出匯出物件。 */
export function makeExport(data, now = Date.now()) {
  return {
    app: APP_NAME,
    schema: SCHEMA,
    exported_at: isoTaipei(now),
    data: {
      settings: data.settings,
      scenarios: data.scenarios,
      tape: data.tape,
      memory: data.memory,
    },
  };
}

/** 驗證匯入物件；回傳 {ok:true} 或 {ok:false, error}（error 為中文原因）。 */
export function validateImport(obj) {
  const bad = (error) => ({ ok: false, error });
  if (!isObj(obj)) return bad("檔案內容不是 BACalc 備份（最外層必須是物件）");
  if (obj.app !== APP_NAME) return bad(`這不是 BACalc 的備份檔（app 欄位應為 "${APP_NAME}"）`);
  if (obj.schema !== SCHEMA) {
    return bad(`不支援的備份版本 schema：${JSON.stringify(obj.schema)}（本程式只讀 schema ${SCHEMA}）`);
  }
  if (!isObj(obj.data)) return bad("備份檔缺少 data 欄位或型別不對");
  const d = obj.data;
  if (!isObj(d.settings)) return bad("data.settings 缺少或型別不對（應為物件）");
  if (!Array.isArray(d.scenarios)) return bad("data.scenarios 缺少或型別不對（應為陣列）");
  if (!Array.isArray(d.tape)) return bad("data.tape 缺少或型別不對（應為陣列）");
  if (!isObj(d.memory)) return bad("data.memory 缺少或型別不對（應為物件）");
  const ids = new Set();
  for (let i = 0; i < d.scenarios.length; i++) {
    const s = d.scenarios[i];
    const at = `data.scenarios[${i}]`;
    if (!isObj(s)) return bad(`${at} 不是物件`);
    for (const k of ["id", "worksheet", "name", "updated_at"]) {
      if (typeof s[k] !== "string" || s[k] === "") return bad(`${at} 缺少 ${k} 或型別不對（應為非空字串）`);
    }
    if (!isObj(s.inputs)) return bad(`${at} 缺少 inputs 或型別不對（應為物件）`);
    if (ids.has(s.id)) return bad(`${at} 的 id 重複：${s.id}`);
    ids.add(s.id);
  }
  if (d.tape.length > MAX_TAPE) {
    return bad(`紙帶有 ${d.tape.length} 筆，超過上限 ${MAX_TAPE} 筆，拒絕匯入`);
  }
  return { ok: true };
}

/** 紙帶項目只留合法的（算式字串、有限數值），ts 不是有限數時記為 0。 */
function normalizeTape(list) {
  const clean = list.filter((e) => e && typeof e.expr === "string" && Number.isFinite(e.value))
    .map((e) => ({ ...e, ts: Number.isFinite(e.ts) ? e.ts : 0 }));
  return createTape(MAX_TAPE, clean).toJSON();
}

/** 表格內容：1～500 列、每列 1～10 欄的字串；形狀不合回傳 null。 */
export function sanitizeGrid(g) {
  if (!Array.isArray(g) || g.length < 1 || g.length > MAX_GRID_ROWS) return null;
  for (const row of g) {
    if (!Array.isArray(row) || row.length < 1 || row.length > MAX_GRID_COLS) return null;
    if (!row.every((c) => typeof c === "string" && c.length <= 100)) return null;
  }
  return g.map((r) => r.slice());
}

/** 一個欄位的儲存狀態：只留 text／direction／exact／checked 四種合法形狀；不合法回傳 null。 */
function sanitizeFieldState(st) {
  if (!isObj(st)) return null;
  if (typeof st.checked === "boolean" && !("text" in st)) return { checked: st.checked };
  if (typeof st.text !== "string" || st.text.length > 1000) return null;
  const out = { text: st.text };
  if (st.direction === "in" || st.direction === "out") out.direction = st.direction;
  if (typeof st.exact === "number" && Number.isFinite(st.exact)) out.exact = st.exact;
  return out;
}

/** 清理情境的 inputs：只留該工作表已知的輸入欄位 id 與合法的表格內容。 */
export function sanitizeScenarioInputs(worksheet, inputs) {
  const known = new Set(SHEETS[worksheet].fields.filter((f) => !f.output).map((f) => f.id));
  const out = {};
  for (const [k, v] of Object.entries(inputs)) {
    if (k === GRID_KEY) {
      const g = sanitizeGrid(v);
      if (g) out[GRID_KEY] = g;
    } else if (known.has(k)) {
      const st = sanitizeFieldState(v);
      if (st) out[k] = st;
    }
  }
  return out;
}

/** 把已通過 validateImport 的 data 清理成可安全寫入的形狀：不合格的設定鍵、記憶值、紙帶項目被丟棄。 */
export function normalizeData(data) {
  return {
    settings: sanitizeSettings(data.settings),
    scenarios: data.scenarios
      .filter((s) => Object.prototype.hasOwnProperty.call(SHEETS, s.worksheet)) // 不認得的工作表丟棄
      .slice(0, MAX_SCENARIOS)
      .map((s) => ({
        id: s.id, worksheet: s.worksheet, name: s.name.slice(0, MAX_NAME),
        inputs: sanitizeScenarioInputs(s.worksheet, s.inputs), updated_at: s.updated_at,
        ...(s.sep === "us" || s.sep === "eu" ? { sep: s.sep } : {}), // 儲存時的千分位設定
      })),
    tape: normalizeTape(data.tape),
    memory: memFromJSON(data.memory).toJSON(),
  };
}

const time = (s) => {
  const t = Date.parse(s);
  return Number.isFinite(t) ? t : -Infinity;
};

/** 兩個情境誰比較新（updated_at）；無法解析的時間當最舊，同時間取 a（呼叫端把 incoming 放前面）。 */
function newer(a, b) {
  const ta = time(a.updated_at);
  const tb = time(b.updated_at);
  if (ta !== tb) return ta > tb ? a : b;
  return a;
}

/**
 * 合併本機 local 與匯入 incoming（兩者皆為 normalizeData 後的形狀）。
 * mode "replace"：incoming 整份取代。
 * mode "merge"：scenarios 依 id，保留 updated_at 較新的（相同時間取 incoming）；settings 以 incoming 覆蓋；
 *   tape 串接後依 ts 排序（相同時間維持原順序），完全相同的項目（ts、算式、值）只留一筆，保留最新的 500 筆；
 *   memory 以 incoming 覆蓋。
 */
export function mergeData(local, incoming, mode) {
  if (mode !== "merge" && mode !== "replace") throw new Error("mode 必須是 merge 或 replace");
  const copy = (x) => JSON.parse(JSON.stringify(x));
  if (mode === "replace") return copy(incoming);
  const byId = new Map();
  for (const s of local.scenarios) byId.set(s.id, s);
  for (const s of incoming.scenarios) {
    const cur = byId.get(s.id);
    byId.set(s.id, cur ? newer(s, cur) : s);
  }
  const seen = new Set();
  const tape = [...local.tape, ...incoming.tape]
    .map((e, i) => ({ e, i }))
    .sort((a, b) => (a.e.ts - b.e.ts) || (a.i - b.i))
    .map((x) => x.e)
    .filter((e) => {
      const k = `${e.ts}|${e.expr}|${e.value}`;
      if (seen.has(k)) return false;
      seen.add(k);
      return true;
    })
    .slice(-MAX_TAPE);
  return copy({
    settings: { ...local.settings, ...incoming.settings },
    scenarios: [...byId.values()],
    tape,
    memory: incoming.memory,
  });
}

/**
 * 整個匯入流程（純函式）：驗證 → 清理 → 合併。
 * 成功回傳 {ok:true, data, counts:{scenarios, tape, settings, memory}}（counts 是「檔案內」的數量）；
 * 失敗回傳 {ok:false, error}。
 */
export function importBackup(obj, local, mode) {
  const v = validateImport(obj);
  if (!v.ok) return v;
  const incoming = normalizeData(obj.data);
  const base = normalizeData({ ...emptyData(), ...local });
  const data = mergeData(base, incoming, mode);
  const m = incoming.memory;
  const memCells = Object.keys(m).filter((k) => /^M\d$/.test(k) && m[k] !== 0).length;
  return {
    ok: true,
    data,
    counts: {
      scenarios: incoming.scenarios.length,
      tape: incoming.tape.length,
      settings: Object.keys(incoming.settings).length,
      memory: memCells + (m.ACC && m.ACC.count > 0 ? 1 : 0),
    },
  };
}

const SEP_NAME = { us: "1,234.5（US）", eu: "1.234,5（EU）" };

/**
 * 載入情境前的千分位（sep）換算（純函式）：情境存的是使用者打的原始文字，
 * 以「情境記錄的 sep」解析後改寫成目前設定（currentSep）的標準寫法，數值不變。
 * - 情境 sep 與目前相同：原樣
 * - 有引擎完整精度 exact：直接用 exact 改寫（不需要猜）
 * - 情境 sep 下解不出：該欄位列入 errors（中文訊息），呼叫端標紅、不可當成數字送出
 * - 情境沒有 sep（舊資料、匯入）：只有在 US 與 EU 下解析結果相同時才接受，否則列入 errors
 * 表格（__grid）每格同樣處理；任一格無法確定 → gridError（呼叫端不載入表格）。
 * 回傳 {inputs, errors: {欄位 id: 訊息}, gridError: 訊息 | null}。
 */
export function prepareScenarioForLoad(scenario, currentSep) {
  const from = scenario.sep === "us" || scenario.sep === "eu" ? scenario.sep : null;
  const fm = SHEETS[scenario.worksheet] ? fieldMap(scenario.worksheet) : {};
  const inputs = {};
  const errors = {};
  let gridError = null;
  const why = (text) => (from
    ? `情境中的「${text}」無法用儲存時的千分位格式 ${SEP_NAME[from]} 解讀，請重新輸入`
    : `情境沒有記錄千分位格式，「${text}」在 1,234.5 與 1.234,5 兩種寫法下數值不同，請重新輸入`);
  for (const [id, st] of Object.entries(scenario.inputs || {})) {
    if (id === GRID_KEY) continue;
    const f = fm[id];
    if (!f || !isObj(st) || typeof st.text !== "string" || !SEP_KINDS.has(f.kind) || from === currentSep) {
      inputs[id] = st;
      continue;
    }
    if (typeof st.exact === "number" && Number.isFinite(st.exact) && f.kind !== "list") {
      const v = f.kind === "direction" ? Math.abs(st.exact) : st.exact;
      inputs[id] = { ...st, text: canonicalText(v, currentSep) };
      continue;
    }
    if (from) {
      const r = convertSepText(st.text, f, from, currentSep);
      if (r.error) errors[id] = why(st.text);
      inputs[id] = r.error ? st : { ...st, text: r.text };
    } else {
      if (!sameUnderBothSeps(st.text, f)) errors[id] = why(st.text);
      inputs[id] = st;
    }
  }
  const g = scenario.inputs ? scenario.inputs[GRID_KEY] : undefined;
  if (g !== undefined) {
    if (!Array.isArray(g) || from === currentSep) {
      inputs[GRID_KEY] = g;
    } else {
      const num = { kind: "number" };
      const out = [];
      for (const row of g) {
        const cells = [];
        for (const cell of Array.isArray(row) ? row : []) {
          if (typeof cell !== "string" || cell.trim() === "") {
            cells.push(cell);
            continue;
          }
          const r = from ? convertSepText(cell, num, from, currentSep)
            : (sameUnderBothSeps(cell, num) ? { text: cell } : { error: true });
          if (r.error && !gridError) {
            gridError = `表格${why(cell).replace(/^情境/, "")}；表格沒有載入`;
          }
          cells.push(r.error ? cell : r.text);
        }
        out.push(cells);
      }
      inputs[GRID_KEY] = gridError ? null : out;
    }
  }
  return { inputs, errors, gridError };
}
