// settings.js 測試：預設值、合法性檢查、storage 不可用或丟例外時仍可運作。
import test from "node:test";
import assert from "node:assert/strict";

import { DEFAULTS, get, set, toEngine, _resetCache } from "../../web/js/settings.js";

function fakeStorage(initial = {}) {
  const m = new Map(Object.entries(initial));
  return {
    getItem: (k) => (m.has(k) ? m.get(k) : null),
    setItem: (k, v) => m.set(k, String(v)),
    map: m,
  };
}

test("沒有 localStorage：回傳預設值，set 只在記憶體生效", () => {
  delete globalThis.localStorage;
  _resetCache();
  assert.deepEqual(get(), { decimals: 2, sep: "us", mode: "AOS", theme: "auto" });
  assert.deepEqual(DEFAULTS, get());
  const r = set({ decimals: 4 });
  assert.deepEqual(r.errors, {});
  assert.equal(get().decimals, 4);
  _resetCache();
  assert.equal(get().decimals, 2);
});

test("讀寫 localStorage；不合法值忽略並回報", () => {
  const st = fakeStorage({ "bacalc.settings": JSON.stringify({ decimals: 5, sep: "xx", theme: "dark" }) });
  globalThis.localStorage = st;
  _resetCache();
  assert.deepEqual(get(), { decimals: 5, sep: "us", mode: "AOS", theme: "dark" });
  const r = set({ decimals: null, mode: "CHAIN", sep: "fr", bogus: 1 });
  assert.deepEqual(Object.keys(r.errors), ["sep"]);
  assert.deepEqual(JSON.parse(st.map.get("bacalc.settings")),
    { decimals: null, sep: "us", mode: "CHAIN", theme: "dark" });
  assert.deepEqual(toEngine(), { decimals: null, sep: "us", mode: "CHAIN" });
  delete globalThis.localStorage;
});

test("localStorage 丟例外或內容壞掉：不影響運作", () => {
  globalThis.localStorage = {
    getItem() { throw new Error("SecurityError"); },
    setItem() { throw new Error("QuotaExceeded"); },
  };
  _resetCache();
  assert.equal(get().sep, "us");
  assert.deepEqual(set({ sep: "eu" }).errors, {});
  assert.equal(get().sep, "eu");
  globalThis.localStorage = fakeStorage({ "bacalc.settings": "{not json" });
  _resetCache();
  assert.equal(get().mode, "AOS");
  delete globalThis.localStorage;
  _resetCache();
});
