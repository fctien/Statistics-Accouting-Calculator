// Controller 輔助：使用者設定（settings）。目前只用 localStorage 當「單一裝置的便利記憶」，
// Task 25 會改存 IndexedDB。localStorage 可能不存在或丟例外（私密視窗、Node 測試），一律 try/catch，
// 讀不到就用預設值，畫面照常運作。

const KEY = "bacalc.settings";

/** 預設值：小數 2 位、美式千分位、AOS 運算順序、外觀跟隨系統。 */
export const DEFAULTS = Object.freeze({ decimals: 2, sep: "us", mode: "AOS", theme: "auto" });

const VALID = {
  decimals: (v) => v === null || (Number.isInteger(v) && v >= 0 && v <= 9),
  sep: (v) => v === "us" || v === "eu",
  mode: (v) => v === "AOS" || v === "CHAIN",
  theme: (v) => v === "auto" || v === "light" || v === "dark",
};

let cache = null;

function storage() {
  try {
    return globalThis.localStorage || null;
  } catch (e) {
    return null;
  }
}

/** 只保留合法的鍵值；不合法的忽略（回到預設）。 */
function sanitize(obj) {
  const out = {};
  if (!obj || typeof obj !== "object") return out;
  for (const k of Object.keys(VALID)) {
    if (k in obj && VALID[k](obj[k])) out[k] = obj[k];
  }
  return out;
}

/** 目前設定（預設值＋已儲存值）。 */
export function get() {
  if (cache) return { ...cache };
  let saved = {};
  try {
    const raw = storage()?.getItem(KEY);
    if (raw) saved = sanitize(JSON.parse(raw));
  } catch (e) {
    saved = {};
  }
  cache = { ...DEFAULTS, ...saved };
  return { ...cache };
}

/**
 * 更新設定；回傳 {settings, errors}。不合法的值不寫入，errors 以鍵為鍵、值為中文訊息。
 * 儲存失敗（storage 不可用）不算錯誤：本次開啟期間仍有效。
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
  try {
    storage()?.setItem(KEY, JSON.stringify(next));
  } catch (e) {
    /* 私密視窗或已停用網站資料：只在記憶體中生效 */
  }
  return { settings: { ...next }, errors };
}

/** 送給引擎的 settings（bridge 只認 decimals、sep、mode）。 */
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

/** 測試用：清除記憶體快取。 */
export function _resetCache() {
  cache = null;
}
