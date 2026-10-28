// settings.js 測試：預設值、合法性檢查、IndexedDB 載入與寫回、localStorage 搬家、不可用時仍可運作。
import test from "node:test";
import assert from "node:assert/strict";

import { DEFAULTS, get, set, init, replace, toEngine, _resetCache } from "../../web/js/settings.js";
import * as idb from "../../web/js/storage/idb.js";
import { makeFakeIndexedDB } from "./helpers/fake-idb.mjs";

function fakeStorage(initial = {}) {
  const m = new Map(Object.entries(initial));
  return {
    getItem: (k) => (m.has(k) ? m.get(k) : null),
    removeItem: (k) => m.delete(k),
    setItem: (k, v) => m.set(k, String(v)),
    map: m,
  };
}

test("預設值：還沒 init 時 get 回預設，set 只在記憶體生效", () => {
  _resetCache();
  assert.deepEqual(get(), {
    decimals: 2, sep: "us", mode: "AOS", angle: "DEG", theme: "auto", dateFmt: "us", taxPreset: "", gdriveClientId: "", gdriveLastSync: "", gdriveLastSyncHash: "",
  });
  assert.deepEqual(DEFAULTS, get());
  const r = set({ decimals: 4 });
  assert.deepEqual(r.errors, {});
  assert.equal(get().decimals, 4);
  _resetCache();
  assert.equal(get().decimals, 2);
});

function cleanup() {
  delete globalThis.localStorage;
  delete globalThis.indexedDB;
  idb._reset();
  _resetCache();
}

test("init：讀 IndexedDB；不合法值忽略；set 寫回 IndexedDB", async () => {
  globalThis.indexedDB = makeFakeIndexedDB();
  idb._reset();
  await idb.put("settings", { key: "settings", value: { decimals: 5, sep: "xx", theme: "dark" } });
  _resetCache();
  await init();
  assert.deepEqual(get(), {
    decimals: 5, sep: "us", mode: "AOS", angle: "DEG", theme: "dark", dateFmt: "us", taxPreset: "", gdriveClientId: "", gdriveLastSync: "", gdriveLastSyncHash: "",
  });
  const r = set({ decimals: null, mode: "CHAIN", sep: "fr", bogus: 1 });
  assert.deepEqual(Object.keys(r.errors), ["sep"]);
  await new Promise((res) => setTimeout(res, 50));
  assert.deepEqual((await idb.get("settings", "settings")).value,
    { decimals: null, sep: "us", mode: "CHAIN", angle: "DEG", theme: "dark", dateFmt: "us", taxPreset: "", gdriveClientId: "", gdriveLastSync: "", gdriveLastSyncHash: "" });
  assert.deepEqual(toEngine(), { decimals: null, sep: "us", mode: "CHAIN", angle: "DEG" });
  cleanup();
});

test("init 搬家：舊 localStorage 設定寫進 IndexedDB 後移除舊鍵", async () => {
  globalThis.indexedDB = makeFakeIndexedDB();
  idb._reset();
  const st = fakeStorage({ "bacalc.settings": JSON.stringify({ decimals: 3, theme: "light", sep: "bad" }) });
  globalThis.localStorage = st;
  _resetCache();
  const s = await init();
  assert.equal(s.decimals, 3);
  assert.equal(s.theme, "light");
  assert.equal(s.sep, "us");
  assert.equal(st.map.has("bacalc.settings"), false);
  assert.equal((await idb.get("settings", "settings")).value.decimals, 3);
  // 再啟動：IndexedDB 已有紀錄，忽略 localStorage
  st.map.set("bacalc.settings", JSON.stringify({ decimals: 9 }));
  _resetCache();
  assert.equal((await init()).decimals, 3);
  cleanup();
});

test("init 搬家：IndexedDB 不可用時保留舊鍵（資料不遺失），設定仍可用", async () => {
  delete globalThis.indexedDB;
  idb._reset();
  const st = fakeStorage({ "bacalc.settings": JSON.stringify({ decimals: 3 }) });
  globalThis.localStorage = st;
  _resetCache();
  assert.equal((await init()).decimals, 3);
  assert.equal(st.map.has("bacalc.settings"), true);
  cleanup();
});

test("replace：整組取代，不合法的鍵回到預設", () => {
  _resetCache();
  set({ decimals: 7, theme: "dark" });
  const r = replace({ mode: "CHAIN", decimals: 99 });
  assert.deepEqual(r, { ...DEFAULTS, mode: "CHAIN" });
  assert.deepEqual(get(), r);
  cleanup();
});

test("日期格式與稅率預設值：合法才寫入", () => {
  delete globalThis.localStorage;
  _resetCache();
  assert.deepEqual(set({ dateFmt: "eu", taxPreset: "營業稅" }).errors, {});
  assert.equal(get().dateFmt, "eu");
  assert.equal(get().taxPreset, "營業稅");
  assert.deepEqual(Object.keys(set({ dateFmt: "jp", taxPreset: 5 }).errors).sort(), ["dateFmt", "taxPreset"]);
  assert.equal(get().dateFmt, "eu");
  assert.deepEqual(toEngine(), { decimals: 2, sep: "us", mode: "AOS", angle: "DEG" });
  _resetCache();
});

test("init：IndexedDB 內容壞掉或 localStorage 丟例外：不影響運作", async () => {
  globalThis.indexedDB = makeFakeIndexedDB();
  idb._reset();
  await idb.put("settings", { key: "settings", value: "not an object" });
  globalThis.localStorage = {
    getItem() { throw new Error("SecurityError"); },
    removeItem() { throw new Error("SecurityError"); },
  };
  _resetCache();
  assert.equal((await init()).mode, "AOS");
  assert.deepEqual(set({ sep: "eu" }).errors, {});
  assert.equal(get().sep, "eu");
  cleanup();
});

test("init 搬家：IndexedDB 寫入失敗（退回記憶體）時不移除舊鍵", async () => {
  globalThis.indexedDB = makeFakeIndexedDB({ failPut: true });
  idb._reset();
  const st = fakeStorage({ "bacalc.settings": JSON.stringify({ decimals: 3 }) });
  globalThis.localStorage = st;
  _resetCache();
  assert.equal((await init()).decimals, 3);
  assert.equal(st.map.has("bacalc.settings"), true);
  cleanup();
});

test("Google Drive 設定：Client ID 形狀驗證、lastSync 為字串", () => {
  _resetCache();
  const ok = set({ gdriveClientId: "123-abc.apps.googleusercontent.com", gdriveLastSync: "2026-10-20T01:00:00.000Z" });
  assert.deepEqual(ok.errors, {});
  const bad = set({ gdriveClientId: "not-a-client-id", gdriveLastSync: 5 });
  assert.deepEqual(Object.keys(bad.errors).sort(), ["gdriveClientId", "gdriveLastSync"]);
  assert.equal(get().gdriveClientId, "123-abc.apps.googleusercontent.com");
  _resetCache();
});

test("角度單位 angle：DEG／RAD 才合法，toEngine 送出，sanitize（匯入）丟掉不合法值", async () => {
  delete globalThis.localStorage;
  _resetCache();
  assert.deepEqual(set({ angle: "RAD" }).errors, {});
  assert.equal(toEngine().angle, "RAD");
  assert.deepEqual(Object.keys(set({ angle: "GRAD" }).errors), ["angle"]);
  assert.equal(get().angle, "RAD");
  const { sanitize } = await import("../../web/js/settings.js");
  assert.deepEqual(sanitize({ angle: "RAD", mode: "x" }), { angle: "RAD" });
  assert.deepEqual(sanitize({ angle: "deg" }), {});
  _resetCache();
});
