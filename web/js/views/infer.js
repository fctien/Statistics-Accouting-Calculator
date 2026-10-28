// View：信賴區間與檢定（統計頁 #stat/infer）。類型選單 → 對應輸入（摘要值欄位，或資料表格；
// 卡方獨立性為可增減列欄的 r × c 表格）→ 結果：H0／H1、統計量、df、p 值（浮動格式）、結論句、warnings。
// 表格沿用 grid.js（可從 Excel 貼上）；換類型時表格版面跟著換，各版面的內容暫存在記憶體，切回來還在。
// 具名情境：表格內容存在 __grid；載入時先依情境的「類型」換好版面再還原表格。
import { SHEETS } from "../sheets.js";
import * as settingsStore from "../settings.js";
import {
  INFER_TYPES, inferFields, prepareInfer, gridLayout, readInferGrid, hypotheses, inferRows, floatKeys,
} from "../stat.js";
import { renderForm } from "./form.js";
import { runEngineAction, watchStale, markStale, generation, isGeneration } from "./run.js";
import { createGrid } from "./grid.js";
import { el, ctrl, showOnly, onlyPrimaryButton, fetchFloat, resultList, statusBox } from "./statui.js";

const SHEET = "infer";
const GRID_KEYS = new Set(["X", "Y", "OBS", "EXP", "PROBS", "TABLE"]); // 引擎錯誤 field 指向表格
const TABLE_FIELDS = new Set(["XS", "YS", "OBS", "EXP", "PROBS", "TABLE"]); // 由表格取代的欄位
const LAYOUT_FIELDS = new Set(["TYPE", "CI_INPUT", "GOF_EXP"]);
const MAX_COLS = 10;

