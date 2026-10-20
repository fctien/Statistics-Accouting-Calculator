// Controller 輔助：使用者設定（settings）。存在 IndexedDB（storage/idb.js，物件庫 settings，單一紀錄 key "settings"）。
// 為了讓 get() 維持同步：啟動時（畫面掛載前）呼叫 init() 把設定載入記憶體，之後 get() 只讀記憶體，
// set() 更新記憶體並在背景寫入 IndexedDB。IndexedDB 不可用時只在記憶體生效（idb.js 會提示使用者一次）。
// init() 同時做一次性搬家：舊版存在 localStorage 的設定，寫進 IndexedDB 後移除舊的鍵。
import * as idb from "./storage/idb.js";

const KEY = "bacalc.settings";

/**
 * 預設值：小數 2 位、美式千分位、AOS 運算順序、外觀跟隨系統、日期顯示美式 mm/dd/yyyy、
 * 稅率預設值不指定（taxPreset 為 TAX_PRESETS 的名稱，空字串＝自訂）。
 */
export const DEFAULTS = Object.freeze({
  decimals: 2, sep: "us", mode: "AOS", theme: "auto", dateFmt: "us", taxPreset: "",
  gdriveClientId: "", gdriveLastSync: "", gdriveLastSyncHash: "", // Google Drive 同步（選用）：Client ID、上次同步的雲端時間
});

const VALID = {
  decimals: (v) => v === null || (Number.isInteger(v) && v >= 0 && v <= 9),
  sep: (v) => v === "us" || v === "eu",
  mode: (v) => v === "AOS" || v === "CHAIN",
  theme: (v) => v === "auto" || v === "light" || v === "dark",
  dateFmt: (v) => v === "us" || v === "eu",
  taxPreset: (v) => typeof v === "string" && v.length <= 40,
  gdriveClientId: (v) => typeof v === "string" && (v === "" || /^[A-Za-z0-9._-]{1,200}\.apps\.googleusercontent\.com$/.test(v)),
  gdriveLastSync: (v) => typeof v === "string" && v.length <= 40,
  gdriveLastSyncHash: (v) => typeof v === "string" && /^[0-9a-f]{0,64}$/.test(v),
};

let cache = null;

/** 舊版 localStorage 的鍵（只用於一次性搬家）。 */
function legacyStorage() {
  try {
    return globalThis.localStorage || null;
  } catch (e) {
    return null;
  }
}

/** 只保留合法的鍵值；不合法的忽略（回到預設）。 */
export function sanitize(obj) {
  const out = {};
  if (!obj || typeof obj !== "object") return out;
  for (const k of Object.keys(VALID)) {
    if (k in obj && VALID[k](obj[k])) out[k] = obj[k];
  }
  return out;
}

/** 目前設定（預設值＋已載入的值）。 */
export function get() {
  if (!cache) cache = { ...DEFAULTS };
  return { ...cache };
}

/** 背景寫入 IndexedDB；失敗（idb.js 已提示）不影響目前運作。 */
/** 回傳是否真的寫進 IndexedDB（false＝只在記憶體或失敗）。 */
function persist(value) {
  return idb.put("settings", { key: "settings", value }).catch(() => false);
}

/**
 * 啟動時載入設定（畫面掛載前呼叫一次）：讀 IndexedDB；沒有紀錄時嘗試從舊版 localStorage 搬家，
 * 搬成功（確定寫進 IndexedDB）才移除舊的鍵。回傳載入後的設定。
 */
export async function init() {
  let saved = null;
  try {
    const rec = await idb.get("settings", "settings");
    if (rec && typeof rec.value === "object") saved = sanitize(rec.value);
  } catch (e) {
    saved = null;
  }
  if (saved === null) {
    const ls = legacyStorage();
    let legacy = null;
    try {
      const raw = ls?.getItem(KEY);
      if (raw) legacy = sanitize(JSON.parse(raw));
    } catch (e) {
      legacy = null;
    }
    if (legacy !== null) {
      saved = legacy;
      cache = { ...DEFAULTS, ...saved };
      const written = await persist(cache);
      if (written === true) {
        try {
          ls.removeItem(KEY);
        } catch (e) {
          /* 無法移除舊鍵：下次啟動會因為 IndexedDB 已有紀錄而忽略它 */
        }
      }
    }
  }
  cache = { ...DEFAULTS, ...(saved || {}) };
  return { ...cache };
}

/**
 * 更新設定；回傳 {settings, errors}。不合法的值不寫入，errors 以鍵為鍵、值為中文訊息。
 * 儲存失敗（IndexedDB 不可用）不算錯誤：本次開啟期間仍有效。
 */
export function set(patch) {
  const errors = {};
  const next = get();
  for (const [k, v] of Object.entries(patch || {})) {
    if (!(k in VALID)) continue;
    if (VALID[k](v)) next[k] = v;
    else errors[k] = `${k} 的值不合法`;
  }
  cache = next;
  persist(next);
  return { settings: { ...next }, errors };
}

/** 送給引擎的 settings（bridge 只認 decimals、sep、mode；dateFmt、taxPreset 只供畫面使用）。 */
export function toEngine(s = get()) {
  return { decimals: s.decimals, sep: s.sep, mode: s.mode };
}

/** 套用外觀：auto 移除 data-theme（跟隨 prefers-color-scheme），light／dark 寫入 <html>。 */
export function applyTheme(s = get()) {
  const root = globalThis.document?.documentElement;
  if (!root) return;
  if (s.theme === "light" || s.theme === "dark") root.dataset.theme = s.theme;
  else delete root.dataset.theme;
}

/**
 * 更新設定並立即生效：寫入、套用外觀、並通知畫面（document 事件 "bacalc-settings"），
 * 讓目前顯示的結果、紙帶、日期讀數用新格式重新顯示。回傳 {settings, errors}。
 */
export function commit(patch) {
  const r = set(patch);
  applyTheme(r.settings);
  const doc = globalThis.document;
  if (doc && typeof CustomEvent === "function") {
    doc.dispatchEvent(new CustomEvent("bacalc-settings", { detail: r.settings }));
  }
  return r;
}

/**
 * 整組取代設定（匯入「取代」、清除全部資料用）：不在 DEFAULTS 內或不合法的鍵回到預設值。
 * 寫入、套用外觀並通知畫面；回傳新設定。
 */
export function replace(obj) {
  const next = { ...DEFAULTS, ...sanitize(obj) };
  cache = next;
  persist(next);
  applyTheme(next);
  const doc = globalThis.document;
  if (doc && typeof CustomEvent === "function") {
    doc.dispatchEvent(new CustomEvent("bacalc-settings", { detail: { ...next } }));
  }
  return { ...next };
}

/** 測試用：清除記憶體快取。 */
export function _resetCache() {
  cache = null;
}
