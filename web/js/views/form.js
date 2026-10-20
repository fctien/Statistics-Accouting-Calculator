// View：通用工作表表單（generic worksheet form）。依 sheets.js 的欄位定義產生有標籤的輸入框，
// 讀取輸入（readInputs，內部用 input.js 的 collect）、顯示引擎結果（showResult）。
// 只負責畫面；何時呼叫引擎由 Controller（app.js）決定，經 opts.onAction(actionId) 通知。
// 鍵盤：Enter＝主要動作（計算）、Esc＝清除表單、Tab 依畫面順序換欄；
// 多行清單（textarea）內 Enter 換行，Ctrl／⌘+Enter 計算；中文輸入法組字中的 Enter 不觸發。
import { SHEETS, fieldMap, fieldForKey, sendFields, primaryAction } from "../sheets.js";
import { collect, parseNumber, resolveBlanks, toSigned } from "../input.js";
import * as settings from "../settings.js";

const DIR_TEXT = { in: "收到 ↓", out: "付出 ↑" };
const RESOLVE_HINT = "綠色欄位是上次求出的結果；修改其他欄位後按 計算 會重新求出它";
const forms = new Map(); // sheetId -> {form, opts, lastAction}

const domId = (prefix, sheetId, fieldId) => `${prefix}-${sheetId}-${fieldId}`;

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (k === "dataset") Object.assign(node.dataset, v);
    else node.setAttribute(k, v === true ? "" : String(v));
  }
  for (const c of children) if (c) node.append(c);
  return node;
}

function getForm(sheetId) {
  const entry = forms.get(sheetId);
  if (!entry || !entry.form.isConnected) return null;
  return entry.form;
}

function fieldWrap(form, fieldId) {
  return form.querySelector(`.field[data-field="${CSS.escape(fieldId)}"]`);
}

function control(form, sheetId, fieldId) {
  return form.querySelector("#" + CSS.escape(domId("f", sheetId, fieldId)));
}

/** aria-describedby：單位＋（展開時）說明＋（有錯時）錯誤訊息。 */
function updateDescribedBy(wrap) {
  const input = wrap.querySelector(".control");
  const ids = [];
  const unit = wrap.querySelector(".unit");
  const help = wrap.querySelector(".help");
  const errEl = wrap.querySelector(".field-error");
  if (errEl && !errEl.hidden) ids.push(errEl.id);
  if (unit) ids.push(unit.id);
  if (help && !help.hidden) ids.push(help.id);
  if (ids.length) input.setAttribute("aria-describedby", ids.join(" "));
  else input.removeAttribute("aria-describedby");
}

function setDirection(wrap, dir) {
  const btn = wrap.querySelector(".dir");
  if (!btn) return;
  btn.dataset.direction = dir;
  btn.textContent = DIR_TEXT[dir];
  btn.classList.toggle("dir-out", dir === "out");
  const label = wrap.dataset.label;
  btn.setAttribute("aria-label",
    `${label}方向：${dir === "in" ? "收到" : "付出"}（按一下改為${dir === "in" ? "付出" : "收到"}）`);
  updateTiSign(wrap);
}

/** 顯示 TI 計算機的正負號慣例（收到為正、付出為負），讓學生對照實體計算機。 */
function updateTiSign(wrap) {
  const out = wrap.querySelector(".ti-sign");
  if (!out) return;
  const input = wrap.querySelector(".control");
  const v = parseNumber(input.value, settings.get().sep);
  if (v === null) {
    out.textContent = "";
    return;
  }
  const dir = wrap.querySelector(".dir").dataset.direction;
  const signed = toSigned(v, dir);
  out.textContent = `TI 正負號：${signed < 0 ? "−" : "+"}${input.value.trim().replace(/^[+-]/, "")}`;
}

/** 忘掉「引擎求出」狀態（solved／exact／shown）。 */
function forgetSolved(ctrl) {
  delete ctrl.dataset.solved;
  delete ctrl.dataset.exact;
  delete ctrl.dataset.shown;
}

