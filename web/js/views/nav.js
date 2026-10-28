// View：三大頁面導覽（工程 ENG｜統計 STAT｜會計 ACCT）＋共用的設定。
// hash 路由 #<頁>/<項目>（例：#acct/tvm），舊網址自動導向（replaceState，不留多餘歷史）。
// 三個元素（由 CSS 媒體查詢決定位置）：
//   page-tabs  三大頁分頁（tablist）：桌面在頂端、手機固定在底部
//   side-nav   該頁子選單：桌面（≥ 900px）左側
//   sub-nav    該頁子選單：手機（< 900px）橫向捲動的 chip 列
// 鍵盤：Tab 進入、方向鍵在同一組內移動焦點、Enter 開啟（手動啟用）。
// 記住上次的位置（localStorage，只是單一裝置的便利功能，讀寫失敗就忽略）。
import {
  PAGES, PAGE_ORDER, itemByRoute, routeOfSheet, resolveHash,
} from "../pages.js";

const LAST_KEY = "bacalc.lastRoute";
const OLD_LAST_KEY = "bacalc.lastSheet"; // v0.1 記的是工作表 id，仍可讀

let current = null; // 目前完整路由
let listeners = [];
let els = {};

function loadLast() {
  try {
    return globalThis.localStorage?.getItem(LAST_KEY)
      || globalThis.localStorage?.getItem(OLD_LAST_KEY) || null;
  } catch (e) {
    return null;
  }
}

function saveLast(route) {
  try {
    globalThis.localStorage?.setItem(LAST_KEY, route);
  } catch (e) {
    /* 私密視窗：不記憶 */
  }
}

function link(route, cls, text) {
  const a = document.createElement("a");
  a.href = "#" + route;
  a.className = cls;
  a.dataset.route = route;
  a.textContent = text;
  return a;
}

/** 方向鍵在 container 內符合 selector 的連結間移動焦點（←↑ 上一個、→↓ 下一個、Home／End）。 */
function arrowKeys(container, selector) {
  container.addEventListener("keydown", (e) => {
    const keys = { ArrowLeft: -1, ArrowUp: -1, ArrowRight: 1, ArrowDown: 1 };
    const items = [...container.querySelectorAll(selector)];
    const i = items.indexOf(document.activeElement);
    if (i < 0) return;
    let j = null;
    if (e.key in keys) j = (i + keys[e.key] + items.length) % items.length;
    else if (e.key === "Home") j = 0;
    else if (e.key === "End") j = items.length - 1;
    if (j === null) return;
    e.preventDefault();
    items[j].focus();
  });
}

function buildPageTabs(nav) {
  const ul = document.createElement("ul");
  ul.className = "tabs";
  ul.setAttribute("role", "tablist");
  for (const p of PAGE_ORDER) {
    const li = document.createElement("li");
    li.setAttribute("role", "presentation");
    const a = link(`${p}/${PAGES[p].items[0].route}`, "tab-link", PAGES[p].title);
    a.dataset.page = p;
    a.setAttribute("role", "tab");
    a.title = PAGES[p].abbr;
    li.append(a);
    ul.append(li);
  }
  nav.replaceChildren(ul);
  arrowKeys(nav, "a[data-page]");
}

/** 依目前頁重建子選單（桌面側欄與手機 chip 列）；設定頁沒有子選單。 */
function renderSub(page) {
  const { sidebar, subnav } = els;
  for (const nav of [sidebar, subnav]) {
    if (!nav) continue;
    if (!page) {
      nav.hidden = true;
      nav.replaceChildren();
      continue;
    }
    nav.hidden = false;
    nav.setAttribute("aria-label", `${PAGES[page].title}的功能`);
    const ul = document.createElement("ul");
    for (const it of PAGES[page].items) {
      const li = document.createElement("li");
      const cls = nav === sidebar ? "side-link" : "chip-link";
      const a = link(`${page}/${it.route}`, cls, it.title);
      if (!it.sheet) a.classList.add("soon");
      li.append(a);
      ul.append(li);
    }
    nav.replaceChildren(ul);
  }
}

function markCurrent(route) {
  const it = itemByRoute(route);
  for (const a of document.querySelectorAll("a[data-route]")) {
    if (a.dataset.route === route) {
      a.setAttribute("aria-current", "page");
      // 手機 chip 列橫向捲動：讓目前項目留在畫面內
      if (a.classList.contains("chip-link")) a.scrollIntoView({ block: "nearest", inline: "center" });
    } else a.removeAttribute("aria-current");
  }
  for (const a of document.querySelectorAll("a[data-page]")) {
    const on = a.dataset.page === it?.page;
    if (on) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
    a.setAttribute("aria-selected", String(on));
  }
}

function onHash() {
  const r = resolveHash(location.hash, loadLast());
  if (r.redirected || location.hash !== "#" + r.route) {
    history.replaceState(null, "", "#" + r.route); // 舊網址、未知網址：改寫不留歷史
  }
  show(r.route);
}

function show(route) {
  if (route === current) return;
  const it = itemByRoute(route);
  const first = current === null;
  const prevPage = current ? itemByRoute(current)?.page : undefined;
  current = route;
  saveLast(route);
  if (first || it.page !== prevPage) renderSub(it.page);
  markCurrent(route);
  for (const cb of listeners) {
    cb(it.sheet, { initial: first, route, page: it.page, title: it.title, placeholder: !it.sheet });
  }
}

/** 切換到工作表（改 hash）；replace=true 時不新增瀏覽紀錄。 */
export function go(sheetId, replace = false) {
  const route = routeOfSheet(sheetId) || resolveHash("", null).route;
  const hash = "#" + route;
  if (location.hash === hash) {
    onHash();
    return;
  }
  if (replace) {
    history.replaceState(null, "", hash);
    onHash();
  } else {
    location.hash = hash;
  }
}

/**
 * 畫面內自行切換子分頁（例：商業的四個分頁）時，讓導覽的目前項目與網址跟著變：
 * 只改 hash（replaceState，不觸發 hashchange、不重新載入畫面）。
 */
export function select(sheetId) {
  const route = routeOfSheet(sheetId);
  if (!route || route === current) return;
  current = route;
  saveLast(route);
  markCurrent(route);
  history.replaceState(null, "", "#" + route);
}

/** 目前的工作表 id（placeholder 頁為 null）。 */
export function currentSheet() {
  return current ? itemByRoute(current)?.sheet ?? null : null;
}

/**
 * 建立導覽。onChange(sheetId|null, {initial, route, page, title, placeholder}) 在畫面改變時呼叫（含第一次）；
 * sheetId 為 null＝尚未完成的畫面（顯示「即將推出」）。
 */
export function initNav({ pageTabs, sidebar, subnav, onChange }) {
  els = { sidebar, subnav };
  if (pageTabs) buildPageTabs(pageTabs);
  for (const nav of [sidebar, subnav]) if (nav) arrowKeys(nav, "a[data-route]");
  if (onChange) listeners.push(onChange);
  window.addEventListener("hashchange", onHash);
  onHash();
}
