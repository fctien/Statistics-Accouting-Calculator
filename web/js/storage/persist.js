// Controller：把設定以外的狀態存進 IndexedDB（settings 由 settings.js 自己存）。
//  - 紙帶 tape：每次變動後延遲約 300 ms 寫入（debounce），最多 500 筆（由 tape.js 控制）
//  - 記憶 memory：每次成功的記憶操作後寫入
//  - 情境 scenarios：每個情境一筆，keyPath id
//  - readAll／writeAll：備份匯出入用（整份資料）
import * as idb from "./idb.js";
import { emptyData } from "./backup.js";

export const TAPE_DEBOUNCE_MS = 300;

let tapeTimer = null;
let tapePending = null;

function writeTape(entries) {
  return idb.put("tape", { key: "tape", entries }).catch(() => {});
}

/** 排程儲存紙帶（連續變動只寫最後一次）。 */
export function saveTape(entries) {
  tapePending = entries;
  if (tapeTimer !== null) clearTimeout(tapeTimer);
  tapeTimer = setTimeout(() => {
    tapeTimer = null;
    const e = tapePending;
    tapePending = null;
    writeTape(e);
  }, TAPE_DEBOUNCE_MS);
}

/** 立刻寫入尚未寫出的紙帶（匯出前）。 */
export async function flushTape() {
  if (tapeTimer === null) return;
  clearTimeout(tapeTimer);
  tapeTimer = null;
  const e = tapePending;
  tapePending = null;
  await writeTape(e);
}

/** 放棄尚未寫出的紙帶（匯入／清除之前，避免舊資料蓋掉新資料）。 */
export function cancelTape() {
  if (tapeTimer !== null) clearTimeout(tapeTimer);
  tapeTimer = null;
  tapePending = null;
}

/** 儲存記憶（M0～M9、ACC），形狀同 memstore.toJSON()。 */
export function saveMemory(data) {
  return idb.put("memory", { key: "memory", data }).catch(() => {});
}

/** 啟動時讀回紙帶與記憶；沒有或讀取失敗時為 null（呼叫端再驗證內容）。 */
export async function loadState() {
  const out = { tape: null, memory: null };
  try {
    const t = await idb.get("tape", "tape");
    if (t && Array.isArray(t.entries)) out.tape = t.entries;
    const m = await idb.get("memory", "memory");
    if (m && m.data && typeof m.data === "object") out.memory = m.data;
  } catch (e) {
    /* 讀不到就當沒有資料 */
  }
  return out;
}

// ---- 情境
export async function listScenarios(worksheet) {
  const rows = await idb.all("scenarios");
  return rows.filter((s) => s.worksheet === worksheet)
    .sort((a, b) => (a.updated_at < b.updated_at ? 1 : a.updated_at > b.updated_at ? -1 : 0));
}
export const saveScenario = (s) => idb.put("scenarios", s);
export const deleteScenario = (id) => idb.del("scenarios", id);

// ---- 整份資料（備份）
/** 讀出整份資料（設定、情境、紙帶、記憶）；先把待寫的紙帶寫出。 */
export async function readAll() {
  await flushTape();
  const data = emptyData();
  const s = await idb.get("settings", "settings");
  if (s && s.value && typeof s.value === "object") data.settings = s.value;
  data.scenarios = await idb.all("scenarios");
  const st = await loadState();
  if (st.tape) data.tape = st.tape;
  if (st.memory) data.memory = st.memory;
  return data;
}

/** 以 data 取代 IndexedDB 內的全部資料（data 須先經 normalizeData）。 */
export async function writeAll(data) {
  cancelTape();
  await idb.clear("scenarios");
  for (const s of data.scenarios) await idb.put("scenarios", s);
  await idb.put("settings", { key: "settings", value: data.settings });
  await idb.put("tape", { key: "tape", entries: data.tape });
  await idb.put("memory", { key: "memory", data: data.memory });
}