/** 欄位值是上次引擎求出、且使用者沒有改動。 */
function isEngineValue(ctrl) {
  return ctrl.dataset.solved === "1" && ctrl.value === ctrl.dataset.shown;
}

/** 使用者改了欄位：移除「已求出」標記、精確值與錯誤。 */
function onEdited(wrap) {
  wrap.classList.remove("solved");
  forgetSolved(wrap.querySelector(".control"));
  updateResolveHint(wrap.closest("form"));
  clearFieldError(wrap);
  updateTiSign(wrap);
}

function clearFieldError(wrap) {
  wrap.classList.remove("error");
  const input = wrap.querySelector(".control");
  input.removeAttribute("aria-invalid");
  const errEl = wrap.querySelector(".field-error");
  if (errEl) {
    errEl.hidden = true;
    errEl.textContent = "";
  }
  updateDescribedBy(wrap);
}

function setFieldError(wrap, message) {
  wrap.classList.add("error");
  const input = wrap.querySelector(".control");
  input.setAttribute("aria-invalid", "true");
  const errEl = wrap.querySelector(".field-error");
  errEl.textContent = message;
  errEl.hidden = false;
  updateDescribedBy(wrap);
}

function buildControl(sheetId, f) {
  const id = domId("f", sheetId, f.id);
  const common = { id, name: f.id, class: "control", dataset: { field: f.id } };
  if (f.output) {
    return el("input", { ...common, type: "text", readonly: true, placeholder: `例：${f.example}` });
  }
  switch (f.kind) {
    case "select": {
      const sel = el("select", common);
      for (const o of f.options) {
        sel.append(el("option", { value: o.value === null ? "" : String(o.value), text: o.label }));
      }
      return sel;
    }
    case "bool":
      return el("input", { ...common, type: "checkbox" });
    case "date":
      return el("input", { ...common, type: "date", placeholder: `例：${f.example}` });
    case "list":
      return el("textarea", {
        ...common, rows: 3, spellcheck: "false", autocomplete: "off", placeholder: `例：${f.example}`,
      });
    case "text":
      return el("input", {
        ...common, type: "text", autocomplete: "off", spellcheck: "false", placeholder: `例：${f.example}`,
      });
    default: // number／percent／direction
      return el("input", {
        ...common, type: "text", inputmode: "decimal", autocomplete: "off", spellcheck: "false",
        placeholder: `例：${f.example}`,
      });
  }
}

