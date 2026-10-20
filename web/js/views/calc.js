// View：計算機 CALC。算式輸入框、按鍵面板（手機）、紙帶（tape）、M0～M9 記憶面板與累加器 Σ。
// 所有運算與數字格式化都交給引擎（callEngine，sheet "calc" / action "eval"）：
//   - 算式結果、記憶與 Σ 的顯示字串都由引擎依小數位數與千分位設定產生，JS 不自己格式化；
//   - 記憶值以原始浮點數存在 memstore.js（鏡射 engine/memory.py），作為 MEM 送給引擎。
// 狀態（紙帶、記憶、ANS）放在模組層級：切換工作表再回來仍在（持久化由 Task 25 接手）。
// 錯誤不進紙帶，顯示在輸入框下方。
import { callEngine } from "../py-client.js";
import * as settingsStore from "../settings.js";
import { createMemStore } from "../memstore.js";
import { createTape, createWalker } from "../tape.js";
import { KEY_ROWS, insertAt, backspaceAt } from "../keypad.js";

const memory = createMemStore();
const tape = createTape();
const walker = createWalker(tape);
let ans = 0; // 上一次成功的值（原始浮點數）；初始 0，同引擎預設
let ansDisplay = "";
let listener = null; // 目前掛載的畫面對 bacalc-settings 的監聽（重新掛載時移除舊的）

function el(tag, attrs = {}, text = "") {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    node.setAttribute(k, v === true ? "" : String(v));
  }
  if (text) node.textContent = text;
  return node;
}

const CHAIN_HINT = "依序（Chain）模式：+ − × ÷ ^ 一律由左到右，所以 2+3×4 = 20，且 −2^2 = 4（AOS 模式為 14 與 −4）";

/** 呼叫引擎計算算式（用目前的 ANS、記憶與設定）。 */
function evaluate(expr) {
  return callEngine({
    sheet: "calc", action: "eval",
    inputs: { EXPR: expr, ANS: ans, MEM: memory.toEngineMem() },
    settings: settingsStore.toEngine(),
  });
}

/** 把原始數值交給引擎格式化（當成數字常數算式）；失敗時回傳 "?"，不會顯示猜測值。 */
async function formatValue(x) {
  try {
    const r = await evaluate(String(x));
    return r.ok === true ? r.display.value : "?";
  } catch (e) {
    return "?";
  }
}

