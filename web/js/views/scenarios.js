// View：具名情境（scenarios）。每個有表單的工作表下方一列「儲存情境／載入情境」：
//  - 儲存：把目前表單的每個輸入欄位（原始文字、方向、引擎求出的完整精度值）以 getFieldState 存起來，
//    名稱由使用者輸入，空白時用「工作表標題＋本機時間」
//  - 載入：用 setFieldState 還原欄位，並把結果標為過期（stale），要重新按「計算」才有結果
//  - 重新命名、刪除（刪除前 confirm）
// 情境存在 IndexedDB（storage/persist.js），欄位 {id, worksheet, name, inputs, updated_at}。
// 這一列放在 #sheet 外面（由 app.js 掛載），用 MutationObserver 跟著 #sheet 內目前的表單
// （例：商業工作表切換子分頁時，worksheet 會跟著變）。
import { SHEETS } from "../sheets.js";
import { getFieldState, setFieldState } from "./form.js";
import { markStale } from "./run.js";
import * as persist from "../storage/persist.js";
import { isoTaipei, localStamp } from "../storage/backup.js";

const NO_BAR = new Set(["calc", "settings"]);

function el(tag, attrs = {}, text = "") {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    node.setAttribute(k, v === true ? "" : String(v));
  }
  if (text) node.textContent = text;
  return node;
}

/** 產生新的情境編號。 */
export function newId() {
  const c = globalThis.crypto;
  if (c && typeof c.randomUUID === "function") return c.randomUUID();
  return `sc-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

/** 預設名稱：工作表標題＋本機時間（ISO 切片，不用地區格式化）。 */
export function defaultName(worksheet, now = Date.now()) {
  return `${SHEETS[worksheet].title} ${localStamp(now)}`;
}

/** 目前掛載中的工作表表單的 sheetId；沒有（或是設定、計算機）回傳 null。 */
export function currentWorksheet(root = document) {
  const form = root.querySelector("#sheet form.sheet-form[data-sheet]");
  const id = form ? form.dataset.sheet : null;
  return id && SHEETS[id] && !NO_BAR.has(id) ? id : null;
}

/** 讀出目前表單所有輸入欄位的狀態 {欄位id: getFieldState}。 */
export function captureInputs(worksheet) {
  const inputs = {};
  for (const f of SHEETS[worksheet].fields) {
    if (f.output) continue;
    const st = getFieldState(worksheet, f.id);
    if (st) {
      const { stale, ...rest } = st; // stale 只是畫面標記，不存
      inputs[f.id] = rest;
    }
  }
  return inputs;
}

/** 把情境還原到表單，並讓結果失效（要重新計算）。 */
export function applyScenario(worksheet, scenario) {
  for (const [id, state] of Object.entries(scenario.inputs)) {
    if (state && typeof state === "object") setFieldState(worksheet, id, state);
  }
  markStale(worksheet);
  // 通知專屬畫面（例：攤還表、表格）清除自己的輸出
  document.querySelector(`#sheet form.sheet-form[data-sheet="${CSS.escape(worksheet)}"]`)
    ?.dispatchEvent(new Event("change", { bubbles: true }));
}