function buildField(sheetId, f) {
  const inputId = domId("f", sheetId, f.id);
  const helpId = domId("h", sheetId, f.id);
  const wrap = el("div", {
    class: `field kind-${f.kind}${f.output ? " output" : ""}`,
    dataset: { field: f.id, kind: f.kind, label: f.label },
  });
  const label = el("label", { for: inputId }, `${f.label} `, el("abbr", { text: f.abbr, title: f.abbr }));
  const helpBtn = el("button", {
    type: "button", class: "help-btn", "aria-expanded": "false", "aria-controls": helpId,
    "aria-label": `${f.label} ${f.abbr} 說明`, title: "說明", text: "ⓘ",
  });
  const head = el("div", { class: "field-head" }, label, helpBtn);
  const help = el("p", { id: helpId, class: "help", hidden: true, text: f.help });
  const ctrl = buildControl(sheetId, f);
  const row = el("div", { class: "field-input" }, ctrl);
  if (f.unit) row.append(el("span", { class: "unit", id: domId("u", sheetId, f.id), text: f.unit }));
  if (f.kind === "direction" && !f.output) {
    row.append(el("button", { type: "button", class: "dir", dataset: { direction: "in" } }));
  }
  wrap.append(head, help, row);
  if (f.kind === "direction" && !f.output) wrap.append(el("p", { class: "ti-sign", "aria-hidden": "true" }));
  wrap.append(el("p", { class: "field-error", id: domId("e", sheetId, f.id), hidden: true }));
  if (f.kind === "direction" && !f.output) setDirection(wrap, f.initialDirection || "in");

  helpBtn.addEventListener("click", () => {
    const open = help.hidden;
    help.hidden = !open;
    helpBtn.setAttribute("aria-expanded", String(open));
    updateDescribedBy(wrap);
  });
  const dirBtn = wrap.querySelector(".dir");
  if (dirBtn) {
    dirBtn.addEventListener("click", () => {
      setDirection(wrap, dirBtn.dataset.direction === "in" ? "out" : "in");
      wrap.classList.remove("solved");
      forgetSolved(wrap.querySelector(".control")); // 改方向＝使用者自己的值
      updateResolveHint(wrap.closest("form"));
      clearFieldError(wrap);
    });
  }
  if (!f.output) {
    ctrl.addEventListener(f.kind === "select" || f.kind === "bool" ? "change" : "input", () => onEdited(wrap));
  }
  if (f.kind === "direction" && !f.output) {
    // 打入正負號：轉成方向鈕，輸入框保持絕對值（與 TI 正負號慣例一致）
    ctrl.addEventListener("change", () => {
      const m = /^\s*([+\-－])\s*/.exec(ctrl.value);
      if (!m) return;
      ctrl.value = ctrl.value.slice(m[0].length);
      setDirection(wrap, m[1] === "+" ? "in" : "out");
    });
  }
  updateDescribedBy(wrap);
  return wrap;
}

/**
 * 產生工作表表單並放進 container（會清空 container）。
 * opts.onAction(actionId)：按下動作按鈕或 Enter（主要動作）時呼叫。
 * opts.fields：只顯示這些欄位 id（Task 22～24 的版面可分區呼叫）；預設全部。
 * 回傳 <form> 元素。
 */
export function renderForm(sheetId, container, opts = {}) {
  const sheet = SHEETS[sheetId];
  if (!sheet) throw new Error("未知的工作表：" + sheetId);
  const only = opts.fields ? new Set(opts.fields) : null;
  const form = el("form", {
    class: "sheet-form", novalidate: true, dataset: { sheet: sheetId },
    "aria-label": sheet.title,
  });
  const grid = el("div", { class: "fields" });
  for (const f of sheet.fields) {
    if (!only || only.has(f.id)) grid.append(buildField(sheetId, f));
  }
  const msg = el("div", { class: "form-message", role: "alert", hidden: true });
  const status = el("div", { class: "form-status", role: "status", "aria-live": "polite" });
  const actions = el("div", { class: "actions" });
  for (const a of sheet.actions) {
    const b = el("button", {
      type: a.primary ? "submit" : "button",
      class: a.primary ? "btn btn-primary" : "btn",
      dataset: { action: a.id },
      text: a.label,
      title: a.primary ? `${a.label}（Enter）` : a.label,
    });
    if (!a.primary) b.addEventListener("click", () => opts.onAction?.(a.id));
    actions.append(b);
  }
  const clear = el("button", { type: "button", class: "btn btn-ghost", title: "清除（Esc）", text: "清除" });
  clear.addEventListener("click", () => clearForm(sheetId));
  actions.append(clear);
  form.append(grid, actions, msg, status);

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    opts.onAction?.(primaryAction(sheetId).id);
  });
  form.addEventListener("keydown", (e) => {
    if (e.isComposing || e.keyCode === 229) return; // 中文輸入法組字中
    const t = e.target;
    if (e.key === "Escape") {
      e.preventDefault();
      clearForm(sheetId);
    } else if (e.key === "Enter") {
      if (t.tagName === "TEXTAREA" && !(e.ctrlKey || e.metaKey)) return; // 清單內換行
      if (t.tagName === "BUTTON" || t.tagName === "A") return; // 按鈕自己的動作
      e.preventDefault();
      form.requestSubmit();
    }
  });

  container.replaceChildren(form);
  forms.set(sheetId, { form, opts });
  resetValues(form, sheetId);
  return form;
}

