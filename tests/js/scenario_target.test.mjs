// 情境列的目標工作表：商業頁四個子分頁的表單同時在 DOM（未選的分頁 hidden），
// 情境必須存取「看得到的」那張表單，不可默默存／載到隱藏的第一張（PROFIT）。
import test from "node:test";
import assert from "node:assert/strict";

import { currentWorksheet } from "../../web/js/views/scenarios.js";

/** 假 DOM：form 有 dataset.sheet，closest("[hidden]") 依 hidden 旗標回傳。 */
function fakeRoot(forms) {
  const nodes = forms.map(([sheet, hidden]) => ({
    dataset: { sheet },
    closest: (sel) => (sel === "[hidden]" && hidden ? {} : null),
  }));
  return {
    querySelector: () => nodes[0] || null,
    querySelectorAll: () => nodes,
  };
}

test("商業頁在稅額分頁：情境目標是 tax，不是隱藏的 business-profit", () => {
  const root = fakeRoot([
    ["business-profit", true], ["business-breakeven", true], ["business-pct", true], ["tax", false],
  ]);
  assert.equal(currentWorksheet(root), "tax");
});

test("單一表單頁照舊；全部隱藏或沒有表單回傳 null；計算機、設定不顯示情境列", () => {
  assert.equal(currentWorksheet(fakeRoot([["dist", false]])), "dist");
  assert.equal(currentWorksheet(fakeRoot([["business-profit", true]])), null);
  assert.equal(currentWorksheet(fakeRoot([])), null);
  assert.equal(currentWorksheet(fakeRoot([["settings", false]])), null);
});
