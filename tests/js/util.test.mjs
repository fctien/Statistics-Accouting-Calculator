// util.js 單元測試：debounce 只執行最後一次、可取消。
import test from "node:test";
import assert from "node:assert/strict";

import { debounce } from "../../web/js/util.js";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

test("連續呼叫只執行最後一次，且用最後的參數", async () => {
  const calls = [];
  const d = debounce((x) => calls.push(x), 30);
  d(1); d(2); d(3);
  assert.deepEqual(calls, []);
  await sleep(80);
  assert.deepEqual(calls, [3]);
});

test("間隔夠久的呼叫各自執行", async () => {
  const calls = [];
  const d = debounce((x) => calls.push(x), 20);
  d("a");
  await sleep(60);
  d("b");
  await sleep(60);
  assert.deepEqual(calls, ["a", "b"]);
});

test("cancel 取消尚未執行的呼叫", async () => {
  const calls = [];
  const d = debounce((x) => calls.push(x), 20);
  d(1);
  d.cancel();
  await sleep(60);
  assert.deepEqual(calls, []);
});
