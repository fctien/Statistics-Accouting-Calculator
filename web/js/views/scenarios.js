// View：具名情境（scenarios）。每個有表單的工作表下方一列「儲存情境／載入情境」：
//  - 儲存：把目前表單的每個輸入欄位（原始文字、方向、引擎求出的完整精度值）以 getFieldState 存起來，
//    名稱由使用者輸入，空白時用「工作表標題＋本機時間」
//  - 載入：用 setFieldState 還原欄位，並把結果標為過期（stale），要重新按「計算」才有結果
//  - 重新命名、刪除（刪除前 confirm）
// 情境存在 IndexedDB（storage/persist.js），欄位 {id, worksheet, name, inputs, updated_at, sep}。
// sep：儲存當時的千分位設定（us／eu）。原始文字只在這個設定下有意義，載入時經
// backup.prepareScenarioForLoad 換成目前設定的寫法；無法確定的欄位標紅，絕不默默重新解讀。
// 這一列放在 #sheet 外面（由 app.js 掛載），用 MutationObserver 跟著 #sheet 內目前的表單
// （例：商業工作表切換子分頁時，worksheet 會跟著變）。
import { SHEETS } from "../sheets.js";
import { getFieldState, setFieldState } from "./form.js";
import { markStale } from "./run.js";
import * as persist from "../storage/persist.js";
import { isoTaipei, localStamp, prepareScenarioForLoad } from "../storage/backup.js";
import * as settingsStore from "../settings.js";

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

/**
 * 目前「看得到的」工作表表單的 sheetId；沒有（或是設定、計算機）回傳 null。
 * 商業頁四個子分頁的表單同時在 DOM（未選的 hidden）：只取不在 hidden 容器內的那張，
 * 否則在稅額分頁存的情境其實是隱藏的 PROFIT 表單內容（誤導）。
 */
export function currentWorksheet(root = document) {
  const forms = [...root.querySelectorAll("#sheet form.sheet-form[data-sheet]")];
  const form = forms.find((f) => !f.closest("[hidden]"));
  const id = form ? form.dataset.sheet : null;
  return id && SHEETS[id] && !NO_BAR.has(id) ? id : null;
}

/**
 * 讀出目前表單所有輸入欄位的狀態 {欄位id: getFieldState}。
 * 仍有「待確認」欄位（載入時千分位寫法無法確定）時回傳 {pending: [欄位 label]}，不可儲存。
 */
export function captureInputs(worksheet) {
  const inputs = {};
  const pending = [];
  for (const f of SHEETS[worksheet].fields) {
    if (f.output) continue;
    const st = getFieldState(worksheet, f.id);
    if (st) {
      const { stale, error, ...rest } = st; // stale 只是畫面標記，不存
      if (error) pending.push(f.label);
      inputs[f.id] = rest;
    }
  }
  if (pending.length) return { pending };
  // 表格（CF、STAT）透過 "scenario-capture" 事件把內容放進 __grid
  const detail = {};
  formOf(worksheet)?.dispatchEvent(new CustomEvent("scenario-capture", { detail }));
  if (detail.__grid) inputs.__grid = detail.__grid;
  return inputs;
}

function formOf(worksheet) {
  return document.querySelector(`#sheet form.sheet-form[data-sheet="${CSS.escape(worksheet)}"]`);
}

/**
 * 把情境還原到表單，並讓結果失效（要重新計算）。
 * 先依情境的 sep 換算成目前千分位設定的寫法；回傳 {errors: 待確認欄位數, gridError}。
 */
export function applyScenario(worksheet, scenario) {
  const prep = prepareScenarioForLoad(scenario, settingsStore.get().sep);
  for (const [id, state] of Object.entries(prep.inputs)) {
    if (id !== "__grid" && state && typeof state === "object") {
      setFieldState(worksheet, id, prep.errors[id] ? { ...state, error: prep.errors[id] } : state);
    }
  }
  // 表格：有存就還原，沒存就重設為空白（舊內容不可混進新情境）；寫法無法確定時不載入並說明
  const detail = { __grid: prep.inputs.__grid, __gridError: prep.gridError };
  formOf(worksheet)?.dispatchEvent(new CustomEvent("scenario-apply", { detail }));
  markStale(worksheet);
  // 通知專屬畫面（例：攤還表、表格）清除自己的輸出
  document.querySelector(`#sheet form.sheet-form[data-sheet="${CSS.escape(worksheet)}"]`)
    ?.dispatchEvent(new Event("change", { bubbles: true }));
  return { errors: Object.keys(prep.errors).length, gridError: prep.gridError };
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
    const inputs = captureInputs(ws);
    if (inputs.pending) {
      say(`無法儲存：${inputs.pending.join("、")} 的值待確認（紅色），請先重新輸入`);
      return;
    }
    const scenario = {
      id: newId(), worksheet: ws, name, inputs, updated_at: isoTaipei(), sep: settingsStore.get().sep,
    };
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
    const r = applyScenario(ws, s);
    const warn = [
      r.errors ? `${r.errors} 個欄位的千分位寫法無法確定（紅色），請重新輸入` : "",
      r.gridError || "",
    ].filter(Boolean).join("；");
    say(`已載入情境「${s.name}」；結果已清除，請按「計算」重新求出${warn ? "。注意：" + warn : ""}`);
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
    }).observe(sheetBox, { childList: true, subtree: true, attributes: true, attributeFilter: ["hidden"] }); // 子分頁切換只改 hidden
  }
  document.addEventListener("bacalc-data-changed", () => refresh());
  refresh();
  return { refresh };
}
