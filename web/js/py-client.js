// Controller：Python 引擎的 Promise 用戶端（client）。
// callEngine(request) 回傳 Promise<object>；Worker 尚未 ready 時請求放進佇列（queue），
// ready 後依序送出。onStatus(cb) 回報 "loading" | "ready" | "error"。
// 進入 "error" 之後的請求一律 reject，訊息說明原因。

const WORKER_URL = new URL("./py-worker.js", import.meta.url);

let status = "loading";
let detail = {}; // ready：{ms}；error：{message}
let nextId = 1;
const listeners = new Set();
const queue = []; // ready 前的請求：{id, msg, resolve, reject}
const inflight = new Map(); // 已送出、等待回覆：id -> {resolve, reject}
let worker = null;

function setStatus(s, d) {
  status = s;
  detail = d || {};
  for (const cb of listeners) {
    try { cb(status, detail); } catch (e) { console.error(e); }
  }
}

function fail(message) {
  if (status === "error") return;
  setStatus("error", { message });
  const why = new Error("Python 引擎載入失敗，無法計算：" + message);
  queue.splice(0).forEach((q) => q.reject(why));
  for (const [, p] of inflight) p.reject(why);
  inflight.clear();
  if (worker) {
    try { worker.terminate(); } catch (e) { /* 已結束 */ }
  }
}

/** 送出一筆；postMessage 失敗（例如 DataCloneError）只 reject 這一筆，不影響其他請求。 */
function dispatch(item) {
  inflight.set(item.id, item);
  try {
    worker.postMessage({ id: item.id, ...item.msg });
  } catch (e) {
    inflight.delete(item.id);
    item.reject(new Error("無法送出請求：" + ((e && e.message) || e)));
  }
}

function onMessage(ev) {
  if (status === "error") return; // error 之後的訊息（含遲到的 ready）一律忽略
  const m = ev.data || {};
  if (m.type === "ready") {
    setStatus("ready", { ms: m.ms });
    queue.splice(0).forEach(dispatch); // 依送出順序清空佇列
    return;
  }
  if (m.type === "error") {
    fail(m.message);
    return;
  }
  const p = inflight.get(m.id);
  if (!p) return;
  inflight.delete(m.id);
  if ("response" in m) p.resolve(m.response);
  else p.reject(new Error(m.error || "引擎沒有回應"));
}

function start() {
  try {
    worker = new Worker(WORKER_URL, { type: "module" });
  } catch (e) {
    fail("無法建立 Web Worker：" + ((e && e.message) || e));
    return;
  }
  worker.onmessage = onMessage;
  worker.onerror = (ev) => {
    if (ev && ev.preventDefault) ev.preventDefault();
    fail("Worker 錯誤：" + ((ev && ev.message) || "模組載入失敗"));
  };
}

function send(msg) {
  if (status === "error") {
    return Promise.reject(new Error("Python 引擎載入失敗，無法計算：" + (detail.message || "")));
  }
  return new Promise((resolve, reject) => {
    const item = { id: nextId++, msg, resolve, reject };
    if (status === "ready") dispatch(item);
    else queue.push(item);
  });
}

/** 呼叫 engine.bridge.call；request 為 {sheet, action, inputs, settings}。 */
export function callEngine(request) {
  return send({ request });
}

/** 傳原始字串給 bridge（selftest 測錯誤路徑用，例如非法 JSON）。 */
export function callEngineRaw(text) {
  return send({ raw: String(text) });
}

/** 訂閱狀態；立即以目前狀態呼叫一次。回傳取消訂閱函式。 */
export function onStatus(cb) {
  listeners.add(cb);
  try { cb(status, detail); } catch (e) { console.error(e); }
  return () => listeners.delete(cb);
}

/** 目前狀態（"loading" | "ready" | "error"）。 */
export function getStatus() {
  return status;
}

start();