/** 把欄位設回初始值（initial／initialDirection），清掉結果與錯誤。 */
function resetValues(form, sheetId) {
  for (const f of SHEETS[sheetId].fields) {
    const wrap = fieldWrap(form, f.id);
    if (!wrap) continue;
    const ctrl = control(form, sheetId, f.id);
    if (f.kind === "bool" && !f.output) ctrl.checked = f.initial === "是";
    else if (f.kind === "select" && !f.output) {
      ctrl.value = f.initial ?? (f.options[0].value === null ? "" : String(f.options[0].value));
    } else ctrl.value = f.initial ?? "";
    wrap.classList.remove("solved");
    forgetSolved(ctrl);
    if (f.kind === "direction" && !f.output) setDirection(wrap, f.initialDirection || "in");
    clearFieldError(wrap);
  }
  clearMessages(form);
}

function clearMessages(form) {
  form.querySelector(".resolve-hint")?.remove();
  const msg = form.querySelector(".form-message");
  msg.hidden = true;
  msg.textContent = "";
  form.querySelector(".form-status").replaceChildren();
}

/** 清除表單（Esc）：恢復初始值並把焦點放在第一個輸入欄。 */
export function clearForm(sheetId) {
  const form = getForm(sheetId);
  if (!form) return;
  resetValues(form, sheetId);
  form.querySelector(".control:not([readonly])")?.focus();
}

/** 讀出畫面上的原始值（字串、{text, direction}、布林）。 */
function rawValues(form, sheetId, fields) {
  const values = {};
  for (const f of fields) {
    const ctrl = control(form, sheetId, f.id);
    if (!ctrl) continue;
    if (f.kind === "bool") values[f.id] = ctrl.checked;
    else if (f.kind === "direction") {
      values[f.id] = { text: ctrl.value, direction: fieldWrap(form, f.id).querySelector(".dir").dataset.direction };
    } else values[f.id] = ctrl.value;
  }
  return values;
}

/**
 * 讀取輸入：回傳 {inputs, errors}（inputs 以引擎鍵為鍵、空白為 null；errors 以欄位 id 為鍵）。
 * actionId 指定時只收集該動作要送出的欄位（sheets.js 的 action.send）。
 * 引擎求出的值若使用者沒有改動，送出完整精度（不是畫面上四捨五入後的數字）。
 */
export function readInputs(sheetId, actionId) {
  const form = getForm(sheetId);
  if (!form) return { inputs: {}, errors: {} };
  const fields = (actionId ? sendFields(sheetId, actionId) : SHEETS[sheetId].fields.filter((f) => !f.output))
    .filter((f) => control(form, sheetId, f.id));
  const kinds = Object.fromEntries(fields.map((f) => [f.id, f]));
  const { inputs, errors } = collect(rawValues(form, sheetId, fields), kinds, settings.get().sep);
  const solvedKeys = [];
  for (const f of fields) {
    const ctrl = control(form, sheetId, f.id);
    if (f.id in errors || ctrl.value !== ctrl.dataset.shown) continue;
    const key = f.key || f.id;
    if (isEngineValue(ctrl)) solvedKeys.push(key);
    const exact = Number(ctrl.dataset.exact);
    if (ctrl.dataset.exact === undefined || !Number.isFinite(exact)) continue;
    inputs[key] = f.kind === "direction"
      ? toSigned(exact, fieldWrap(form, f.id).querySelector(".dir").dataset.direction)
      : exact;
  }
  // 沒有空白時：上次求出且未改動的欄位再當未知數（改了 N 直接按 Enter 就重算 PMT）
  const action = SHEETS[sheetId].actions.find((a) => a.id === actionId) || primaryAction(sheetId);
  forms.get(sheetId).lastAction = action.id; // showResult 依此動作對應錯誤欄位
  return { inputs: resolveBlanks(inputs, action.solve, solvedKeys), errors };
}

