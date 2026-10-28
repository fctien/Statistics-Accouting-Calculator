// View：DEPR 折舊。通用表單（method、CST、SAL、LIF、M01、DB%、YR → DEP／RBV／RDV）
// ＋ 完整折舊表（id="depr-table"）＋「匯出 CSV」（id="depr-csv"，規則同 AMORT：引擎以 sep "us" 捨入的純數字）。
// 折舊方法為 SYD、DB、DBX 時，M01 回到預設 1 並提示「只支援 M01=1」（引擎規則）。
// 改任何輸入（YR 除外）或計算失敗，折舊表立刻清掉，不留舊表。
import { renderForm, showResult } from "./form.js";
import { runEngineAction, watchStale, generation, isGeneration } from "./run.js";
import { callEngine } from "../py-client.js";
import * as settingsStore from "../settings.js";
import { toCSV, download, exportSettings, plainNumberRows } from "../csv.js";
import { layoutSyncNeeded } from "../stat.js";

const SHEET = "depr";
const HEADERS = ["年度", "折舊 DEP", "剩餘帳面價值 RBV", "剩餘可折舊價值 RDV"];
const RANGE_ONLY = new Set(["YR"]); // 只影響單年結果，不影響整張表
const M01_ONLY_ONE = new Set(["SYD", "DB", "DBX"]);
const M01_HINT_ONE = "SYD、DB、DBX 目前只支援 M01=1（部分年度需 TI 手冊範例驗證，引擎不算其他月份）";
const M01_HINT_SL = "直線法 SL 可輸入 M01（1～12）：第一年與最後一年依月份比例折舊";

function el(tag, attrs = {}, text = "") {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (text) node.textContent = text;
  return node;
}

function buildTable(rows) {
  const table = el("table", { id: "depr-table", class: "amort-table" });
  table.append(el("caption", {}, `完整折舊表（共 ${rows.length} 年）`));
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

export function mount(container) {
  const host = el("div");
  container.replaceChildren(host);
  const formBox = el("div");
  const tableBox = el("div", { id: "depr-table-box", class: "amort-box" });
  host.append(formBox, tableBox);
  let csvRows = null;

  const csv = el("button", { type: "button", id: "depr-csv", class: "btn" }, "匯出 CSV");
  csv.disabled = true;
  csv.title = "把目前的折舊表存成 CSV（可用 Excel 開啟）";
  csv.addEventListener("click", () => {
    if (csvRows) download("depr-schedule.csv", toCSV(csvRows, HEADERS, { bom: true }));
  });

  const clearTable = () => {
    csvRows = null;
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
      showResult({ ok: false, error: "引擎沒有回傳折舊表（沒有資料列），請檢查輸入", field: null }, SHEET, actionId);
      return;
    }
    const token = generation(SHEET);
    tableBox.replaceChildren(buildTable(shown));
    try {
      const again = await callEngine({
        sheet: SHEET, action: "schedule", inputs: res.inputs, settings: exportSettings(settingsStore.toEngine()),
      });
      const plain = again.ok === true ? again.display?.rows : null;
      if (!isGeneration(SHEET, token)) { clearTable(); return; }
      if (!Array.isArray(plain) || plain.length !== shown.length) throw new Error("匯出資料取得失敗");
      csvRows = plainNumberRows(plain);
      csv.disabled = false;
    } catch (e) {
      if (isGeneration(SHEET, token)) {
        csv.disabled = true;
        showResult({ ok: false, error: "無法產生 CSV 匯出資料：" + (e.message || e), field: null }, SHEET, actionId);
      }
    }
  };

  const form = renderForm(SHEET, formBox, { onAction: run });
  watchStale(SHEET, (e) => {
    const id = e.target.closest?.(".field")?.dataset.field;
    if (!RANGE_ONLY.has(id)) clearTable();
  });
  form.querySelector(".actions").append(csv);

  // M01 提示與預設：SYD／DB／DBX 時 M01 一律回到 1 並顯示規則
  const method = form.querySelector("#f-depr-method");
  const m01 = form.querySelector("#f-depr-M01");
  const hint = el("p", { id: "depr-m01-hint", class: "field-hint" });
  form.querySelector('.field[data-field="M01"]').append(hint);
  const syncM01 = (changed) => {
    const only = M01_ONLY_ONE.has(method.value);
    hint.textContent = only ? M01_HINT_ONE : M01_HINT_SL;
    hint.classList.toggle("hint-rule", only);
    if (changed && only && m01.value.trim() !== "1") {
      m01.value = "1";
      hint.textContent = M01_HINT_ONE + "；已將 M01 改回 1";
    }
  };
  method.addEventListener("change", () => syncM01(true));
  // 清除、情境載入（scenario-apply 與表單層級 change）：提示跟著載入的方法，不改值
  for (const type of ["change", "form-reset", "scenario-apply"]) {
    form.addEventListener(type, (e) => {
      if (e.target !== method && layoutSyncNeeded(type, e.target, form, [])) syncM01(false);
    });
  }
  syncM01(false);
}
