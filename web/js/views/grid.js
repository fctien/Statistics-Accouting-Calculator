// View 元件：可編輯數字表格（CF、STAT 共用）。
// 每格是一個文字輸入框（inputmode="decimal"），可新增／刪除列、從 Excel 貼上（paste 事件）、
// 上下方向鍵換列。內容只存在輸入框裡，讀出時交給 tables.js（純函式）解析與驗證。
// 本元件不碰引擎；有使用者編輯（新增／刪除／貼上）時呼叫 opts.onEdit()，讓專屬畫面讓舊結果失效。
// 一般輸入（打字）會以 input 事件冒泡到所屬的 <form>，由 run.js 的 watchStale 處理。
import { parsePastedTable } from "../paste.js";
import { applyPaste, MAX_ROWS } from "../tables.js";

function el(tag, attrs = {}, text = "") {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    node.setAttribute(k, v === true ? "" : String(v));
  }
  if (text) node.textContent = text;
  return node;
}

/**
 * 建立表格。opts：
 *   id、addId        表格與「新增列」按鈕的 DOM id（給 e2e）
 *   caption          表格標題
 *   rowPrefix        列標籤前綴（例："C"→C01、C02…；省略則為純數字）
 *   columns          [{label, abbr, example, initial}]，initial 是新列的預設文字
 *   initialRows      起始列數
 *   maxRows          列數上限（預設 MAX_ROWS）
 *   getSep()         目前的千分位設定（"us"／"eu"）
 *   fill             單欄貼上時，其餘欄的預設（{欄索引: 文字}）
 *   onEdit()         新增／刪除／貼上之後呼叫
 * 回傳 {root, table, getCells, setCells, reset, markError, clearError, setMessage}。
 */