/** 顯示 readInputs 的格式錯誤（第一個錯誤欄位取得焦點）。回傳是否有錯誤。 */
export function showErrors(sheetId, errors) {
  const form = getForm(sheetId);
  if (!form) return false;
  clearMessages(form);
  for (const wrap of form.querySelectorAll(".field")) clearFieldError(wrap);
  const ids = Object.keys(errors || {});
  for (const id of ids) {
    const wrap = fieldWrap(form, id);
    if (wrap) setFieldError(wrap, errors[id]);
  }
  if (ids.length) {
    showMessage(form, `有 ${ids.length} 個欄位格式不正確，請修正紅色欄位`);
    control(form, sheetId, ids[0])?.focus();
  }
  return ids.length > 0;
}

function showMessage(form, text) {
  const msg = form.querySelector(".form-message");
  msg.textContent = text;
  msg.hidden = false;
}

/**
 * 重新求解提示：有「求出的輸入欄位」（綠色、非輸出欄）時，在表單下方說明再按計算會重算它；
 * 沒有時移除提示（例：使用者改了那一格）。
 */
function updateResolveHint(form) {
  if (!form) return;
  const has = form.querySelector(".field.solved:not(.output)") !== null;
  const old = form.querySelector(".resolve-hint");
  if (has && !old) {
    form.querySelector(".form-status").after(el("p", { class: "resolve-hint", text: RESOLVE_HINT }));
  } else if (!has && old) {
    old.remove();
  }
}

/** 欄位是使用者自己填的值（非空白、也不是上次引擎求出且未改動的值）。 */
function isUserValue(form, sheetId, f) {
  if (f.output || f.kind === "bool" || f.kind === "select") return false;
  const ctrl = control(form, sheetId, f.id);
  if (!ctrl || ctrl.value.trim() === "") return false;
  return !isEngineValue(ctrl);
}

function pad(n, w) {
  return String(n).padStart(w, "0");
}

/** 把引擎值寫入欄位；回傳畫面上顯示的文字。 */
function fillField(form, sheetId, f, value, shown) {
  const wrap = fieldWrap(form, f.id);
  const ctrl = control(form, sheetId, f.id);
  if (!wrap || !ctrl) return null;
  forgetSolved(ctrl);
  if (Array.isArray(value) && value.length === 3 && f.kind === "date") {
    ctrl.value = `${pad(value[0], 4)}-${pad(value[1], 2)}-${pad(value[2], 2)}`;
  } else if (typeof value === "number") {
    let text = shown ?? String(value);
    if (f.kind === "direction" && !f.output) {
      setDirection(wrap, value < 0 ? "out" : "in");
      text = text.replace(/^-/, "");
    }
    ctrl.value = text;
    ctrl.dataset.exact = String(value);
    updateTiSign(wrap);
  } else if (typeof value === "string" || typeof value === "boolean") {
    ctrl.value = String(value);
  } else {
    return null;
  }
  ctrl.dataset.solved = "1";
  ctrl.dataset.shown = ctrl.value;
  clearFieldError(wrap);
  wrap.classList.add("solved");
  return f.kind === "direction" && typeof value === "number"
    ? `${ctrl.value}（${value < 0 ? "付出" : "收到"}）`
    : ctrl.value;
}

/**
 * 顯示引擎回應：
 *   ok:true  → 求出的欄位填值並加 class "solved"，warnings 列在表單下方
 *   ok:false → field 對得到欄位：欄位加 class "error"、訊息顯示在欄位下方（aria-describedby）；
 *              否則顯示表單層級訊息
 * actionId：剛執行的動作（省略時用最近一次 readInputs 的動作），錯誤 field 先在該動作的欄位中對應。
 * 回傳 {filled: [欄位 id], unmatched: [沒有對應欄位的回傳鍵，如 rows]}，給 Task 22～24 的版面使用。
 */
