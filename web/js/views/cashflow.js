// View：CF 現金流。CF0 與各期現金流表格（id="cf-table"，每列 [金額 CFj, 次數 Fj]，可新增／刪除列、
// 從 Excel 貼上）＋ I、RI ＋ 六個指標按鈕（NPV／IRR／NFV／MIRR／PB／DPB）。
// 表格內容由 tables.js 的 readCfTable 驗證（錯誤指出第幾列第幾欄），再以 flows 送給引擎；
// 引擎警告（例：IRR 可能有多個解）顯示在結果區（樣式為醒目的警告框）。
import { SHEETS } from "../sheets.js";
import * as settingsStore from "../settings.js";
import { readCfTable } from "../tables.js";
import { renderForm } from "./form.js";
import { runEngineAction, watchStale, markStale } from "./run.js";
import { createGrid, attachScenarioHooks } from "./grid.js";

const SHEET = "cashflow";
const TABLE_FIELD = "flows"; // 由表格取代的欄位（仍以 flows 送給引擎）

export function mount(container) {
  const formBox = document.createElement("div");
  container.replaceChildren(formBox);
  let grid = null;

  const run = (actionId) => runEngineAction(SHEET, actionId, {
    extra: () => {
      grid.clearError();
      const r = readCfTable(grid.getCells(), settingsStore.get().sep);
      return r.error ? { error: { message: r.error, row: r.row, col: r.col } } : { inputs: { flows: r.flows } };
    },
    onExtraError: (e) => grid.markError(e),
    mapError: (resp) => {
      // 引擎的 field "CF" 指整串現金流（例：IRR 無解、沒有正負號變化）；CF0 自己的錯誤才標在 CF0 欄
      if (resp.field === "CF" && !/^CF0/.test(resp.error || "")) {
        grid.table.classList.add("has-error");
        return { ...resp, field: null };
      }
      return null;
    },
  });

  const fields = SHEETS[SHEET].fields.filter((f) => f.id !== TABLE_FIELD).map((f) => f.id);
  const form = renderForm(SHEET, formBox, { onAction: run, fields });
  grid = createGrid({
    id: "cf-table",
    addId: "cf-add-row",
    caption: "各期現金流（C01…Cnn 金額、F01…Fnn 次數）",
    rowPrefix: "C",
    columns: [
      { label: "金額", abbr: "CFj", example: "-1500" },
      { label: "次數", abbr: "Fj", example: "1", initial: "1" },
    ],
    initialRows: 4,
    getSep: () => settingsStore.get().sep,
    fill: { 1: "1" }, // 只貼一欄金額時，次數都是 1
    hint: "可直接從 Excel 複製貼上（兩欄＝金額與次數，一欄＝金額）；次數留空視為 1；沒有現金流的期請輸入 0；Enter 計算",
    onEdit: () => markStale(SHEET),
  });
  const section = document.createElement("div");
  section.className = "grid-section";
  section.append(grid.root);
  form.querySelector('.field[data-field="CF0"]').after(section);

  watchStale(SHEET);
  attachScenarioHooks(form, grid); // 具名情境：一併存取表格內容
  form.addEventListener("form-reset", () => grid.reset()); // 清除鈕／Esc：表格一併還原
}
