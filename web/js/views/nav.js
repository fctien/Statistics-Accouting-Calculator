// View：工作表導覽（navigation）。hash 路由（#tvm、#cf、…）；
// 寬度 < 900px：底部分頁列（5 個主要工作表＋「更多」選單）；≥ 900px：左側列出全部工作表。
// 兩組選單都在 DOM 中，由 CSS 媒體查詢（media query）決定顯示哪一組。
// 記住上次的工作表（localStorage，只是單一裝置的便利功能，讀寫失敗就忽略）。
import { SHEETS, SHEET_ORDER, PRIMARY_SHEETS, sheetByRoute } from "../sheets.js";

const LAST_KEY = "bacalc.lastSheet";
const DEFAULT_SHEET = "tvm";

let current = null;
let listeners = [];
let moreBtn = null;
let morePanel = null;

function loadLast() {
  try {
    const id = globalThis.localStorage?.getItem(LAST_KEY);
    return id && id in SHEETS ? id : null;
  } catch (e) {
    return null;
  }
}

function saveLast(id) {
  try {
    globalThis.localStorage?.setItem(LAST_KEY, id);
  } catch (e) {
    /* 私密視窗：不記憶 */
  }
}

function link(id, cls) {
  const a = document.createElement("a");
  a.href = "#" + SHEETS[id].route;
  a.className = cls;
  a.dataset.sheet = id;
  return a;
}

function buildSidebar(nav) {
  const ul = document.createElement("ul");
  let group = null;
  for (const id of SHEET_ORDER) {
    const g = SHEETS[id].group || null;
    if (g && g !== group) {
      const li = document.createElement("li");
      li.className = "nav-group";
      li.setAttribute("aria-hidden", "true");
      li.textContent = g;
      ul.append(li);
    }
    group = g;
    const li = document.createElement("li");
    const a = link(id, "side-link" + (g ? " in-group" : ""));
    a.textContent = SHEETS[id].title;
    li.append(a);
    ul.append(li);
  }
  nav.replaceChildren(ul);
}

function closeMore(focusButton = false) {
  if (!morePanel || morePanel.hidden) return;
  morePanel.hidden = true;
  moreBtn.setAttribute("aria-expanded", "false");
  if (focusButton) moreBtn.focus();
}

function buildTabbar(nav) {
  const ul = document.createElement("ul");
  ul.className = "tabs";
  for (const id of PRIMARY_SHEETS) {
    const li = document.createElement("li");
    const a = link(id, "tab-link");
    a.textContent = SHEETS[id].short;
    li.append(a);
    ul.append(li);
  }
  const li = document.createElement("li");
  moreBtn = document.createElement("button");
  moreBtn.type = "button";
  moreBtn.className = "tab-link tab-more";
  moreBtn.textContent = "更多";
  moreBtn.setAttribute("aria-expanded", "false");
  moreBtn.setAttribute("aria-controls", "more-menu");
  li.append(moreBtn);
  ul.append(li);

  morePanel = document.createElement("div");
  morePanel.id = "more-menu";
  morePanel.className = "more-menu";
  morePanel.hidden = true;
  const list = document.createElement("ul");
  for (const id of SHEET_ORDER.filter((s) => !PRIMARY_SHEETS.includes(s))) {
    const item = document.createElement("li");
    const a = link(id, "more-link");
    a.textContent = SHEETS[id].title;
    item.append(a);
    list.append(item);
  }
  morePanel.append(list);
  nav.replaceChildren(morePanel, ul);

  moreBtn.addEventListener("click", () => {
    const open = morePanel.hidden;
    morePanel.hidden = !open;
    moreBtn.setAttribute("aria-expanded", String(open));
    if (open) morePanel.querySelector("a")?.focus();
  });
  morePanel.addEventListener("click", (e) => {
    if (e.target.closest("a")) closeMore();
  });
  nav.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !morePanel.hidden) {
      e.stopPropagation();
      closeMore(true);
    }
  });
  document.addEventListener("click", (e) => {
    if (!nav.contains(e.target)) closeMore();
  });
}

function markCurrent(id) {
  for (const a of document.querySelectorAll("a[data-sheet]")) {
    if (a.dataset.sheet === id) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  }
  if (moreBtn) moreBtn.classList.toggle("active", !PRIMARY_SHEETS.includes(id));
}

function resolve() {
  const route = decodeURIComponent(location.hash.replace(/^#/, ""));
  return sheetByRoute(route);
}

function onHash() {
  const id = resolve();
  if (!id) {
    // 不認得的 hash（或沒有 hash）：回到上次的工作表，用 replace 不留歷史
    go(loadLast() || DEFAULT_SHEET, true);
    return;
  }
  if (id === current) return;
  const first = current === null;
  current = id;
  saveLast(id);
  markCurrent(id);
  closeMore();
  for (const cb of listeners) cb(id, { initial: first });
}

/** 切換到工作表（改 hash）；replace=true 時不新增瀏覽紀錄。 */
export function go(sheetId, replace = false) {
  if (!(sheetId in SHEETS)) sheetId = DEFAULT_SHEET;
  const hash = "#" + SHEETS[sheetId].route;
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

/** 目前的工作表 id。 */
export function currentSheet() {
  return current;
}

/**
 * 建立導覽：sidebar（≥ 900px 顯示）與 tabbar（< 900px 顯示）為兩個 <nav> 元素。
 * onChange(sheetId, {initial}) 在工作表改變時呼叫（含第一次）。
 */
export function initNav({ sidebar, tabbar, onChange }) {
  if (sidebar) buildSidebar(sidebar);
  if (tabbar) buildTabbar(tabbar);
  if (onChange) listeners.push(onChange);
  window.addEventListener("hashchange", onHash);
  onHash();
}
