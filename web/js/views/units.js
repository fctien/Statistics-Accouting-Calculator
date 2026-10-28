// View：單位換算（工程頁 #eng/units）。類別 → 從單位、到單位（顯示「中文 符號」）→ 輸入值即時換算。
// 單位清單來自引擎 units/list（只取一次）；換算交給 units/convert，數字由引擎依小數位數設定格式化。
// 即時換算：防抖 250 ms＋序號（seq，同 ICONV）——較舊的回應晚到時丟棄，不蓋掉新結果。
// 錯誤（非數值、低於絕對零度、單位不合法）顯示在對應欄位下方，結果清空（不留舊數字）。
// 千分位設定改變：數值文字依「輸入時的寫法」（textSep）解讀後改寫成新寫法，不以新設定重新解讀
// （否則 US 的 1,000 在 EU 會變成 1）；原本就解不出來時清空結果並請使用者重新輸入。
import { callEngine } from "../py-client.js";
import * as settingsStore from "../settings.js";
import { debounce } from "../util.js";
import { unitsRequest, unitLabel, swapUnits, createSeq, rewriteForSep } from "../eng.js";

const DELAY_MS = 250;
let listPromise = null; // units/list 的結果（成功才快取）
// 切換畫面再回來仍保留；textSep＝數值文字是在哪個千分位設定下輸入的（null＝跟隨目前設定）
const state = { cat: null, from: null, to: null, text: "1", textSep: null };
let listener = null;

function el(tag, attrs = {}, text = "") {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    node.setAttribute(k, v === true ? "" : String(v));
  }
  if (text) node.textContent = text;
  return node;
}

/** 取單位清單；失敗時不快取（下次再試）。 */
async function loadList() {
  if (!listPromise) {
    listPromise = callEngine({ sheet: "units", action: "list", inputs: {} }).then((r) => {
      if (r.ok !== true) throw new Error(r.error || "取得單位清單失敗");
      return r.values.categories;
    });
    listPromise.catch(() => { listPromise = null; });
  }
  return listPromise;
}

/** 一個欄位：標籤、控制項、錯誤訊息。 */
function field(id, label, control) {
  const wrap = el("div", { class: "field", "data-field": id });
  const head = el("div", { class: "field-head" });
  head.append(el("label", { for: control.id }, label));
  const err = el("p", { class: "field-error", id: `${control.id}-error`, hidden: true });
  control.classList.add("control");
  control.setAttribute("aria-describedby", err.id);
  const row = el("div", { class: "field-input" });
  row.append(control);
  wrap.append(head, row, err);
  return { wrap, row, err };
}

