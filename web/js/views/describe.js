// View：敘述統計（統計頁 #stat/desc）。資料表格 [X, 次數]（可新增／刪除列、從 Excel 貼上，沿用 grid.js），
// 送 stats/describe；結果分組顯示（集中趨勢、離散程度、四分位數、分配形狀），眾數 modes 以清單顯示，
// 算不出來的鍵（例：n < 4 的峰態）留空並列出引擎的 warnings。
import { SHEETS } from "../sheets.js";
import * as settingsStore from "../settings.js";
import { DESC_GROUPS, readDescribeTable } from "../stat.js";
import { renderForm } from "./form.js";
import { runEngineAction, watchStale, markStale } from "./run.js";
import { createGrid, attachScenarioHooks } from "./grid.js";
import { el } from "./statui.js";

const SHEET = "describe";
const TABLE_KEYS = new Set(["X", "F"]);

export function mount(container) {
  const box = document.createElement("div");
  container.replaceChildren(box);
  let grid = null;
  let modesOut = null;
  let seq = 0;

  const clearModes = () => {
    seq++; // 進行中的計算回來時不再寫入眾數
    if (modesOut) modesOut.textContent = "";
  };

  const run = async () => {
    clearModes(); // 失敗時不可留著上次的眾數
    const my = seq;
    const res = await runEngineAction(SHEET, "describe", {
      extra: () => {
        grid.clearError();
        const r = readDescribeTable(grid.getCells(), settingsStore.get().sep);
        if (r.error) return { error: { message: r.error, row: r.row, col: r.col } };
        return { inputs: { X: r.X, F: r.F } };
      },
      onExtraError: (e) => grid.markError(e),
      mapError: (resp) => {
        if (!TABLE_KEYS.has(resp.field)) return null;
        grid.table.classList.add("has-error");
        return { ...resp, field: null };
      },
    });
    if (my !== seq || !res || res.response.ok !== true) return;
    const modes = res.response.display.modes || [];
    modesOut.textContent = modes.length ? modes.join("、") : "無眾數";
  };

  const outputs = SHEETS[SHEET].fields.filter((f) => f.output).map((f) => f.id);
  const form = renderForm(SHEET, box, { onAction: run, fields: outputs });
  const fieldsBox = form.querySelector(".fields");

  grid = createGrid({
    id: "desc-table",
    addId: "desc-add-row",
    caption: "資料（每列一筆 X；次數選填，填了就每列都要填）",
    columns: [
      { label: "X", abbr: "X", example: "2" },
      { label: "次數", abbr: "FRQ", example: "1" },
    ],
    initialRows: 8,
    getSep: () => settingsStore.get().sep,
    onEdit: () => {
      markStale(SHEET);
      clearModes();
    },
  });
  const section = el("div", { class: "grid-section" });
  section.append(grid.root);
  fieldsBox.before(section);

  // 結果分組：把輸出欄位移進各組的 fieldset；眾數是清單，另用 <output> 顯示
  const groups = el("div", { class: "stat-groups" });
  for (const g of DESC_GROUPS) {
    const fs = el("fieldset", { class: "stat-group" });
    fs.append(el("legend", {}, g.title));
    const inner = el("div", { class: "fields" });
    for (const key of g.keys) {
      if (key === "modes") {
        const wrap = el("div", { class: "field output", "data-field": "modes" });
        const head = el("div", { class: "field-head" });
        head.append(el("label", { for: "desc-modes" }, "眾數 "), el("abbr", { title: "Mode" }, "Mode"));
        modesOut = el("output", { id: "desc-modes", class: "control stat-modes", "aria-live": "polite" });
        const row = el("div", { class: "field-input" });
        row.append(modesOut);
        wrap.append(head, row);
        inner.append(wrap);
        continue;
      }
      const wrap = fieldsBox.querySelector(`.field[data-field="${key}"]`);
      if (wrap) inner.append(wrap);
    }
    fs.append(inner);
    groups.append(fs);
  }
  fieldsBox.replaceWith(groups);

  watchStale(SHEET, clearModes); // 輸入改了：眾數與其他結果一起失效
  attachScenarioHooks(form, grid);
  form.addEventListener("form-reset", () => grid.reset());
}
