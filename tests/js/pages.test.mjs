// pages.js 路由與導覽結構測試：新舊網址對照、預設頁、未知網址、每個工作表恰好在一個頁面。
import test from "node:test";
import assert from "node:assert/strict";

import { SHEETS, SHEET_ORDER } from "../../web/js/sheets.js";
import {
  PAGES, PAGE_ORDER, LEGACY_ROUTES, DEFAULT_ROUTE, allItems, itemByRoute, routeOfSheet,
  parseHash, resolveHash,
} from "../../web/js/pages.js";

test("三大頁順序為 工程、統計、會計", () => {
  assert.deepEqual(PAGE_ORDER, ["eng", "stat", "acct"]);
  assert.deepEqual(PAGE_ORDER.map((p) => PAGES[p].title), ["工程", "統計", "會計"]);
});

test("子選單內容完整：指定的路由都存在", () => {
  const routes = (p) => PAGES[p].items.map((i) => i.route);
  assert.deepEqual(routes("eng"), ["calc", "units", "base"]);
  assert.deepEqual(routes("stat"), ["reg", "desc", "dist", "infer"]);
  assert.deepEqual(routes("acct"), [
    "tvm", "amort", "cf", "iconv", "bond", "depr", "profit", "brkevn", "pct", "tax", "date",
  ]);
});

test("每個既有工作表（含設定）都恰好出現在一個頁面", () => {
  const items = allItems();
  for (const id of SHEET_ORDER) {
    const hits = items.filter((it) => it.sheet === id);
    // 內嵌在另一畫面的工作表（例：位元運算在進位轉換畫面內）不單獨出現在導覽
    const expect = SHEETS[id].embeddedIn ? 0 : 1;
    assert.equal(hits.length, expect, `${id} 出現 ${hits.length} 次`);
    if (SHEETS[id].embeddedIn) assert.ok(items.some((it) => it.sheet === SHEETS[id].embeddedIn), id);
  }
  // 每個有畫面的項目都指向存在的工作表；完整路由唯一
  for (const it of items) if (it.sheet) assert.ok(it.sheet in SHEETS, it.full);
  assert.equal(new Set(items.map((i) => i.full)).size, items.length);
  assert.equal(itemByRoute("settings").page, null);
});

test("D3：統計頁的敘述統計、機率分配、信賴區間與檢定已有畫面；不再有 placeholder", () => {
  assert.equal(itemByRoute("stat/desc").sheet, "describe");
  assert.equal(itemByRoute("stat/dist").sheet, "dist");
  assert.equal(itemByRoute("stat/infer").sheet, "infer");
  for (const it of allItems()) assert.ok(it.sheet, `${it.full} 沒有畫面`);
});

test("新網址解析", () => {
  for (const it of allItems()) {
    assert.deepEqual(parseHash("#" + it.full), { route: it.full, redirected: false });
  }
  assert.deepEqual(parseHash("acct/tvm"), { route: "acct/tvm", redirected: false });
  assert.deepEqual(parseHash("#acct%2Ftvm"), { route: "acct/tvm", redirected: false });
});

test("舊網址對照表全覆蓋：每個工作表的舊 route 都有導向", () => {
  for (const id of SHEET_ORDER.filter((x) => !SHEETS[x].embeddedIn)) {
    const old = SHEETS[id].route;
    const hit = parseHash("#" + old);
    assert.ok(hit, `${id} 舊網址 #${old} 沒有導向`);
    assert.equal(hit.redirected, old !== "settings"); // 設定的網址沒變
    assert.equal(hit.route, routeOfSheet(id), `#${old} 應導向 ${routeOfSheet(id)}`);
    assert.equal(LEGACY_ROUTES[old], hit.route);
  }
  assert.equal(parseHash("#stat").route, "stat/reg");
  assert.equal(parseHash("#calc").route, "eng/calc");
  assert.equal(parseHash("#cf").route, "acct/cf");
  assert.equal(parseHash("#settings").redirected, false);
});

test("只有頁名（#eng、#stat、#acct）導向該頁第一項", () => {
  // 注意 #stat 是舊網址（統計工作表）而非頁名，兩者都導向 stat/reg
  assert.deepEqual(parseHash("#eng"), { route: "eng/calc", redirected: true });
  assert.deepEqual(parseHash("#stat"), { route: "stat/reg", redirected: true });
  assert.deepEqual(parseHash("#acct"), { route: "acct/tvm", redirected: true });
});

test("未知網址導向記住的位置，沒有記憶則為預設頁", () => {
  assert.equal(DEFAULT_ROUTE, "acct/tvm");
  for (const bad of ["", "#", "#nope", "#acct/nope", "#%E0%A4%A", "#constructor", "#__proto__"]) {
    assert.deepEqual(resolveHash(bad, null), { route: DEFAULT_ROUTE, redirected: true }, bad);
  }
  assert.equal(resolveHash("#nope", "stat/dist").route, "stat/dist");
});

test("記住的上次工作表：新路由、舊路由、舊工作表 id 都能還原", () => {
  assert.equal(resolveHash("", "eng/calc").route, "eng/calc");
  assert.equal(resolveHash("", "cf").route, "acct/cf");
  assert.equal(resolveHash("", "cashflow").route, "acct/cf");
  assert.equal(resolveHash("", "stats").route, "stat/reg");
  assert.equal(resolveHash("", "business-pct").route, "acct/pct");
  assert.equal(resolveHash("", "calc").route, "eng/calc");
  assert.equal(resolveHash("", "garbage").route, DEFAULT_ROUTE);
  // hash 認得時不看記憶
  assert.deepEqual(resolveHash("#acct/bond", "eng/calc"), { route: "acct/bond", redirected: false });
});

test("D2：工程頁的單位換算、進位轉換已有畫面", () => {
  assert.equal(itemByRoute("eng/units").sheet, "units");
  assert.equal(itemByRoute("eng/base").sheet, "base");
});