export function showResult(response, sheetId, actionId) {
  const form = getForm(sheetId);
  const act = actionId || forms.get(sheetId)?.lastAction;
  const result = { filled: [], unmatched: [] };
  if (!form) return result;
  clearMessages(form);
  for (const wrap of form.querySelectorAll(".field")) {
    // 綠色＝目前仍是引擎求出且未改動的值（計算失敗時也保留，提示仍然成立）
    wrap.classList.toggle("solved", isEngineValue(wrap.querySelector(".control")));
    clearFieldError(wrap);
  }
  if (!response || response.ok !== true) {
    const message = (response && response.error) || "計算失敗（沒有原因）";
    const f = fieldForKey(sheetId, response && response.field, act);
    const wrap = f ? fieldWrap(form, f.id) : null;
    if (wrap) {
      setFieldError(wrap, message);
      control(form, sheetId, f.id)?.focus();
    } else {
      showMessage(form, message);
    }
    updateResolveHint(form);
    return result;
  }
  const values = response.values || {};
  const display = response.display || {};
  const lines = [];
  for (const [key, v] of Object.entries(values)) {
    const f = key === "rows" ? null : fieldForKey(sheetId, key, act);
    if (f && isUserValue(form, sheetId, f)) continue; // 引擎回傳的已知值：保留使用者輸入
    const shown = f ? fillField(form, sheetId, f, v, display[key]) : null;
    if (shown === null) {
      result.unmatched.push(key);
      continue;
    }
    result.filled.push(f.id);
    lines.push(`${f.label} ${f.abbr} = ${shown}`);
  }
  // 只有「這次」求出的格子會在下次重算；較早求出的格子降為一般值（仍保留完整精度 exact）
  const solveKeys = new Set(SHEETS[sheetId].actions.flatMap((a) => a.solve || []));
  for (const f of SHEETS[sheetId].fields) {
    if (f.output || result.filled.includes(f.id) || !solveKeys.has(f.key || f.id)) continue;
    const wrap = fieldWrap(form, f.id);
    if (!wrap) continue;
    delete wrap.querySelector(".control").dataset.solved;
    wrap.classList.remove("solved");
  }
  const status = form.querySelector(".form-status");
  if (lines.length) status.append(el("p", { class: "result-line", text: "已求出：" + lines.join("；") }));
  updateResolveHint(form);
  const warnings = response.warnings || [];
  if (warnings.length) {
    const ul = el("ul", { class: "warnings" });
    for (const w of warnings) ul.append(el("li", { text: "⚠ " + w }));
    status.append(ul);
  }
  return result;
}

/** 把一組值寫入表單（例：設定頁顯示目前設定）；values 以欄位 id 為鍵。 */
export function setValues(sheetId, values) {
  const form = getForm(sheetId);
  if (!form) return;
  for (const [id, v] of Object.entries(values || {})) {
    const f = fieldMap(sheetId)[id];
    const ctrl = f && control(form, sheetId, id);
    if (!ctrl) continue;
    if (f.kind === "bool") ctrl.checked = Boolean(v);
    else ctrl.value = v === null || v === undefined ? "" : String(v);
  }
}

/** 計算中：停用動作按鈕並標示 aria-busy。 */
export function setBusy(sheetId, busy) {
  const form = getForm(sheetId);
  if (!form) return;
  form.setAttribute("aria-busy", busy ? "true" : "false");
  for (const b of form.querySelectorAll(".actions button[data-action]")) b.disabled = busy;
}

/** 顯示一般訊息（例：「已套用設定」）。 */
export function showInfo(sheetId, text) {
  const form = getForm(sheetId);
  if (!form) return;
  clearMessages(form);
  form.querySelector(".form-status").append(el("p", { class: "result-line", text }));
}