export function mount(container) {
  const box = document.createElement("div");
  container.replaceChildren(box);
  let seq = 0;
  let grid = null;
  let layout = null; // 目前表格版面 gridLayout(...)
  let indCols = 2; // 卡方獨立性的欄數
  const cache = new Map(); // 版面 key → 表格內容（切換類型時暫存）

  const fields = SHEETS[SHEET].fields.filter((f) => !TABLE_FIELDS.has(f.id)).map((f) => f.id);
  const form = renderForm(SHEET, box, { onAction: () => run(), fields });
  onlyPrimaryButton(form);
  const val = (id) => ctrl(form, SHEET, id).value;
  const opts = () => ({ ciInput: val("CI_INPUT"), gof: val("GOF_EXP"), h1: val("H1"), cols: indCols });

  // 表格區（放在欄位與按鈕之間）＋卡方獨立性的增減欄按鈕
  const section = el("div", { class: "grid-section", id: "infer-grid-section" });
  const gridHolder = el("div");
  const colTools = el("div", { class: "grid-actions", hidden: true });
  const addCol = el("button", { type: "button", id: "infer-add-col", class: "btn", title: "在表格右邊新增一欄" }, "新增一欄");
  const delCol = el("button", { type: "button", id: "infer-del-col", class: "btn btn-ghost", title: "刪除最右邊一欄" }, "刪除一欄");
  colTools.append(addCol, delCol);
  section.append(gridHolder, colTools);
  form.querySelector(".actions").before(section);

  function buildGrid(lay, cells) {
    grid = createGrid({
      id: "infer-table",
      addId: "infer-add-row",
      caption: lay.caption,
      columns: lay.columns,
      initialRows: lay.key === "ind" ? 2 : 6,
      getSep: () => settingsStore.get().sep,
      onEdit: () => {
        markStale(SHEET);
        seq++;
      },
    });
    if (cells && cells.length && cells.every((r) => r.length === lay.columns.length)) grid.setCells(cells);
    gridHolder.replaceChildren(grid.root);
  }

  /** 依類型與選單更新欄位顯示與表格版面；版面不同時暫存舊表格內容、換新表格。 */
  function sync(force = false) {
    const type = val("TYPE");
    showOnly(form, inferFields(type, opts()));
    const lay = gridLayout(type, opts());
    colTools.hidden = !lay || lay.key !== "ind";
    delCol.disabled = indCols <= 2;
    addCol.disabled = indCols >= MAX_COLS;
    const same = lay && layout && lay.key === layout.key && lay.columns.length === layout.columns.length;
    if (same && !force) {
      // 同一版面（例：適合度改期望形式）：只換欄名，內容保留
      grid.table.querySelectorAll("thead th").forEach((th, j) => {
        const c = lay.columns[j - 1];
        if (!c) return;
        th.firstChild.textContent = `${c.label} `;
        th.querySelector("abbr").textContent = c.abbr;
        th.querySelector("abbr").title = c.abbr;
      });
      layout = lay;
      return;
    }
    if (grid && layout) cache.set(layout.key, grid.getCells());
    layout = lay;
    if (!lay) {
      grid = null;
      gridHolder.replaceChildren();
      section.hidden = true;
      return;
    }
    section.hidden = false;
    let cells = cache.get(lay.key);
    if (lay.key === "ind" && cells) { // 欄數改了：補空白欄或截掉右邊
      cells = cells.map((r) => Array.from({ length: lay.columns.length }, (_, j) => r[j] ?? ""));
    }
    buildGrid(lay, cells);
  }

  form.addEventListener("change", (e) => {
    if (LAYOUT_FIELDS.has(e.target?.name)) sync();
  });
  const changeCols = (d) => {
    const cells = grid.getCells();
    indCols = Math.min(MAX_COLS, Math.max(2, indCols + d));
    cache.set("ind", cells);
    layout = null; // 強制重建
    sync(true);
    markStale(SHEET);
    seq++;
  };
  addCol.addEventListener("click", () => changeCols(1));
  delCol.addEventListener("click", () => changeCols(-1));

  form.addEventListener("form-reset", () => {
    cache.clear();
    indCols = 2;
    layout = null;
    sync(true);
  });
  watchStale(SHEET, () => { seq++; });

  // 具名情境：表格內容存在 __grid；載入時先依情境的類型換版面（卡方獨立性依欄數）再還原
  form.addEventListener("scenario-capture", (e) => {
    if (grid) e.detail.__grid = grid.getCells();
  });
  form.addEventListener("scenario-apply", (e) => {
    const g = e.detail.__grid;
    const valid = Array.isArray(g) && g.length >= 1 && g.length <= 500
      && g.every((r) => Array.isArray(r) && r.length === g[0].length && r.every((c) => typeof c === "string"));
    cache.clear();
    if (val("TYPE") === "chi_ind") indCols = valid ? Math.min(MAX_COLS, Math.max(2, g[0].length)) : 2;
    layout = null;
    sync(true);
    if (grid) {
      grid.clearError();
      if (valid && g[0].length === layout.columns.length) grid.setCells(g);
      else grid.reset();
      if (e.detail.__gridError) grid.markError({ message: e.detail.__gridError, row: null });
    }
  });

  sync(true);

  async function run() {
    const my = ++seq;
    const type = val("TYPE");
    const o = opts();
    const useGrid = Boolean(grid);
    const res = await runEngineAction(SHEET, type, {
      prepare: (inputs, errors) => prepareInfer(type, o, inputs, errors),
      extra: useGrid ? () => {
        grid.clearError();
        const r = readInferGrid(type, grid.getCells(), settingsStore.get().sep, o);
        return r.error ? { error: { message: r.error, row: r.row, col: r.col } } : { inputs: r.inputs };
      } : undefined,
      onExtraError: (e) => grid?.markError(e),
      mapError: (resp) => {
        if (!useGrid || !GRID_KEYS.has(resp.field)) return null;
        grid.table.classList.add("has-error");
        return { ...resp, field: null }; // 表單層級訊息（表格沒有對應的欄位）
      },
      showValues: false,
    });
    if (!res || res.response.ok !== true || my !== seq) return;
    const token = generation(SHEET);
    const values = res.response.values;
    const rows = inferRows(type, values);
    const fl = floatKeys(rows).length ? await fetchFloat("infer", type, res.inputs) : null;
    if (my !== seq || !isGeneration(SHEET, token) || !form.isConnected) return;
    const status = statusBox(form);
    status.append(el("h3", { class: "stat-head" }, INFER_TYPES[type].label));
    const hyp = hypotheses(type, o.h1);
    if (hyp) {
      const p = el("p", { class: "stat-hyp", id: "infer-hyp" });
      p.append(el("span", {}, hyp.h0), el("span", {}, hyp.h1));
      status.append(p);
    }
    status.append(resultList(rows, res.response.display, fl ? fl.display : null, "infer-result"));
    if (typeof values.conclusion === "string") {
      status.append(el("p", { class: "stat-conclusion", id: "infer-conclusion" },
        `結論：${values.conclusion}（p ${values.reject ? "≤" : ">"} α）`));
    }
    if (!INFER_TYPES[type].test) {
      const d = floatKeys(rows).includes("lower") ? (fl ? fl.display : null) : res.response.display;
      if (d) {
        status.append(el("p", { class: "stat-conclusion", id: "infer-conclusion" },
          `信賴水準 ${val("CONF").trim()} 的信賴區間：[${d.lower}, ${d.upper}]`
          + (type === "ci_prop" ? `（Wald）；Wilson：[${d.wilson_lower}, ${d.wilson_upper}]` : "")));
      }
    }
  }
}
