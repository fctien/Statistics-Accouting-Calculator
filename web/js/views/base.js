// View：進位轉換（工程頁 #eng/base）。
//   - 四欄 BIN／OCT／DEC／HEX 同步：在任一欄輸入，就以該欄的進位交給引擎 base/convert，更新其他三欄
//     （防抖 250 ms＋序號 seq：舊回應晚到時丟棄）；輸入時其他三欄先清空，不留舊值
//   - 位寬 8/16/32/64、有號／無號：改了就以最後輸入的那一欄重新轉換
//   - 位元運算 base/bitwise：A、B 以「目前進位」（最後輸入的那一欄）解讀；NOT 隱藏 B；SAR 只限有號數
//   - 顯示不加千分位；BIN 每 4 位空白分組（只供顯示：送出與複製時都去掉空白）
//   - 超界等錯誤顯示引擎給的原因（例「數值超出 8 位元無號範圍（0～255）」），不截斷、不顯示猜測值
import { callEngine } from "../py-client.js";
import { debounce } from "../util.js";
import {
  BASES, WIDTHS, BIT_OPS, baseRequest, baseFieldUpdates, bitwiseRequest, needsB, opAllowed,
  stripSpaces, createSeq,
} from "../eng.js";

const DELAY_MS = 250;
const SAR_HINT = "SAR（算術右移）只適用於有號數；無號數請用 SHR 或勾選「有號數」";
const SHIFT_OPS = new Set(["SHL", "SHR", "SAR"]);
// 切換畫面再回來仍保留
const state = {
  width: 8, signed: false, source: "DEC", texts: { BIN: "", OCT: "", DEC: "", HEX: "" },
  op: "AND", a: "", b: "",
};

function el(tag, attrs = {}, text = "") {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    node.setAttribute(k, v === true ? "" : String(v));
  }
  if (text) node.textContent = text;
  return node;
}

function field(key, label, control) {
  const wrap = el("div", { class: "field", "data-field": key });
  const head = el("div", { class: "field-head" });
  const lab = el("label", { for: control.id }, label);
  head.append(lab);
  const err = el("p", { class: "field-error", id: `${control.id}-error`, hidden: true });
  control.classList.add("control");
  control.setAttribute("aria-describedby", err.id);
  const row = el("div", { class: "field-input" });
  row.append(control);
  wrap.append(head, row, err);
  return { wrap, lab, err, control };
}

function setError(f, text) {
  f.err.textContent = text || "";
  f.err.hidden = !text;
  f.wrap.classList.toggle("invalid", Boolean(text));
  if (text) f.control.setAttribute("aria-invalid", "true");
  else f.control.removeAttribute("aria-invalid");
}

/** BIN 的 textarea 依內容調整高度（64 位元在手機上換成 3 行，不截斷）。 */
function fit(t) {
  if (t.tagName !== "TEXTAREA" || !t.isConnected) return;
  t.style.height = "auto";
  t.style.height = `${t.scrollHeight + 2}px`;
}

/** 複製 BIN（輸入框或結果）：去掉分組空白。 */
function stripOnCopy(input) {
  input.addEventListener("copy", (e) => {
    const { selectionStart: a, selectionEnd: b, value } = input;
    const text = a !== null && b !== null && a !== b ? value.slice(a, b) : value;
    if (!e.clipboardData) return;
    e.clipboardData.setData("text/plain", stripSpaces(text));
    e.preventDefault();
  });
}