/** 掛載情境列到 container。回傳 {refresh}。 */
export function mount(container) {
  const root = el("section", { class: "scenario-bar", "aria-labelledby": "sc-title" });
  root.append(el("h3", { id: "sc-title" }, "情境 Scenarios"));
  const saveRow = el("div", { class: "scenario-row" });
  const nameInput = el("input", {
    id: "sc-name", class: "control", type: "text", autocomplete: "off", maxlength: "80",
    "aria-label": "情境名稱", placeholder: "情境名稱（空白＝標題＋時間）",
  });
  const saveBtn = el("button", { type: "button", id: "sc-save", class: "btn", title: "把目前的輸入存成一個具名情境" }, "儲存情境");
  saveRow.append(nameInput, saveBtn);
  const loadRow = el("div", { class: "scenario-row" });
  const select = el("select", { id: "sc-select", class: "control", "aria-label": "已儲存的情境" });
  const loadBtn = el("button", { type: "button", id: "sc-load", class: "btn", title: "把所選情境還原到表單" }, "載入情境");
  const renameBtn = el("button", { type: "button", id: "sc-rename", class: "btn btn-ghost" }, "重新命名");
  const delBtn = el("button", { type: "button", id: "sc-delete", class: "btn btn-ghost" }, "刪除");
  loadRow.append(select, loadBtn, renameBtn, delBtn);
  const status = el("p", { id: "sc-status", class: "scenario-status", role: "status", "aria-live": "polite" });
  root.append(saveRow, loadRow, status);
  container.replaceChildren(root);

  let current = null; // 目前的 worksheet
  let list = [];
  let gen = 0;
  const say = (t) => { status.textContent = t; };

  async function refresh(selectId) {
    const my = ++gen;
    const ws = currentWorksheet();
    current = ws;
    root.hidden = ws === null;
    if (ws === null) return;
    let rows = [];
    try {
      rows = await persist.listScenarios(ws);
    } catch (e) {
      rows = [];
    }
    if (my !== gen) return;
    list = rows;
    select.replaceChildren();
    if (rows.length === 0) select.append(el("option", { value: "" }, "（尚無情境）"));
    for (const s of rows) select.append(el("option", { value: s.id }, `${s.name}　${s.updated_at.slice(0, 16).replace("T", " ")}`));
    if (selectId) select.value = selectId;
    for (const b of [loadBtn, renameBtn, delBtn]) b.disabled = rows.length === 0;
    nameInput.placeholder = `情境名稱（空白＝${defaultName(ws)}）`;
  }

  const selected = () => list.find((s) => s.id === select.value) || null;

  saveBtn.addEventListener("click", async () => {
    const ws = currentWorksheet();
    if (!ws) return;
    const name = nameInput.value.trim() || defaultName(ws);
    const scenario = { id: newId(), worksheet: ws, name, inputs: captureInputs(ws), updated_at: isoTaipei() };
    try {
      await persist.saveScenario(scenario);
    } catch (e) {
      say("儲存失敗：" + ((e && e.message) || e));
      return;
    }
    nameInput.value = "";
    say(`已儲存情境「${name}」`);
    await refresh(scenario.id);
  });

  loadBtn.addEventListener("click", () => {
    const s = selected();
    const ws = currentWorksheet();
    if (!s || !ws || s.worksheet !== ws) return;
    applyScenario(ws, s);
    say(`已載入情境「${s.name}」；結果已清除，請按「計算」重新求出`);
  });

  renameBtn.addEventListener("click", async () => {
    const s = selected();
    if (!s) return;
    const name = (globalThis.prompt("新的情境名稱", s.name) || "").trim();
    if (!name || name === s.name) return;
    try {
      await persist.saveScenario({ ...s, name, updated_at: isoTaipei() });
    } catch (e) {
      say("重新命名失敗：" + ((e && e.message) || e));
      return;
    }
    say(`已改名為「${name}」`);
    await refresh(s.id);
  });

  delBtn.addEventListener("click", async () => {
    const s = selected();
    if (!s) return;
    if (!globalThis.confirm(`要刪除情境「${s.name}」嗎？刪除後無法復原。`)) return;
    try {
      await persist.deleteScenario(s.id);
    } catch (e) {
      say("刪除失敗：" + ((e && e.message) || e));
      return;
    }
    say(`已刪除情境「${s.name}」`);
    await refresh();
  });

  // 工作表內容換了（換頁、商業工作表切子分頁）：重新列出該工作表的情境
  const sheetBox = document.getElementById("sheet");
  if (sheetBox) {
    new MutationObserver(() => {
      if (currentWorksheet() !== current) refresh();
    }).observe(sheetBox, { childList: true, subtree: true });
  }
  document.addEventListener("bacalc-data-changed", () => refresh());
  refresh();
  return { refresh };
}
