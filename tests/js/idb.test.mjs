// idb.js 測試：用記憶體版 fake indexedDB 驗證 get／put／all／del／clear；以及不可用時改存記憶體並只提示一次。
import test from "node:test";
import assert from "node:assert/strict";

import * as idb from "../../web/js/storage/idb.js";
import { makeFakeIndexedDB } from "./helpers/fake-idb.mjs";

test.afterEach(() => {
  delete globalThis.indexedDB;
  idb._reset();
});

test("IndexedDB 可用：五種操作與 keyPath", async () => {
  globalThis.indexedDB = makeFakeIndexedDB();
  assert.equal(await idb.get("scenarios", "x"), undefined);
  await idb.put("scenarios", { id: "x", name: "A" });
  await idb.put("scenarios", { id: "y", name: "B" });
  await idb.put("scenarios", { id: "x", name: "A2" });
  assert.equal((await idb.get("scenarios", "x")).name, "A2");
  assert.equal((await idb.all("scenarios")).length, 2);
  await idb.del("scenarios", "x");
  assert.deepEqual((await idb.all("scenarios")).map((s) => s.id), ["y"]);
  await idb.put("tape", { key: "tape", entries: [1, 2] });
  assert.deepEqual((await idb.get("tape", "tape")).entries, [1, 2]);
  await idb.clear("scenarios");
  assert.deepEqual(await idb.all("scenarios"), []);
  assert.equal(idb.isPersistent(), true);
  // 資料真的在 fake DB 內
  assert.equal(globalThis.indexedDB.dbs.get("bacalc").stores.get("tape").data.size, 1);
});

test("put 缺 keyPath 欄位或未知物件庫：拒絕", async () => {
  globalThis.indexedDB = makeFakeIndexedDB();
  await assert.rejects(idb.put("scenarios", { name: "no id" }));
  await assert.rejects(idb.get("nope", "x"));
});

test("沒有 indexedDB：改存記憶體，提示只出現一次，不丟例外", async () => {
  const msgs = [];
  idb.onUnavailable((m) => msgs.push(m));
  await idb.put("settings", { key: "settings", value: { a: 1 } });
  await idb.put("settings", { key: "settings", value: { a: 2 } });
  assert.deepEqual((await idb.get("settings", "settings")).value, { a: 2 });
  assert.equal((await idb.all("settings")).length, 1);
  await idb.del("settings", "settings");
  assert.equal(await idb.get("settings", "settings"), undefined);
  assert.equal(idb.isPersistent(), false);
  assert.deepEqual(msgs, ["此瀏覽器無法使用本機儲存，資料只保留到關閉頁面"]);
});

test("開啟失敗：先出錯、後註冊回呼也會收到一次提示", async () => {
  globalThis.indexedDB = makeFakeIndexedDB({ failOpen: true });
  await idb.put("memory", { key: "memory", data: {} });
  const msgs = [];
  idb.onUnavailable((m) => msgs.push(m));
  idb.onUnavailable((m) => msgs.push(m));
  assert.equal(msgs.length, 1);
  assert.notEqual(await idb.get("memory", "memory"), undefined);
});

test("單次寫入失敗：該筆退回記憶體並提示，不丟例外", async () => {
  const msgs = [];
  idb.onUnavailable((m) => msgs.push(m));
  globalThis.indexedDB = makeFakeIndexedDB({ failPut: true });
  await idb.put("settings", { key: "settings", value: 1 });
  assert.equal(msgs.length, 1);
  // 這筆在記憶體備援，真 DB 沒有；程式不當機即可
  assert.equal(globalThis.indexedDB.dbs.get("bacalc").stores.get("settings").data.size, 0);
});