export function mount(container) {
  const root = el("div", { class: "eng-base" });

  // ---- 位寬與有號
  const widthSel = el("select", { id: "b-width" });
  for (const w of WIDTHS) widthSel.append(el("option", { value: w }, `${w} 位元`));
  const signed = el("input", { id: "b-signed", type: "checkbox" });
  const opts = el("div", { class: "base-opts" });
  const wLab = el("label", { for: "b-width" }, "位寬 ");
  widthSel.classList.add("control");
  const sLab = el("label", { for: "b-signed", class: "base-signed" });
  sLab.append(signed, " 有號數（二補數）");
  opts.append(wLab, widthSel, sLab);
  const range = el("p", { id: "b-range", class: "calc-note" });

  // ---- 四欄
  const conv = el("section", { class: "base-conv", "aria-labelledby": "b-conv-title" });
  conv.append(el("h3", { id: "b-conv-title" }, "進位轉換"));
  const grid = el("div", { class: "fields base-fields" });
  const fields = {};
  for (const b of BASES) {
    // BIN 用 textarea：64 位元分組後約 79 字，手機上要能換行完整顯示（不截斷）
    const input = el(b.id === "BIN" ? "textarea" : "input", {
      id: `b-${b.id}`, type: b.id === "BIN" ? null : "text", rows: b.id === "BIN" ? 2 : null, autocomplete: "off", autocapitalize: "characters", spellcheck: "false",
      "data-base": b.id, inputmode: b.id === "DEC" ? "numeric" : "text",
      placeholder: { BIN: "例：1111 1111", OCT: "例：377", DEC: "例：255", HEX: "例：FF" }[b.id],
    });
    if (b.id === "BIN") stripOnCopy(input);
    const f = field(b.id, b.label, input);
    grid.append(f.wrap);
    fields[b.id] = f;
  }
  conv.append(grid, el("p", { class: "calc-note" },
    "在任一欄輸入，其他三欄即時更新；BIN 每 4 位以空白分組（只供顯示，複製時自動去掉空白）"));

  // ---- 位元運算
  const bit = el("section", { class: "base-bit", "aria-labelledby": "b-bit-title" });
  bit.append(el("h3", { id: "b-bit-title" }, "位元運算"));
  const radixNote = el("p", { id: "b-radix", class: "base-radix" });
  const aIn = el("input", { id: "b-a", type: "text", autocomplete: "off", spellcheck: "false" });
  const opSel = el("select", { id: "b-op" });
  for (const op of BIT_OPS) opSel.append(el("option", { value: op }, op));
  const bIn = el("input", { id: "b-b", type: "text", autocomplete: "off", spellcheck: "false" });
  stripOnCopy(aIn);
  stripOnCopy(bIn);
  const fA = field("A", "A", aIn);
  const fOp = field("OP", "運算", opSel);
  const fB = field("B", "B", bIn);
  const sarHint = el("p", { id: "b-sar-hint", class: "calc-hint", hidden: true }, SAR_HINT);
  const bitGrid = el("div", { class: "fields base-bit-fields" });
  bitGrid.append(fA.wrap, fOp.wrap, fB.wrap);
  const outGrid = el("div", { class: "fields base-out", role: "group", "aria-label": "位元運算結果" });
  const outs = {};
  for (const b of BASES) {
    const o = b.id === "BIN"
      ? el("textarea", { id: `b-r-${b.id}`, rows: 2, readonly: true })
      : el("input", { id: `b-r-${b.id}`, type: "text", readonly: true });
    if (b.id === "BIN") stripOnCopy(o);
    const f = field(`R${b.id}`, `結果 ${b.id}`, o);
    f.wrap.classList.add("output");
    outGrid.append(f.wrap);
    outs[b.id] = o;
  }
  const bitMsg = el("div", { id: "b-bit-message", class: "form-message", role: "alert", hidden: true });
  bit.append(radixNote, bitGrid, sarHint, bitMsg, outGrid);

  root.append(opts, range, conv, bit);
  container.replaceChildren(root);

  // ---- 狀態還原
  widthSel.value = String(state.width);
  signed.checked = state.signed;
  for (const b of BASES) fields[b.id].control.value = state.texts[b.id];
  opSel.value = state.op;
  aIn.value = state.a;
  bIn.value = state.b;

  const convSeq = createSeq();
  const bitSeq = createSeq();
  const width = () => Number(widthSel.value);

  function remember() {
    state.width = width();
    state.signed = signed.checked;
    for (const b of BASES) state.texts[b.id] = fields[b.id].control.value;
    Object.assign(state, { op: opSel.value, a: aIn.value, b: bIn.value });
  }

  function renderOpts() {
    const w = width();
    range.textContent = signed.checked
      ? `${w} 位元有號：−2^${w - 1}～2^${w - 1}−1（負數以二補數表示）`
      : `${w} 位元無號：0～2^${w}−1`;
    const label = BASES.find((b) => b.id === state.source).label;
    radixNote.textContent = `A、B 依目前進位：${label}（最後輸入的那一欄）`;
    aIn.placeholder = `依目前進位（${state.source}）`;
    const shift = SHIFT_OPS.has(opSel.value);
    fB.lab.textContent = shift ? `B（位移量 0～${w}，${state.source}）` : "B";
    bIn.placeholder = shift ? "位移量，例：1" : `依目前進位（${state.source}）`;
    fB.wrap.hidden = !needsB(opSel.value);
    const sar = opSel.querySelector('option[value="SAR"]');
    sar.disabled = !signed.checked && opSel.value !== "SAR"; // 已選 SAR 時保留選項，改以提示說明
    sarHint.hidden = signed.checked;
  }

  // ---- 進位轉換
  function clearOthers() {
    for (const b of BASES) {
      if (b.id !== state.source) fields[b.id].control.value = "";
      setError(fields[b.id], "");
    }
    fit(fields.BIN.control);
  }

  async function convert() {
    remember();
    const my = convSeq.next();
    const src = state.source;
    const req = baseRequest(src, fields[src].control.value, width(), signed.checked);
    clearOthers();
    if (!req) return;
    let res;
    try {
      res = await callEngine(req);
    } catch (e) {
      res = { ok: false, error: (e && e.message) || String(e) };
    }
    if (!convSeq.isCurrent(my) || !root.isConnected) return; // 舊請求：丟棄
    if (res.ok !== true) {
      setError(fields[src], res.error || "轉換失敗（沒有原因）");
      return;
    }
    for (const [id, text] of Object.entries(baseFieldUpdates(src, res.values))) fields[id].control.value = text;
    fit(fields.BIN.control);
    remember();
  }
  const convLive = debounce(convert, DELAY_MS);

  // ---- 位元運算
  function clearBit() {
    for (const o of Object.values(outs)) o.value = "";
    fit(outs.BIN);
    for (const f of [fA, fB, fOp]) setError(f, "");
    bitMsg.hidden = true;
    bitMsg.textContent = "";
  }

  async function runBit() {
    remember();
    const my = bitSeq.next();
    clearBit();
    const op = opSel.value;
    if (!opAllowed(op, signed.checked)) {
      setError(fOp, SAR_HINT);
      return;
    }
    const req = bitwiseRequest({
      op, a: aIn.value, b: bIn.value, fromId: state.source, width: width(), signed: signed.checked,
    });
    if (!req) return;
    let res;
    try {
      res = await callEngine(req);
    } catch (e) {
      res = { ok: false, error: (e && e.message) || String(e) };
    }
    if (!bitSeq.isCurrent(my) || !root.isConnected) return;
    if (res.ok !== true) {
      const f = { A: fA, B: fB, OP: fOp }[res.field];
      if (f) setError(f, res.error);
      else {
        bitMsg.textContent = res.error || "運算失敗（沒有原因）";
        bitMsg.hidden = false;
      }
      return;
    }
    for (const [id, text] of Object.entries(baseFieldUpdates(null, res.values))) outs[id].value = text;
    fit(outs.BIN);
  }
  const bitLive = debounce(runBit, DELAY_MS);

  const nowBoth = () => {
    convLive.cancel();
    bitLive.cancel();
    convSeq.bump();
    bitSeq.bump();
    renderOpts();
    convert();
    runBit();
  };

  // ---- 事件
  grid.addEventListener("input", (e) => {
    const id = e.target.dataset?.base;
    if (!id) return;
    fit(e.target);
    const changed = id !== state.source;
    state.source = id;
    convSeq.bump(); // 進行中的舊請求作廢
    clearOthers();
    convLive();
    if (changed) { // 目前進位變了：A、B 的解讀跟著變
      renderOpts();
      bitSeq.bump();
      clearBit();
      bitLive();
    }
  });
  widthSel.addEventListener("change", nowBoth);
  signed.addEventListener("change", nowBoth);
  opSel.addEventListener("change", () => {
    renderOpts();
    bitLive.cancel();
    bitSeq.bump();
    runBit();
  });
  for (const inp of [aIn, bIn]) {
    inp.addEventListener("input", () => {
      bitSeq.bump();
      clearBit();
      bitLive();
    });
  }
  root.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && e.target.matches("input, textarea") && !e.isComposing) {
      e.preventDefault();
      nowBoth();
    }
  });

  renderOpts();
  fit(fields.BIN.control);
  if (fields[state.source].control.value.trim()) convert();
  if (aIn.value.trim()) runBit();
}