export function mount(container) {
  if (listener) document.removeEventListener("bacalc-settings", listener);

  // ---- 版面
  const root = el("div", { class: "calc" });
  const modeLine = el("p", { id: "calc-mode", class: "calc-mode" });
  const hint = el("p", { id: "calc-hint", class: "calc-hint", hidden: true });

  const input = el("input", {
    id: "calc-expr", class: "calc-expr control", type: "text", autocomplete: "off", autocapitalize: "off",
    spellcheck: "false", enterkeyhint: "go", "aria-label": "算式", "aria-describedby": "calc-error calc-mode",
    placeholder: "輸入算式，例：200+10%",
  });
  const eq = el("button", { type: "button", id: "calc-eq", class: "btn btn-primary calc-eq", title: "計算（Enter）" }, "＝");
  const inputRow = el("div", { class: "calc-input-row" });
  inputRow.append(input, eq);
  const error = el("div", { id: "calc-error", class: "form-message", role: "alert", hidden: true });
  const status = el("p", { id: "calc-status", class: "calc-status", role: "status", "aria-live": "polite" });
  const result = el("output", { id: "calc-result", class: "calc-result", "aria-label": "結果", "aria-live": "polite" });

  // ---- 按鍵面板
  const pad = el("div", { class: "keypad", role: "group", "aria-label": "按鍵面板" });
  const addKey = (k, extra = "") => {
    const b = el("button", {
      type: "button", class: `key key-${k.kind} ${extra}`.trim(), title: k.title || k.label, "data-insert": k.insert,
    }, k.label);
    pad.append(b);
    return b;
  };
  for (const row of KEY_ROWS) for (const k of row) addKey(k);
  for (const k of [
    { label: "ln", insert: "ln(", title: "自然對數", kind: "fn" },
    { label: "eˣ", insert: "exp(", title: "e 的次方", kind: "fn" },
    { label: "nPr", insert: "nPr(", title: "排列：nPr(5,2)", kind: "fn" },
    { label: "nCr", insert: "nCr(", title: "組合：nCr(5,2)", kind: "fn" },
    { label: ",", insert: ",", title: "引數分隔（nPr、nCr 用）", kind: "fn" },
  ]) addKey(k);
  const back = el("button", { type: "button", id: "calc-back", class: "key key-fn", title: "退格" }, "⌫");
  const clr = el("button", { type: "button", id: "calc-clear-input", class: "key key-fn", title: "清除輸入（Esc）" }, "C");
  pad.append(back, clr);

  // ---- 記憶
  const memBox = el("section", { class: "calc-mem", "aria-labelledby": "calc-mem-title" });
  memBox.append(el("h3", { id: "calc-mem-title" }, "記憶 M0–M9 與累加 Σ"));
  const idx = el("select", { id: "calc-mem-idx", class: "control", "aria-label": "記憶編號" });
  for (let i = 0; i < 10; i++) idx.append(el("option", { value: i }, `M${i}`));
  const memKeys = el("div", { class: "mem-keys" });
  const MEM_OPS = [
    ["sto", "STO", "把目前的值存入所選記憶（取代原值）"],
    ["rcl", "RCL", "把所選記憶（例 M3）插入算式"],
    ["add", "M+", "目前的值加進所選記憶"],
    ["sub", "M−", "從所選記憶減去目前的值"],
    ["mul", "M×", "所選記憶乘以目前的值"],
    ["div", "M÷", "所選記憶除以目前的值（除以 0 會報錯，記憶不變）"],
    ["sigma", "Σ+", "把目前的值加進累加器 Σ，筆數加一"],
  ];
  for (const [op, label, title] of MEM_OPS) {
    memKeys.append(el("button", { type: "button", class: "btn mem-key", "data-op": op, title }, label));
  }
  const memClear = el("button", { type: "button", id: "calc-mem-clear", class: "btn btn-ghost", title: "全部記憶與 Σ 歸零" }, "清除記憶");
  memKeys.append(memClear);
  const note = el("p", { class: "calc-note" }, "「目前的值」＝輸入框的算式結果；輸入框是空的就用 ANS");
  const cells = el("div", { id: "calc-mem-cells", class: "mem-cells" });
  const sigma = el("p", { id: "calc-sigma", class: "calc-sigma" });
  const row = el("div", { class: "mem-row" });
  row.append(el("label", { for: "calc-mem-idx" }, "記憶編號 "), idx);
  memBox.append(row, memKeys, note, cells, sigma);

  // ---- 紙帶
  const tapeBox = el("section", { class: "calc-tape", "aria-labelledby": "calc-tape-title" });
  const tapeHead = el("div", { class: "tape-head" });
  tapeHead.append(el("h3", { id: "calc-tape-title" }, "紙帶 Tape"));
  const tapeClear = el("button", { type: "button", id: "calc-tape-clear", class: "btn btn-ghost" }, "清除紙帶");
  tapeHead.append(tapeClear);
  const tapeList = el("ol", { id: "calc-tape-list", class: "tape-list", reversed: true });
  const tapeEmpty = el("p", { class: "calc-note", id: "calc-tape-empty" }, "還沒有計算紀錄；按 Enter 或 ＝ 計算，點紙帶的任一行可把算式帶回輸入框");
  tapeBox.append(tapeHead, tapeEmpty, tapeList);

  const main = el("div", { class: "calc-main" });
  main.append(modeLine, hint, inputRow, error, status, result, pad);
  root.append(main, memBox, tapeBox);
  container.replaceChildren(root);

  // ---- 狀態更新
  let busy = false;
  let memGen = 0;

  const showError = (text) => {
    error.textContent = text;
    error.hidden = !text;
    if (text) status.textContent = ""; // 失敗時不留上一個成功動作的說明
  };
  const say = (text) => { status.textContent = text; };

  function renderMode() {
    const mode = settingsStore.get().mode;
    modeLine.textContent = `運算順序：${mode === "CHAIN" ? "依序 Chain" : "代數 AOS"}（可在「設定」更改）`;
    hint.textContent = CHAIN_HINT;
    hint.hidden = mode !== "CHAIN";
  }

  function renderResult() {
    result.textContent = ansDisplay ? `ANS = ${ansDisplay}` : "";
  }

  function renderTape() {
    const items = tape.list();
    tapeEmpty.hidden = items.length > 0;
    tapeClear.disabled = items.length === 0;
    tapeList.hidden = items.length === 0;
    const frag = document.createDocumentFragment();
    for (let i = items.length - 1; i >= 0; i--) { // 新的在上
      const e = items[i];
      const li = el("li");
      const b = el("button", { type: "button", class: "tape-line", "data-i": i, title: "點一下把算式帶回輸入框" });
      b.append(el("span", { class: "tape-expr" }, e.expr), el("span", { class: "tape-eq" }, " = "),
        el("span", { class: "tape-val" }, e.display));
      li.append(b);
      frag.append(li);
    }
    tapeList.replaceChildren(frag);
  }

  /** 記憶面板與 Σ：數值由引擎格式化（Promise.all 一次取十格＋Σ）。 */
  async function renderMemory() {
    const gen = ++memGen;
    const vals = memory.values();
    const texts = await Promise.all([...vals, memory.sum].map(formatValue));
    if (gen !== memGen || !root.isConnected) return;
    const frag = document.createDocumentFragment();
    vals.forEach((_, i) => {
      const b = el("button", {
        type: "button", class: "mem-cell", "data-m": i, title: `把 M${i} 插入算式`,
      });
      b.append(el("span", { class: "mem-name" }, `M${i}`), el("span", { class: "mem-val" }, texts[i]));
      frag.append(b);
    });
    cells.replaceChildren(frag);
    sigma.textContent = `Σ = ${texts[10]}　筆數 n = ${memory.count}`;
  }

  /** 設定（小數位數、千分位、運算順序）改變：紙帶與記憶面板重新由引擎格式化。 */
  async function reformatAll() {
    renderMode();
    const items = tape.list();
    const [a, ...rest] = await Promise.all([formatValue(ans), ...items.map((e) => formatValue(e.value))]);
    if (!root.isConnected) return;
    rest.forEach((t, i) => tape.setDisplay(i, t));
    if (ansDisplay) ansDisplay = a;
    renderResult();
    renderTape();
    renderMemory();
  }

  // ---- 動作
  function setInput(text, caret = text.length, focus = true) {
    input.value = text;
    input.setSelectionRange(caret, caret);
    if (focus && window.matchMedia?.("(pointer: fine)").matches) input.focus(); // 手機不彈出系統鍵盤
  }

  function insert(token) {
    const r = insertAt(input.value, input.selectionStart, input.selectionEnd, token);
    setInput(r.text, r.caret);
    walker.reset();
  }

  /** 計算輸入框的算式；成功回傳 {value, display}，失敗顯示錯誤並回傳 null。 */
  async function calculate({ record = true } = {}) {
    const expr = input.value.trim();
    showError("");
    if (busy) return null;
    busy = true;
    eq.disabled = true;
    try {
      const r = await evaluate(expr);
      if (r.ok !== true) {
        showError(r.error || "計算失敗（沒有原因）");
        return null;
      }
      const value = r.values.value;
      const display = r.display.value;
      ans = value;
      ansDisplay = display;
      if (record) {
        tape.add({ expr, value, display, ts: Date.now() });
        walker.reset();
        renderTape();
      }
      renderResult();
      return { value, display };
    } catch (e) {
      showError((e && e.message) || String(e));
      return null;
    } finally {
      busy = false;
      eq.disabled = false;
    }
  }

  /** 記憶鍵：目前的值＝輸入框算式的結果（空白則用 ANS）。除以零或溢位時記憶不變。 */
  async function memOp(op) {
    const i = Number(idx.value);
    if (op === "rcl") {
      insert(`M${i}`);
      return;
    }
    let value = ans;
    let shown = ansDisplay || (await formatValue(ans));
    if (input.value.trim() !== "") {
      const r = await calculate();
      if (!r) return; // 算式有錯：錯誤已顯示
      ({ value, display: shown } = r);
    }
    showError("");
    let res;
    if (op === "sto") res = memory.store(i, value);
    else if (op === "add") res = memory.add(i, value);
    else if (op === "sub") res = memory.sub(i, value);
    else if (op === "mul") res = memory.mul(i, value);
    else if (op === "div") res = memory.div(i, value);
    else res = memory.accumulate(value);
    if (res.ok !== true) {
      showError(`記憶操作失敗，記憶沒有改變：${res.error}`);
      return;
    }
    const names = { sto: "STO", add: "M+", sub: "M−", mul: "M×", div: "M÷" };
    if (op === "sigma") say(`Σ+ ${shown}`);
    else say(`${names[op]} M${i}（目前的值 ${shown}）`);
    renderMemory();
  }

  // ---- 事件
  eq.addEventListener("click", () => { calculate(); });
  input.addEventListener("keydown", (e) => {
    if (e.isComposing || e.keyCode === 229) return; // 中文輸入法組字中
    if (e.key === "Enter") {
      e.preventDefault();
      calculate();
    } else if (e.key === "ArrowUp" || e.key === "ArrowDown") {
      const next = e.key === "ArrowUp" ? walker.prev(input.value) : walker.next();
      if (next !== null) {
        e.preventDefault();
        setInput(next);
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      setInput("");
      showError("");
      walker.reset();
    }
  });
  input.addEventListener("input", () => { walker.reset(); });
  pad.addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    if (b === back) {
      const r = backspaceAt(input.value, input.selectionStart, input.selectionEnd);
      setInput(r.text, r.caret);
    } else if (b === clr) {
      setInput("");
      showError("");
    } else if (b.dataset.insert !== undefined) {
      insert(b.dataset.insert);
    }
  });
  memKeys.addEventListener("click", (e) => {
    const b = e.target.closest("button[data-op]");
    if (b) memOp(b.dataset.op);
  });
  memClear.addEventListener("click", () => {
    memory.clearAll();
    say("已清除全部記憶與 Σ");
    renderMemory();
  });
  cells.addEventListener("click", (e) => {
    const b = e.target.closest("button[data-m]");
    if (b) insert(`M${b.dataset.m}`);
  });
  tapeList.addEventListener("click", (e) => {
    const b = e.target.closest("button[data-i]");
    if (!b) return;
    showError("");
    setInput(tape.at(Number(b.dataset.i)).expr);
    walker.reset();
  });
  tapeClear.addEventListener("click", () => {
    tape.clear();
    walker.reset();
    renderTape();
  });

  listener = () => {
    if (!root.isConnected) {
      document.removeEventListener("bacalc-settings", listener);
      return;
    }
    reformatAll();
  };
  document.addEventListener("bacalc-settings", listener);

  renderMode();
  renderResult();
  renderTape();
  // 重新掛載時設定可能已改：紙帶與記憶用目前設定重新格式化
  reformatAll();
}
