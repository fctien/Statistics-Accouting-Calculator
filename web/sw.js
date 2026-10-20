// Service Worker：安裝時預先快取（precache）整個 app shell，之後 cache-first，可完全離線。
// 規則：web/ 下每個檔案都必須列在 APP_SHELL（tools/check_shell.py 檢查）；
// CACHE_VERSION 必須等於 "bacalc-v" + app.js 的 APP_VERSION（用 tools/build_web.py --bump 升版）。
// 全部是相對於 sw.js 的網址，部署在 GitHub Pages 子路徑下也正確。
const CACHE_VERSION = "bacalc-v0.1.0";

const APP_SHELL = [
  "./",
  "index.html",
  "selftest.html",
  "sw.js",
  "manifest.webmanifest",
  "css/app.css",
  "js/app.js",
  "js/py-client.js",
  "js/py-worker.js",
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

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION)
      .then((cache) => cache.addAll(APP_SHELL))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((k) => k !== CACHE_VERSION).map((k) => caches.delete(k)),
      ))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  // 只處理同源（same-origin）GET；跨源請求一律不快取、不攔截
  if (req.method !== "GET" || new URL(req.url).origin !== self.location.origin) return;
  event.respondWith(
    caches.open(CACHE_VERSION).then((cache) =>
      cache.match(req).then((hit) => hit || fetch(req))),
  );
});