export function createGrid(opts) {
  const {
    id, addId, caption, rowPrefix = "", columns, initialRows = 3, maxRows = MAX_ROWS,
    getSep = () => "us", fill = {}, onEdit, hint: hintText,
  } = opts;
  const width = columns.length;
  const root = el("div", { class: "grid-box" });
  const table = el("table", { id, class: "grid-table" });
  table.append(el("caption", {}, caption));
  const head = el("tr");
  head.append(el("th", { scope: "col" }, "期"));
  for (const c of columns) {
    const th = el("th", { scope: "col" }, `${c.label} `);
    th.append(el("abbr", { title: c.abbr }, c.abbr));
    head.append(th);
  }
  head.append(el("th", { scope: "col" }, ""));
  const thead = el("thead");
  thead.append(head);
  const tbody = el("tbody");
  table.append(thead, tbody);

  const msg = el("p", { class: "grid-msg", role: "alert", hidden: true });
  const add = el("button", { type: "button", id: addId, class: "btn", title: "在表格最後新增一列" }, "新增一列");
  const tools = el("div", { class: "grid-actions" });
  tools.append(add);
  const hint = el("p", { class: "grid-hint" },
    hintText || "可直接從 Excel 複製貼上：點選要開始的格子再貼上；Tab 換欄、上下鍵換列、Enter 計算");
  root.append(table, msg, tools, hint);

  const rowLabel = (i) => (rowPrefix ? rowPrefix + String(i + 1).padStart(2, "0") : String(i + 1));

  function buildRow(values) {
    const tr = el("tr");
    tr.append(el("th", { scope: "row", class: "grid-rowlabel" }));
    columns.forEach((c, j) => {
      const td = el("td");
      td.append(el("input", {
        type: "text", class: "grid-cell", inputmode: "decimal", autocomplete: "off", spellcheck: "false",
        placeholder: c.example ? `例：${c.example}` : null, "data-col": j,
        value: values ? values[j] : c.initial ?? "",
      }));
      tr.append(td);
    });
    const del = el("button", { type: "button", class: "row-del btn btn-ghost", title: "刪除這一列" }, "✕");
    const tdDel = el("td");
    tdDel.append(del);
    tr.append(tdDel);
    return tr;
  }

  /** 重新編號與 aria-label（新增、刪除後呼叫）。 */
  function relabel() {
    Array.from(tbody.rows).forEach((tr, i) => {
      tr.dataset.row = String(i);
      tr.querySelector(".grid-rowlabel").textContent = rowLabel(i);
      tr.querySelectorAll(".grid-cell").forEach((inp, j) => {
        inp.id = `${id}-r${i + 1}c${j + 1}`;
        inp.setAttribute("aria-label", `${columns[j].label}，第 ${i + 1} 列`);
      });
      tr.querySelector(".row-del").setAttribute("aria-label", `刪除第 ${i + 1} 列`);
    });
  }

  function getCells() {
    return Array.from(tbody.rows).map((tr) => Array.from(tr.querySelectorAll(".grid-cell")).map((i) => i.value));
  }

  function cellInput(row, col) {
    return tbody.rows[row]?.querySelectorAll(".grid-cell")[col] ?? null;
  }

  function clearError() {
    for (const inp of table.querySelectorAll(".cell-error")) {
      inp.classList.remove("cell-error");
      inp.removeAttribute("aria-invalid");
    }
    table.classList.remove("has-error");
    msg.hidden = true;
    msg.textContent = "";
  }

  function setMessage(text) {
    msg.textContent = text;
    msg.hidden = !text;
    table.classList.toggle("has-error", Boolean(text));
  }

  /** 標出出錯的格子（row、col 1 起算，null 則只顯示訊息）並顯示訊息；焦點移到該格。 */
  function markError({ message, row, col }) {
    clearError();
    setMessage(message);
    if (row) {
      const inp = cellInput(row - 1, (col || 1) - 1);
      if (inp) {
        inp.classList.add("cell-error");
        inp.setAttribute("aria-invalid", "true");
        inp.focus();
      }
    }
  }

  function setCells(cells) {
    tbody.replaceChildren(...cells.map(buildRow));
    relabel();
  }

  function reset() {
    clearError();
    setCells(Array.from({ length: initialRows }, () => columns.map((c) => c.initial ?? "")));
  }

  add.addEventListener("click", () => {
    if (tbody.rows.length >= maxRows) {
      setMessage(`最多 ${maxRows} 列，無法再新增`);
      return;
    }
    clearError();
    tbody.append(buildRow());
    relabel();
    cellInput(tbody.rows.length - 1, 0)?.focus();
    onEdit?.();
  });

  tbody.addEventListener("click", (e) => {
    const del = e.target.closest(".row-del");
    if (!del) return;
    const tr = del.closest("tr");
    const i = Array.from(tbody.rows).indexOf(tr);
    clearError();
    tr.remove();
    if (tbody.rows.length === 0) tbody.append(buildRow()); // 至少留一列
    relabel();
    cellInput(Math.min(i, tbody.rows.length - 1), 0)?.focus();
    onEdit?.();
  });

  tbody.addEventListener("input", clearError); // 重新編輯：舊的錯誤標示與訊息作廢

  tbody.addEventListener("keydown", (e) => {
    if (e.key !== "ArrowUp" && e.key !== "ArrowDown") return;
    const inp = e.target.closest(".grid-cell");
    if (!inp) return;
    const i = Array.from(tbody.rows).indexOf(inp.closest("tr"));
    const next = cellInput(i + (e.key === "ArrowDown" ? 1 : -1), Number(inp.dataset.col));
    if (next) {
      e.preventDefault();
      next.focus();
      next.select();
    }
  });

  tbody.addEventListener("paste", (e) => {
    const inp = e.target.closest?.(".grid-cell");
    if (!inp) return;
    const text = e.clipboardData ? e.clipboardData.getData("text") : "";
    // 單一值（沒有換行、tab、空白）：交給瀏覽器預設貼進這一格，格式問題計算時再指出
    if (text !== "" && !/[\t\r\n ]/.test(text.trim())) return;
    e.preventDefault();
    const sep = getSep();
    const parsed = parsePastedTable(text, sep);
    if (!parsed.rows) {
      markError({ message: "貼上失敗：" + parsed.error, row: null });
      return;
    }
    const r0 = Array.from(tbody.rows).indexOf(inp.closest("tr"));
    const c0 = Number(inp.dataset.col);
    const res = applyPaste(getCells(), r0, c0, parsed.rows, { width, sep, maxRows, fill });
    if (!res.cells) {
      markError({ message: "貼上失敗：" + res.error, row: null });
      return;
    }
    clearError();
    setCells(res.cells);
    cellInput(Math.min(r0 + parsed.rows.length - 1, tbody.rows.length - 1), c0)?.focus();
    onEdit?.();
  });

  reset();
  return { root, table, width, maxRows, getCells, setCells, reset, markError, clearError, setMessage };
}

/**
 * 讓表格參與具名情境（scenarios.js）：form 上的 "scenario-capture" 事件把表格內容放進 detail.__grid；
 * "scenario-apply" 事件有 detail.__grid（欄數相符、列數不超過上限）就還原，沒有就把表格重設為空白起始狀態
 * （detail.__gridError 有值時另顯示原因），
 * 避免新情境的 CF0／I 與舊表格內容混在一起。
 */
export function attachScenarioHooks(form, grid) {
  form.addEventListener("scenario-capture", (e) => { e.detail.__grid = grid.getCells(); });
  form.addEventListener("scenario-apply", (e) => {
    const g = e.detail.__grid;
    const ok = Array.isArray(g) && g.length >= 1 && g.length <= grid.maxRows
      && g.every((r) => Array.isArray(r) && r.length === grid.width && r.every((c) => typeof c === "string"));
    grid.clearError();
    if (ok) grid.setCells(g);
    else grid.reset();
    // 千分位寫法無法確定（scenarios.js 經 prepareScenarioForLoad）：表格不載入，說明原因
    if (e.detail.__gridError) grid.markError({ message: e.detail.__gridError, row: null });
  });
}
