// Controller：Python 引擎 Web Worker（module worker）。
// 載入 MicroPython（WebAssembly）→ 依 py/manifest.json 把 .py 寫進虛擬檔案系統（VFS）
// → import engine.bridge → 回覆 {type: "ready", ms}。
// 收到 {id, request}（物件）或 {id, raw}（原始 JSON 字串，selftest 用）→ 回覆 {id, response}；
// 單一請求失敗只回 {id, error}，不讓 Worker 停擺。載入失敗回 {type: "error", message}。
// 全部使用相對於本檔的網址（import.meta.url），可部署在任何子路徑下。
// vendor/micropython.js 即套件的 micropython.mjs（改副檔名以確保伺服器回 JavaScript MIME type）
import { loadMicroPython } from "../vendor/micropython.js";

const HEAPSIZE = 16 * 1024 * 1024; // MicroPython heap（位元組），與 tools/mpy_util.mjs 相同
const PYSTACK = 2048;
const VFS_ROOT = "/bacalc"; // VFS 內放 engine/、golden/ 的目錄
const WASM_URL = new URL("../vendor/micropython.wasm", import.meta.url).href;
const PY_BASE = new URL("../py/", import.meta.url);

let bridge = null; // engine.bridge 模組（MicroPython proxy）
let loadError = null;
const early = []; // ready 前收到的訊息（py-client 已有佇列，這裡只是保險）

/** 取得文字檔；HTTP 失敗丟出含網址的錯誤。 */
async function fetchText(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`下載失敗 ${res.status}：${url}`);
  return res.text();
}

/** 在 VFS 建立 path 的所有上層目錄（已存在就略過）。 */
function mkdirs(fs, path, made) {
  const parts = path.split("/").filter(Boolean);
  let cur = "";
  for (const p of parts.slice(0, -1)) {
    cur += "/" + p;
    if (!made.has(cur)) {
      try { fs.mkdir(cur); } catch (e) { /* 已存在 */ }
      made.add(cur);
    }
  }
}

async function boot() {
  const t0 = performance.now();
  try {
    const manifestUrl = new URL("manifest.json", PY_BASE);
    const [mp, manifest] = await Promise.all([
      loadMicroPython({
        heapsize: HEAPSIZE, pystack: PYSTACK, url: WASM_URL,
        stdout: (s) => console.log("[py]", s),
        stderr: (s) => console.warn("[py]", s),
      }),
      fetchText(manifestUrl).then(JSON.parse),
    ]);
    const modules = manifest.modules || [];
    if (!modules.includes("engine/bridge.py")) {
      throw new Error("py/manifest.json 缺少 engine/bridge.py");
    }
    // 並行下載所有 .py，再依序寫入 VFS
    const texts = await Promise.all(modules.map((rel) => fetchText(new URL(rel, PY_BASE))));
    const made = new Set();
    modules.forEach((rel, i) => {
      const path = `${VFS_ROOT}/${rel}`;
      mkdirs(mp.FS, path, made);
      mp.FS.writeFile(path, texts[i]);
    });
    mp.runPython(`import sys\nsys.path.insert(0, '${VFS_ROOT}')`);
    bridge = mp.pyimport("engine.bridge");
    const ms = Math.round(performance.now() - t0);
    self.postMessage({ type: "ready", ms, modules: modules.length });
    early.splice(0).forEach(handle);
  } catch (e) {
    loadError = (e && e.message) || String(e);
    self.postMessage({ type: "error", message: loadError });
    early.splice(0).forEach(handle);
  }
}

/** 處理一筆請求；任何例外只影響這一筆。 */
function handle(msg) {
  const id = msg && msg.id;
  if (loadError) {
    self.postMessage({ id, error: "Python 引擎載入失敗：" + loadError });
    return;
  }
  try {
    const text = typeof msg.raw === "string" ? msg.raw : JSON.stringify(msg.request);
    const out = bridge.call(text);
    self.postMessage({ id, response: JSON.parse(String(out)) });
  } catch (e) {
    self.postMessage({ id, error: "引擎呼叫失敗：" + ((e && e.message) || String(e)) });
  }
}

self.onmessage = (ev) => {
  if (!bridge && !loadError) early.push(ev.data);
  else handle(ev.data);
};

boot();
