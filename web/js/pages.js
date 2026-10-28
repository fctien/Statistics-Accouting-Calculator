// 導覽資料與路由解析（純函式、不碰 DOM，可用 node 測試）。
// 三大頁面：工程 ENG｜統計 STAT｜會計 ACCT，加上共用的「設定」。
// 網址格式：#<頁>/<項目>（例：#acct/tvm、#stat/reg），設定為 #settings。
// sheet 欄位對應 sheets.js 的工作表 id；sheet 為 null 表示畫面尚未完成（D2／D3），顯示「即將推出」。
// 舊網址（#tvm、#cf、#stat、#calc…）與舊的記憶值（工作表 id）都導向新位置。

export const PAGE_ORDER = ["eng", "stat", "acct"];

export const PAGES = {
  eng: {
    title: "工程", abbr: "ENG",
    items: [
      { route: "calc", sheet: "calc", title: "科學計算機" },
      { route: "units", sheet: "units", title: "單位換算" },
      { route: "base", sheet: "base", title: "進位轉換" },
    ],
  },
  stat: {
    title: "統計", abbr: "STAT",
    items: [
      { route: "reg", sheet: "stats", title: "迴歸與單變數" },
      { route: "desc", sheet: null, title: "敘述統計" },
      { route: "dist", sheet: null, title: "機率分配" },
      { route: "infer", sheet: null, title: "信賴區間與檢定" },
    ],
  },
  acct: {
    title: "會計", abbr: "ACCT",
    items: [
      { route: "tvm", sheet: "tvm", title: "TVM 貨幣時間價值" },
      { route: "amort", sheet: "amort", title: "AMORT 攤還" },
      { route: "cf", sheet: "cashflow", title: "CF 現金流" },
      { route: "iconv", sheet: "iconv", title: "ICONV 利率換算" },
      { route: "bond", sheet: "bond", title: "BOND 債券" },
      { route: "depr", sheet: "depr", title: "DEPR 折舊" },
      { route: "profit", sheet: "business-profit", title: "PROFIT 毛利" },
      { route: "brkevn", sheet: "business-breakeven", title: "BRKEVN 損益兩平" },
      { route: "pct", sheet: "business-pct", title: "Δ% 百分比變動" },
      { route: "tax", sheet: "tax", title: "TAX 稅額" },
      { route: "date", sheet: "date", title: "DATE 日期" },
    ],
  },
};

/** 共用的設定入口（不屬於任何一頁）。 */
export const SETTINGS_ITEM = { route: "settings", sheet: "settings", title: "設定" };

export const DEFAULT_ROUTE = "acct/tvm";

/** 舊網址（#後面的部分）→ 新路由。 */
export const LEGACY_ROUTES = {
  tvm: "acct/tvm", amort: "acct/amort", cf: "acct/cf", iconv: "acct/iconv",
  bond: "acct/bond", depr: "acct/depr", profit: "acct/profit", brkevn: "acct/brkevn",
  pct: "acct/pct", tax: "acct/tax", date: "acct/date",
  stat: "stat/reg", calc: "eng/calc", units: "eng/units", base: "eng/base", settings: "settings",
};

/** 全部項目（含頁面 id），設定的 page 為 null。 */
export function allItems() {
  const out = [];
  for (const page of PAGE_ORDER) {
    for (const it of PAGES[page].items) out.push({ ...it, page, full: `${page}/${it.route}` });
  }
  out.push({ ...SETTINGS_ITEM, page: null, full: "settings" });
  return out;
}

/** 由完整路由（例：acct/tvm、settings）找項目；找不到回傳 null。 */
export function itemByRoute(route) {
  return allItems().find((it) => it.full === route) || null;
}

/** 由工作表 id 找完整路由；沒有（或尚未有 UI）回傳 null。 */
export function routeOfSheet(sheetId) {
  const it = allItems().find((x) => x.sheet === sheetId);
  return it ? it.full : null;
}

/**
 * 解析 hash（可含 #）；不認得回傳 null。
 * 回傳 {route, redirected}：redirected＝輸入不是標準新網址（舊網址或只有頁名），應 replaceState 成 route。
 */
export function parseHash(hash) {
  let raw = String(hash ?? "").replace(/^#/, "");
  try {
    raw = decodeURIComponent(raw);
  } catch (e) {
    return null;
  }
  raw = raw.replace(/^\/+|\/+$/g, "");
  if (!raw) return null;
  if (itemByRoute(raw)) return { route: raw, redirected: false };
  if (Object.hasOwn(LEGACY_ROUTES, raw)) return { route: LEGACY_ROUTES[raw], redirected: true };
  if (PAGE_ORDER.includes(raw)) return { route: `${raw}/${PAGES[raw].items[0].route}`, redirected: true };
  return null;
}

/**
 * 決定要顯示的路由。hash 認得就用 hash；否則用記住的上次位置 last
 * （新路由、舊路由或舊的工作表 id 都可）；再不行用預設。redirected 一律 true（需改寫網址）當 hash 不是標準新網址。
 */
export function resolveHash(hash, last) {
  const h = parseHash(hash);
  if (h) return h;
  if (last) {
    const l = parseHash(last);
    if (l) return { route: l.route, redirected: true };
    const r = routeOfSheet(last);
    if (r) return { route: r, redirected: true };
  }
  return { route: DEFAULT_ROUTE, redirected: true };
}
