// View：AMORT 攤還。通用表單（P1～P2 區間的 BAL／PRN／INT）＋完整攤還表（id="amort-table"）
// ＋「匯出 CSV」（id="amort-csv"）。表格內容一律用引擎的 display 字串，尾差警告顯示在表格上方
// （表單的結果區）。改輸入（P1／P2 除外）或計算失敗時，攤還表立刻清掉，不留舊表。
import { renderForm, setFieldState } from "./form.js";
import { runEngineAction, watchStale } from "./run.js";
import { toCSV, download } from "../csv.js";

const SHEET = "amort";
const HEADERS = ["期數", "每期付款 PMT", "利息 INT", "本金 PRN", "餘額 BAL"];
const RANGE_ONLY = new Set(["P1", "P2"]); // 只影響區間結果，不影響整張表

function el(tag, attrs = {}, text = "") {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (text) node.textContent = text;
  return node;
}

function buildTable(rows) {
  const table = el("table", { id: "amort-table", class: "amort-table" });
  table.append(el("caption", {}, `完整攤還表（共 ${rows.length} 期）`));
  const head = el("tr");
  for (const h of HEADERS) head.append(el("th", { scope: "col" }, h));
  const thead = el("thead");
  thead.append(head);
  table.append(thead);
  const body = el("tbody");
  for (const r of rows) {
    const tr = el("tr");
    r.forEach((cell, i) => tr.append(i === 0 ? el("th", { scope: "row" }, cell) : el("td", {}, cell)));
    body.append(tr);
  }
  table.append(body);
  return table;
}

/** ctx.prefill：TVM「帶入攤還」帶來的欄位狀態（getFieldState 格式）。 */
export function mount(container, ctx = {}) {
  const host = el("div");
  container.replaceChildren(host);
  const formBox = el("div");
  const tableBox = el("div", { id: "amort-table-box", class: "amort-box" });
  host.append(formBox, tableBox);
  let rows = null; // 目前畫面上的表（display 字串二維陣列）

  const csv = el("button", { type: "button", id: "amort-csv", class: "btn" }, "匯出 CSV");
  csv.disabled = true;
  csv.title = "把目前的攤還表存成 CSV（可用 Excel 開啟）";
  csv.addEventListener("click", () => {
    if (rows) download("amort-schedule.csv", toCSV(rows, HEADERS, { bom: true }));
  });

  const clearTable = () => {
    rows = null;
    tableBox.replaceChildren();
    csv.disabled = true;
  };

  const run = async (actionId) => {
    if (actionId === "schedule") clearTable();
    const res = await runEngineAction(SHEET, actionId, { onFail: clearTable });
    if (!res || actionId !== "schedule" || res.response.ok !== true) return;
    const shown = res.response.display?.rows;
    if (!Array.isArray(shown) || shown.length === 0) {
      clearTable();
      return;
    }
    rows = shown;
    tableBox.replaceChildren(buildTable(shown));
    csv.disabled = false;
  };

  const form = renderForm(SHEET, formBox, { onAction: run });
  watchStale(SHEET, (e) => {
    const id = e.target.closest?.(".field")?.dataset.field;
    if (!RANGE_ONLY.has(id)) clearTable();
  });
  form.querySelector(".actions").append(csv);

  if (ctx.prefill) {
    for (const [id, state] of Object.entries(ctx.prefill)) setFieldState(SHEET, id, state);
  }
}
