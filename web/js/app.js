// Controller：App 進入點。記錄啟動計時、更新狀態膠囊、註冊 Service Worker、
// 掛上導覽與工作表表單，把使用者動作轉成引擎請求（callEngine）。
// 版本號 APP_VERSION 必須與 sw.js 的 CACHE_VERSION 同步（tools/build_web.py --bump）。
import { callEngine, onStatus } from "./py-client.js";
import { SHEETS } from "./sheets.js";
import * as settingsStore from "./settings.js";
import * as idb from "./storage/idb.js";
import * as persist from "./storage/persist.js";
import * as scenarios from "./views/scenarios.js";
import { initNav, go, select } from "./views/nav.js";
import { renderForm } from "./views/form.js";
import { runEngineAction } from "./views/run.js";
import * as tvmView from "./views/tvm.js";
import * as amortView from "./views/amort.js";
import * as iconvView from "./views/iconv.js";
import * as businessView from "./views/business.js";
import * as dateView from "./views/date.js";
import * as cashflowView from "./views/cashflow.js";
import * as statsView from "./views/stats.js";
import * as describeView from "./views/describe.js";
import * as distView from "./views/dist.js";
import * as inferView from "./views/infer.js";
import * as bondView from "./views/bond.js";
import * as deprView from "./views/depr.js";
import * as calcView from "./views/calc.js";
import * as unitsView from "./views/units.js";
import * as baseView from "./views/base.js";
import * as settingsView from "./views/settings.js";

export const APP_VERSION = "0.2.1";

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

// ---------------------------------------------------------------- 工作表
// 專屬畫面（views/*.js，各自 export mount(container, ctx)）；沒有專屬畫面的工作表用通用表單。

const VIEWS = {
  tvm: tvmView,
  amort: amortView,
  iconv: iconvView,
  "business-profit": businessView,
  "business-breakeven": businessView,
  "business-pct": businessView,
  tax: businessView,
  date: dateView,
  cashflow: cashflowView,
  stats: statsView,
  describe: describeView,
  dist: distView,
  infer: inferView,
  bond: bondView,
  depr: deprView,
  calc: calcView,
  units: unitsView,
  base: baseView,
  settings: settingsView,
};

let pendingPrefill = null; // 跨工作表帶值（TVM → AMORT）：下一次掛載的畫面取用一次

/** 執行通用工作表動作（交給 views/run.js；設定頁與計算機有自己的畫面，不走這裡）。 */
async function runAction(sheetId, actionId) {
  await runEngineAction(sheetId, actionId);
}

function setHeading(sheetId) {
  const sheet = SHEETS[sheetId];
  document.getElementById("sheet-title").textContent = sheet.title;
  document.getElementById("sheet-intro").textContent = sheet.intro || "";
  document.title = `${sheet.title}｜BACalc 財務計算機`;
}

/** 尚未完成的畫面（D2／D3）：只顯示「即將推出」，不呼叫任何引擎路由。 */
function mountPlaceholder(container, info) {
  document.getElementById("sheet-title").textContent = info.title;
  document.getElementById("sheet-intro").textContent = "";
  document.title = `${info.title}｜BACalc 財務計算機`;
  const box = document.createElement("div");
  box.className = "coming-soon";
  box.setAttribute("role", "status");
  const h = document.createElement("p");
  h.className = "coming-soon-title";
  h.textContent = "即將推出";
  const t = document.createElement("p");
  t.textContent = `「${info.title}」還在製作中，完成後會出現在這裡。`;
  box.append(h, t);
  container.replaceChildren(box);
}

function mountSheet(sheetId, info) {
  const { initial } = info;
  const title = document.getElementById("sheet-title");
  const container = document.getElementById("sheet");
  if (!sheetId) {
    mountPlaceholder(container, info);
    if (!initial) title.focus();
    return;
  }
  setHeading(sheetId);
  const view = VIEWS[sheetId];
  if (view) {
    const prefill = pendingPrefill;
    pendingPrefill = null;
    view.mount(container, {
      sheetId,
      prefill,
      openSheet: (id, values) => {
        pendingPrefill = values || null;
        go(id);
      },
      about: { appVersion: APP_VERSION, timings }, // 設定頁的「關於」區
      onSelect: (id) => { // 畫面內切換子分頁：同步標題與網址
        select(id);
        setHeading(id);
      },
    });
  } else {
    renderForm(sheetId, container, {
      onAction: (actionId) => runAction(sheetId, actionId),
    });
  }
  if (!initial) title.focus(); // 換頁後把焦點移到標題，螢幕閱讀器會念出新工作表
}

/** 頁首的小數位數選單：與設定頁同一個設定，改了立即重新顯示目前的結果。 */
function initQuickDecimals() {
  const sel = document.getElementById("quick-decimals");
  if (!sel) return;
  for (let i = 0; i <= 9; i++) sel.append(new Option(String(i), String(i)));
  sel.append(new Option("浮動", ""));
  const sync = () => {
    const d = settingsStore.get().decimals;
    sel.value = d === null ? "" : String(d);
  };
  sync();
  sel.addEventListener("change", () => {
    settingsStore.commit({ decimals: sel.value === "" ? null : Number(sel.value) });
  });
  document.addEventListener("bacalc-settings", sync);
}

function onAppShell() {
  settingsStore.applyTheme();
  initQuickDecimals();
  initNav({
    pageTabs: document.getElementById("page-tabs"),
    sidebar: document.getElementById("side-nav"),
    subnav: document.getElementById("sub-nav"),
    onChange: mountSheet,
  });
}

function registerServiceWorker() {
  if (!("serviceWorker" in navigator)) return;
  navigator.serviceWorker.register("sw.js", { scope: "./" }).catch((e) => {
    console.warn("Service Worker 註冊失敗：", e);
  });
}

/** 本機儲存不可用的提示（idb.js 只會呼叫一次）：頁首下方一條可關閉的訊息。 */
function showStorageNotice(text) {
  if (document.getElementById("storage-notice")) return;
  const bar = document.createElement("div");
  bar.id = "storage-notice";
  bar.className = "storage-notice";
  bar.setAttribute("role", "status");
  bar.append(text + " ");
  const close = document.createElement("button");
  close.type = "button";
  close.className = "btn btn-ghost";
  close.textContent = "知道了";
  close.addEventListener("click", () => bar.remove());
  bar.append(close);
  const header = document.querySelector(".app-header");
  if (header) header.after(bar);
  else document.body.prepend(bar);
}

/** 啟動時從 IndexedDB 還原設定、紙帶、記憶（畫面掛載前）；任何失敗都不擋啟動。 */
async function hydrate() {
  idb.onUnavailable(showStorageNotice);
  try {
    await settingsStore.init();
    const st = await persist.loadState();
    calcView.replaceState(st.tape, st.memory);
  } catch (e) {
    console.warn("還原本機資料失敗：", e);
  }
}

async function start() {
  onShell();
  await hydrate();
  onAppShell();
  const bar = document.getElementById("scenario-bar");
  if (bar) scenarios.mount(bar);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", start, { once: true });
} else {
  start();
}
registerServiceWorker();

// 除錯／驗證用（瀏覽器主控台）：window.bacalc.callEngine({...})
window.bacalc = { APP_VERSION, callEngine, timings, settings: settingsStore };
