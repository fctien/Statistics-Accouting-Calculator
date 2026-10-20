// Controller 輔助：IndexedDB 的 Promise 包裝（資料庫 "bacalc"，版本 1）。
// 物件庫（object store）：settings（keyPath "key"）、scenarios（keyPath "id"）、
// tape（單一紀錄，key "tape"）、memory（單一紀錄，key "memory"）。
// 介面：get／put／all／del／clear。任何一步失敗（私密視窗、被封鎖、逾時、沒有 indexedDB）都不丟例外：
// 改存在記憶體（只保留到關閉頁面），並透過 onUnavailable 回呼提醒使用者一次。

export const DB_NAME = "bacalc";
export const DB_VERSION = 1;
export const STORE_KEYS = Object.freeze({ settings: "key", scenarios: "id", tape: "key", memory: "key" });
export const UNAVAILABLE_MESSAGE = "此瀏覽器無法使用本機儲存，資料只保留到關閉頁面";
const OPEN_TIMEOUT_MS = 3000;

const fallback = {}; // store -> Map（IndexedDB 不可用時的記憶體備援）
for (const s of Object.keys(STORE_KEYS)) fallback[s] = new Map();

let dbPromise = null;
let usable = false; // 真的有開到資料庫
let noticeFn = null;
let noticePending = false;
let noticed = false;

function notice() {
  if (noticed) return;
  if (!noticeFn) {
    noticePending = true;
    return;
  }
  noticed = true;
  noticePending = false;
  try {
    noticeFn(UNAVAILABLE_MESSAGE);
  } catch (e) {
    /* 提示失敗不影響運作 */
  }
}

/** 註冊「本機儲存不可用」的提示回呼（只會呼叫一次）。 */
export function onUnavailable(fn) {
  noticeFn = fn;
  if (noticePending) notice();
}

/** 目前是否真的寫進 IndexedDB（false＝只在記憶體）。 */
export function isPersistent() {
  return usable;
}

function openDb() {
  if (dbPromise) return dbPromise;
  dbPromise = new Promise((resolve) => {
    let done = false;
    const finish = (db) => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      usable = db !== null;
      if (!db) notice();
      resolve(db);
    };
    const timer = setTimeout(() => finish(null), OPEN_TIMEOUT_MS);
    try {
      const idb = globalThis.indexedDB;
      if (!idb) return finish(null);
      const req = idb.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = () => {
        const db = req.result;
        for (const [name, keyPath] of Object.entries(STORE_KEYS)) {
          if (!db.objectStoreNames?.contains?.(name)) db.createObjectStore(name, { keyPath });
        }
      };
      req.onsuccess = () => {
        const db = req.result;
        db.onversionchange = () => db.close();
        finish(db);
      };
      req.onerror = () => finish(null);
      req.onblocked = () => finish(null);
    } catch (e) {
      finish(null);
    }
  });
  return dbPromise;
}

/** 在 store 上執行 fn(objectStore)；fn 回傳 IDBRequest。mode 為 "readonly"／"readwrite"。失敗回傳 {failed:true}。 */
function run(db, store, mode, fn) {
  return new Promise((resolve) => {
    try {
      const tx = db.transaction(store, mode);
      const req = fn(tx.objectStore(store));
      let result;
      if (req) req.onsuccess = () => { result = req.result; };
      tx.oncomplete = () => resolve({ value: result });
      tx.onerror = () => resolve({ failed: true });
      tx.onabort = () => resolve({ failed: true });
    } catch (e) {
      resolve({ failed: true });
    }
  });
}

async function exec(store, mode, fn, memFn) {
  if (!(store in STORE_KEYS)) throw new Error("未知的物件庫：" + store);
  const db = await openDb();
  if (db) {
    const r = await run(db, store, mode, fn);
    if (!r.failed) return r.value;
    notice(); // 單次操作失敗（例：配額已滿）：這一筆退回記憶體
  }
  return memFn(fallback[store]);
}

/** 讀一筆；沒有回傳 undefined。 */
export function get(store, key) {
  return exec(store, "readonly", (s) => s.get(key), (m) => m.get(key));
}

/** 寫入（取代同鍵）一筆；value 必須含該庫的 keyPath 欄位。成功寫進 IndexedDB 回傳 true，只存進記憶體備援回傳 false。 */
export function put(store, value) {
  const kp = STORE_KEYS[store];
  if (value === null || typeof value !== "object" || value[kp] === undefined) {
    return Promise.reject(new Error(`寫入 ${store} 的資料缺少 ${kp}`));
  }
  return exec(store, "readwrite", (s) => s.put(value), (m) => { m.set(value[kp], structuredClone(value)); })
    .then((key) => key !== undefined);
}

/** 讀全部（陣列）。 */
export function all(store) {
  return exec(store, "readonly", (s) => s.getAll(), (m) => [...m.values()].map((v) => structuredClone(v)));
}

/** 刪一筆。 */
export function del(store, key) {
  return exec(store, "readwrite", (s) => s.delete(key), (m) => { m.delete(key); });
}

/** 清空一個物件庫。 */
export function clear(store) {
  return exec(store, "readwrite", (s) => s.clear(), (m) => { m.clear(); });
}

/** 測試用：重設連線與備援狀態。 */
export function _reset() {
  dbPromise = null;
  usable = false;
  noticeFn = null;
  noticePending = false;
  noticed = false;
  for (const m of Object.values(fallback)) m.clear();
}
