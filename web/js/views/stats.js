// View：STAT 統計。X、Y（與選填的次數）資料表格（id="stat-table"，可新增／刪除列、從 Excel 貼上）
// ＋ 迴歸模型 ＋ 結果格 ＋ 預測箱（X'／Y'，與 Task 21 相同）。
// 單變數 1-V 送 X、F；迴歸送 X、Y、model（引擎鍵與先前的文字區塊版相同）；預測不讀表格。
import { SHEETS } from "../sheets.js";
import * as settingsStore from "../settings.js";
import { readStatTable } from "../tables.js";
import { renderForm } from "./form.js";
import { runEngineAction, watchStale, markStale } from "./run.js";
import { createGrid } from "./grid.js";

const SHEET = "stats";
const TABLE_FIELDS = new Set(["X", "F", "Y"]); // 由表格取代的欄位
const TABLE_ACTIONS = new Set(["one_var", "two_var"]);
const TABLE_KEYS = new Set(["X", "Y", "F"]); // 引擎錯誤 field 指向資料表格

export function mount(container) {
  const formBox = document.createElement("div");
  container.replaceChildren(formBox);
  let grid = null;

  const run = (actionId) => {
    if (!TABLE_ACTIONS.has(actionId)) return runEngineAction(SHEET, actionId); // 預測：只用欄位
    return runEngineAction(SHEET, actionId, {
      extra: () => {
        grid.clearError();
        const r = readStatTable(grid.getCells(), actionId, settingsStore.get().sep);
        if (r.error) return { error: { message: r.error, row: r.row, col: r.col } };
        const inputs = actionId === "one_var" ? { X: r.X, F: r.F } : { X: r.X, Y: r.Y };
        return { inputs };
      },
      onExtraError: (e) => grid.markError(e),
      mapError: (resp) => {
        if (!TABLE_KEYS.has(resp.field)) return null;
        grid.table.classList.add("has-error");
        return { ...resp, field: null }; // 表單層級訊息，不誤標到預測用的 X'／Y' 欄
      },
    });
  };

  const fields = SHEETS[SHEET].fields.filter((f) => !TABLE_FIELDS.has(f.id)).map((f) => f.id);
  const form = renderForm(SHEET, formBox, { onAction: run, fields });
  grid = createGrid({
    id: "stat-table",
    addId: "stat-add-row",
    caption: "資料（單變數只用 X，可加次數；迴歸用 X 與 Y）",
    columns: [
      { label: "X", abbr: "X", example: "1" },
      { label: "Y", abbr: "Y", example: "2.1" },
      { label: "次數", abbr: "FRQ", example: "1" },
    ],
    initialRows: 6,
    getSep: () => settingsStore.get().sep,
    onEdit: () => markStale(SHEET),
  });
  const section = document.createElement("div");
  section.className = "grid-section";
  section.append(grid.root);
  form.querySelector('.field[data-field="model"]').before(section);

  watchStale(SHEET);
  form.addEventListener("form-reset", () => grid.reset());
}
