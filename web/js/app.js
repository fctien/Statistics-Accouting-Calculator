// Controller：App 進入點。記錄啟動計時、更新狀態膠囊、註冊 Service Worker、
// 掛上導覽與工作表表單，把使用者動作轉成引擎請求（callEngine）。
// 版本號 APP_VERSION 必須與 sw.js 的 CACHE_VERSION 同步（tools/build_web.py --bump）。
import { callEngine, onStatus } from "./py-client.js";
import { SHEETS } from "./sheets.js";
import * as settingsStore from "./settings.js";
import { initNav } from "./views/nav.js";
import {
  renderForm, readInputs, showErrors, showResult, setBusy, setValues, showInfo,
} from "./views/form.js";

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

// ---------------------------------------------------------------- 工作表（Task 21 通用表單）
// Task 22～24 會為各工作表加專屬版面；目前每張工作表都用通用表單，動作直接送引擎。

/** 執行工作表動作：讀輸入 → 格式錯誤就標紅 → 呼叫引擎 → 顯示結果。 */
async function runAction(sheetId, actionId) {
  const sheet = SHEETS[sheetId];
  const { inputs, errors } = readInputs(sheetId, actionId);
  if (showErrors(sheetId, errors)) return;
  if (sheet.engine === null) { // 設定頁：不經引擎
    const { errors: bad } = settingsStore.set(inputs);
    settingsStore.applyTheme();
    if (!showErrors(sheetId, bad)) showInfo(sheetId, "已套用設定（只存在這台裝置）");
    return;
  }
  setBusy(sheetId, true);
  try {
    const response = await callEngine({
      sheet: sheet.engine, action: actionId, inputs, settings: settingsStore.toEngine(),
    });
    showResult(response, sheetId, actionId);
  } catch (e) {
    showResult({ ok: false, error: (e && e.message) || String(e), field: null }, sheetId, actionId);
  } finally {
    setBusy(sheetId, false);
  }
}

function mountSheet(sheetId, { initial }) {
  const sheet = SHEETS[sheetId];
  const title = document.getElementById("sheet-title");
  title.textContent = sheet.title;
  document.getElementById("sheet-intro").textContent = sheet.intro || "";
  document.title = `${sheet.title}｜BACalc 財務計算機`;
  renderForm(sheetId, document.getElementById("sheet"), {
    onAction: (actionId) => runAction(sheetId, actionId),
  });
  if (sheet.engine === null) setValues(sheetId, settingsStore.get());
  if (!initial) title.focus(); // 換頁後把焦點移到標題，螢幕閱讀器會念出新工作表
}

function onAppShell() {
  settingsStore.applyTheme();
  initNav({
    sidebar: document.getElementById("side-nav"),
    tabbar: document.getElementById("tab-bar"),
    onChange: mountSheet,
  });
}

function registerServiceWorker() {
  if (!("serviceWorker" in navigator)) return;
  navigator.serviceWorker.register("sw.js", { scope: "./" }).catch((e) => {
    console.warn("Service Worker 註冊失敗：", e);
  });
}

function start() {
  onShell();
  onAppShell();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", start, { once: true });
} else {
  start();
}
registerServiceWorker();

// 除錯／驗證用（瀏覽器主控台）：window.bacalc.callEngine({...})
window.bacalc = { APP_VERSION, callEngine, timings, settings: settingsStore };
