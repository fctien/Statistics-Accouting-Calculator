// Controller：App 進入點。記錄啟動計時、更新狀態膠囊、註冊 Service Worker。
// 版本號 APP_VERSION 必須與 sw.js 的 CACHE_VERSION 同步（tools/build_web.py --bump）。
import { callEngine, onStatus } from "./py-client.js";

export const APP_VERSION = "0.1.0";

const LABEL = { loading: "載入中", ready: "就緒", error: "錯誤" };

/** 取得 performance mark 的時間（毫秒，自頁面開始），沒有則 null。 */
function markTime(name) {
  const e = performance.getEntriesByName(name, "mark")[0];
  return e ? Math.round(e.startTime) : null;
}

/** 目前的啟動計時：shell（殼顯示）、pyReady（Python 就緒）、workerMs（Worker 內載入耗時）。 */
export const timings = { shell: null, pyReady: null, workerMs: null };

function renderStatus(status, detail) {
  const pill = document.getElementById("py-status");
  if (!pill) return;
  pill.className = "pill pill-" + status;
  let text = LABEL[status] || status;
  if (status === "ready" && timings.pyReady !== null) {
    text += ` ${(timings.pyReady / 1000).toFixed(1)} s`;
  }
  pill.textContent = text;
  const lines = [
    `版本 v${APP_VERSION}`,
    `殼顯示 shell：${timings.shell ?? "—"} ms`,
    `Python 就緒 py-ready：${timings.pyReady ?? "—"} ms`,
  ];
  if (timings.workerMs !== null) lines.push(`Worker 內載入：${timings.workerMs} ms`);
  if (status === "error") lines.push(`錯誤：${detail.message || ""}`);
  pill.title = lines.join("\n");
}

function onShell() {
  if (markTime("shell") === null) performance.mark("shell");
  timings.shell = markTime("shell");
  onStatus((status, detail) => {
    if (status === "ready" && markTime("py-ready") === null) {
      performance.mark("py-ready");
      timings.pyReady = markTime("py-ready");
      timings.workerMs = detail.ms ?? null;
    }
    renderStatus(status, detail);
  });
}

function registerServiceWorker() {
  if (!("serviceWorker" in navigator)) return;
  navigator.serviceWorker.register("sw.js", { scope: "./" }).catch((e) => {
    console.warn("Service Worker 註冊失敗：", e);
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", onShell, { once: true });
} else {
  onShell();
}
registerServiceWorker();

// 除錯／驗證用（瀏覽器主控台）：window.bacalc.callEngine({...})
window.bacalc = { APP_VERSION, callEngine, timings };