export async function mount(container) {
  if (listener) document.removeEventListener("bacalc-settings", listener);
  const root = el("div", { class: "eng-units" });
  const loading = el("p", { class: "calc-note", role: "status" }, "載入單位清單中…");
  root.append(loading);
  container.replaceChildren(root);

  let cats;
  try {
    cats = await loadList();
  } catch (e) {
    loading.className = "form-message";
    loading.setAttribute("role", "alert");
    loading.textContent = `無法取得單位清單：${(e && e.message) || e}`;
    return;
  }
  if (!root.isConnected) return;

  const catSel = el("select", { id: "u-cat" });
  for (const c of cats) catSel.append(el("option", { value: c.id }, `${c.zh} ${c.en}`));
  const value = el("input", {
    id: "u-value", type: "text", inputmode: "decimal", autocomplete: "off", spellcheck: "false",
    placeholder: "例：1",
  });
  const fromSel = el("select", { id: "u-from" });
  const toSel = el("select", { id: "u-to" });
  const swap = el("button", {
    type: "button", id: "u-swap", class: "btn unit-swap", title: "交換從單位與到單位", "aria-label": "交換單位",
  }, "⇄");

  const fCat = field("cat", "類別", catSel);
  const fValue = field("VALUE", "數值", value);
  const fFrom = field("FROM", "從單位", fromSel);
  const fTo = field("TO", "到單位", toSel);
  const grid = el("div", { class: "fields unit-fields" });
  const swapRow = el("div", { class: "unit-swap-row" });
  swapRow.append(swap);
  grid.append(fCat.wrap, fValue.wrap, fFrom.wrap, swapRow, fTo.wrap);

  const result = el("output", { id: "u-result", class: "calc-result unit-result", "aria-live": "polite", for: "u-value u-from u-to" });
  const message = el("div", { id: "u-message", class: "form-message", role: "alert", hidden: true });
  const note = el("p", { class: "calc-note" }, "結果的小數位數依頁首／設定的小數位數（可選浮動）；輸入即時換算");
  root.replaceChildren(grid, result, message, note);

  const errs = { VALUE: fValue.err, FROM: fFrom.err, TO: fTo.err };
  const seq = createSeq();

  const catOf = (id) => cats.find((c) => c.id === id) || cats[0];
  const unitOf = (id) => catOf(catSel.value).units.find((u) => u.id === id);

  function fillUnits(keepFrom, keepTo) {
    const cat = catOf(catSel.value);
    for (const sel of [fromSel, toSel]) {
      sel.replaceChildren(...cat.units.map((u) => el("option", { value: u.id }, unitLabel(u))));
    }
    const ids = cat.units.map((u) => u.id);
    fromSel.value = ids.includes(keepFrom) ? keepFrom : ids[0];
    toSel.value = ids.includes(keepTo) ? keepTo : ids[Math.min(1, ids.length - 1)];
  }

  function clearOutput() {
    result.textContent = "";
    message.hidden = true;
    message.textContent = "";
    for (const [k, p] of Object.entries(errs)) {
      p.hidden = true;
      p.textContent = "";
      (k === "VALUE" ? fValue : k === "FROM" ? fFrom : fTo).wrap.classList.remove("invalid");
    }
    value.removeAttribute("aria-invalid");
  }

  function showError(text, fieldKey) {
    const p = errs[fieldKey];
    if (p) {
      p.textContent = text;
      p.hidden = false;
      p.closest(".field").classList.add("invalid");
      if (fieldKey === "VALUE") value.setAttribute("aria-invalid", "true");
    } else {
      message.textContent = text;
      message.hidden = false;
    }
  }

  function remember() {
    Object.assign(state, { cat: catSel.value, from: fromSel.value, to: toSel.value, text: value.value });
  }

  /** 千分位設定與輸入時不同：改寫數值文字；回傳 false＝無法改寫（已標錯誤，不換算）。 */
  function syncSep() {
    const sep = settingsStore.get().sep;
    const from = state.textSep || sep;
    state.textSep = sep;
    if (from === sep) return true;
    const r = rewriteForSep(value.value, from, sep);
    if (r.error) {
      seq.bump();
      clearOutput();
      showError(r.error, "VALUE");
      return false;
    }
    value.value = r.text;
    remember();
    return true;
  }

  async function convert() {
    remember();
    const my = seq.next();
    clearOutput();
    const r = unitsRequest(value.value, fromSel.value, toSel.value, settingsStore.get().sep);
    if (r.empty) return;
    if (r.error) {
      showError(r.error, r.field);
      return;
    }
    const req = { ...r.request, settings: settingsStore.toEngine() };
    let res;
    try {
      res = await callEngine(req);
    } catch (e) {
      res = { ok: false, error: (e && e.message) || String(e), field: null };
    }
    if (!seq.isCurrent(my) || !root.isConnected) return; // 已有較新的請求：丟棄
    if (res.ok !== true) {
      showError(res.error || "換算失敗（沒有原因）", res.field);
      return;
    }
    const f = unitOf(req.inputs.FROM);
    const t = unitOf(req.inputs.TO);
    result.textContent = `${value.value.trim()} ${f ? f.sym : req.inputs.FROM} = ${res.display.value} ${t ? t.sym : req.inputs.TO}`;
  }
  const live = debounce(convert, DELAY_MS);
  const now = () => {
    live.cancel();
    seq.bump();
    convert();
  };

  // 還原上次狀態（預設：長度，第一、二個單位）
  catSel.value = state.cat && cats.some((c) => c.id === state.cat) ? state.cat : cats[0].id;
  fillUnits(state.from, state.to);
  value.value = state.text;

  catSel.addEventListener("change", () => {
    fillUnits(null, null);
    now();
  });
  fromSel.addEventListener("change", now);
  toSel.addEventListener("change", now);
  value.addEventListener("input", () => {
    state.textSep = settingsStore.get().sep; // 使用者以目前設定的寫法輸入
    seq.bump(); // 進行中的舊請求作廢
    result.textContent = ""; // 舊結果不可留著看似目前的
    live();
  });
  value.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.isComposing) {
      e.preventDefault();
      now();
    }
  });
  swap.addEventListener("click", () => {
    const s = swapUnits({ from: fromSel.value, to: toSel.value });
    fromSel.value = s.from;
    toSel.value = s.to;
    now();
  });

  listener = () => {
    if (!root.isConnected) {
      document.removeEventListener("bacalc-settings", listener);
      return;
    }
    live.cancel();
    if (syncSep()) now(); // 小數位數、千分位改了：先改寫數值文字，再重新換算
  };
  document.addEventListener("bacalc-settings", listener);
  if (syncSep()) now();
}
