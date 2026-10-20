// Service Worker：安裝時預先快取（precache）整個 app shell，之後 cache-first，可完全離線。
// 規則：web/ 下每個檔案都必須列在 APP_SHELL（tools/check_shell.py 檢查）；
// CACHE_VERSION 必須等於 "bacalc-v" + app.js 的 APP_VERSION（用 tools/build_web.py --bump 升版）。
// SHELL_HASH 由 tools/build_web.py 依 APP_SHELL 檔案內容計算：任何殼檔案改變 → sw.js 改變
// → 瀏覽器安裝新 SW、換新快取（不必每次手動 --bump）。
// 全部是相對於 sw.js 的網址，部署在 GitHub Pages 子路徑下也正確。
const CACHE_VERSION = "bacalc-v0.1.0";
const SHELL_HASH = "c339fb8d5586c47a";
const CACHE_NAME = `${CACHE_VERSION}-${SHELL_HASH}`;
const CACHE_PREFIX = "bacalc-"; // 同一 origin（github.io）可能有其他 App 的快取，只清自己的

const APP_SHELL = [
  "./",
  "index.html",
  "selftest.html",
  "sw.js",
  "manifest.webmanifest",
  "css/app.css",
  "js/app.js",
  "js/input.js",
  "js/sheets.js",
  "js/settings.js",
  "js/py-client.js",
  "js/py-worker.js",
  "js/csv.js",
  "js/util.js",
  "js/views/form.js",
  "js/views/nav.js",
  "js/views/run.js",
  "js/views/tvm.js",
  "js/views/amort.js",
  "js/views/iconv.js",
  "js/views/business.js",
  "js/views/date.js",
  "icons/icon-192.png",
  "icons/icon-512.png",
  "vendor/VERSION.txt",
  "vendor/micropython.js",
  "vendor/micropython.wasm",
  // @py-begin（由 tools/build_web.py 產生，勿手改）
  "py/data/error_cases.json",
  "py/data/excel.json",
  "py/engine/__init__.py",
  "py/engine/amort.py",
  "py/engine/bond.py",
  "py/engine/bridge.py",
  "py/engine/business.py",
  "py/engine/calc.py",
  "py/engine/cashflow.py",
  "py/engine/dates.py",
  "py/engine/depr.py",
  "py/engine/fmt.py",
  "py/engine/iconv.py",
  "py/engine/memory.py",
  "py/engine/money.py",
  "py/engine/result.py",
  "py/engine/solver.py",
  "py/engine/stats.py",
  "py/engine/tvm.py",
  "py/golden/__init__.py",
  "py/golden/runner.py",
  "py/manifest.json",
  // @py-end
];

// 逐檔以 cache: "reload" 繞過 HTTP 快取（GitHub Pages max-age=600）取得最新位元組；
// 全部成功才寫入快取，任何一檔失敗則整個安裝失敗並刪掉這個快取（原子性）
async function precache() {
  const cache = await caches.open(CACHE_NAME);
  try {
    const got = await Promise.all(APP_SHELL.map(async (u) => {
      const res = await fetch(new Request(u, { cache: "reload" }));
      if (!res.ok) throw new Error(`precache 失敗 ${res.status}：${u}`);
      return [u, res];
    }));
    await Promise.all(got.map(([u, res]) => cache.put(u, res)));
  } catch (e) {
    await caches.delete(CACHE_NAME);
    throw e;
  }
}

self.addEventListener("install", (event) => {
  event.waitUntil(precache().then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((k) => k.startsWith(CACHE_PREFIX) && k !== CACHE_NAME)
          .map((k) => caches.delete(k)),
      ))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  // 只處理同源（same-origin）GET；跨源請求一律不快取、不攔截
  if (req.method !== "GET" || new URL(req.url).origin !== self.location.origin) return;
  event.respondWith(caches.open(CACHE_NAME).then(async (cache) => {
    if (req.mode === "navigate") {
      // 頁面導覽：忽略查詢字串（?x=1）；網路也失敗（離線）時退回 index.html
      const hit = await cache.match(req, { ignoreSearch: true });
      if (hit) return hit;
      try {
        return await fetch(req);
      } catch (e) {
        const index = await cache.match("./index.html");
        if (index) return index;
        throw e;
      }
    }
    return (await cache.match(req)) || fetch(req);
  }));
});
