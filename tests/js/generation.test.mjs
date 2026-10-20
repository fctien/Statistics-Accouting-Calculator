// generation.js 單元測試：世代守衛。
import test from "node:test";
import assert from "node:assert/strict";

import { createGuard } from "../../web/js/generation.js";

test("未見過的 id 世代為 0，bump 後遞增且各 id 獨立", () => {
  const g = createGuard();
  assert.equal(g.get("a"), 0);
  assert.equal(g.bump("a"), 1);
  assert.equal(g.bump("a"), 2);
  assert.equal(g.get("b"), 0);
});

test("請求期間 bump 後，先前取得的 token 不再有效", () => {
  const g = createGuard();
  const token = g.get("amort");
  assert.ok(g.isCurrent("amort", token));
  g.bump("amort"); // 使用者在請求進行中改了輸入
  assert.ok(!g.isCurrent("amort", token));
  assert.ok(g.isCurrent("amort", g.get("amort")));
});

test("bump 一張表不影響另一張表的 token", () => {
  const g = createGuard();
  const t = g.get("tvm");
  g.bump("amort");
  assert.ok(g.isCurrent("tvm", t));
});
