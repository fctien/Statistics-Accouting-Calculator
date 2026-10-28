// View：科學計算機（工程頁 #eng/calc）。算式輸入框、科學鍵（三角／反三角用 2nd、log、ln、∛、π、e、±、
// DEG／RAD 切換）、數字鍵、紙帶（tape）、M0～M9 記憶面板與累加器 Σ。
// 角度單位存在 settings.angle，計算時隨 settings 送出；切換後，已顯示的結果若是另一模式算的就標過期（stale）。
// 所有運算與數字格式化都交給引擎（callEngine，sheet "calc" / action "eval"）：
//   - 算式結果、記憶與 Σ 的顯示字串都由引擎依小數位數與千分位設定產生，JS 不自己格式化；
//   - 記憶值以原始浮點數存在 memstore.js（鏡射 engine/memory.py），作為 MEM 送給引擎。
// 狀態（紙帶、記憶、ANS）放在模組層級：切換工作表再回來仍在；紙帶與記憶另存 IndexedDB（storage/persist.js），
// 啟動時由 app.js 呼叫 replaceState 還原（內容經 fromJSON／createTape 驗證，壞資料被丟棄）。
// 錯誤不進紙帶，顯示在輸入框下方。
import { callEngine } from "../py-client.js";
import * as settingsStore from "../settings.js";
import { createMemStore, fromJSON as memFromJSON } from "../memstore.js";
import { createTape, createWalker, MAX_ENTRIES } from "../tape.js";
import * as persist from "../storage/persist.js";
import { createGuard } from "../generation.js";
import { KEY_ROWS, SCI_ROWS, insertAt, backspaceAt, toggleSign } from "../keypad.js";
import { evalRequest, angleLabel, resultIsStale } from "../eng.js";

let memory = createMemStore();
const tape = createTape();
const walker = createWalker(tape);
let ans = 0; // 上一次成功的值（原始浮點數）；初始 0，同引擎預設
let ansDisplay = "";
let ansAngle = null; // ANS 是在哪個角度模式算出的（null＝還沒有結果）
let listener = null; // 目前掛載的畫面對 bacalc-settings 的監聽（重新掛載時移除舊的）

/**
 * 以儲存的資料取代紙帶與記憶（啟動還原、匯入備份、清除全部資料用）。
 * tapeEntries：紙帶項目陣列或 null；memoryData：memstore.toJSON() 形狀或 null（null＝清空）。
 * 無效資料由 createTape／fromJSON 安全丟棄；這裡不會觸發儲存（呼叫端已處理）。
 */
export function replaceState(tapeEntries, memoryData) {
  tape.clear();
  if (Array.isArray(tapeEntries)) {
    for (const e of createTape(MAX_ENTRIES, tapeEntries).list()) {
      tape.add({ expr: e.expr, value: e.value, display: e.display, ts: e.ts });
    }
  }
  memory = memoryData ? memFromJSON(memoryData) : createMemStore();
  walker.reset();
  ans = 0;
  ansDisplay = "";
  ansAngle = null;
}

const saveTape = () => persist.saveTape(tape.toJSON());
const saveMemory = () => persist.saveMemory(memory.toJSON());

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
function evaluate(expr, settings = settingsStore.toEngine()) {
  return callEngine(evalRequest(expr, ans, memory.toEngineMem(), settings));
}

/** 把原始數值交給引擎格式化（當成數字常數算式）；失敗時回傳 null，由呼叫端保留舊顯示或標 "?"（不顯示猜測值）。 */
async function formatValue(x) {
  try {
    const r = await evaluate(String(x));
    return r.ok === true ? r.display.value : null;
  } catch (e) {
    return null;
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

  // ---- 按鍵面板：科學鍵（5 欄）＋數字鍵（4 欄）
  const sciPad = el("div", { class: "keypad keypad-sci", role: "group", "aria-label": "科學鍵" });
  const pad = el("div", { class: "keypad", role: "group", "aria-label": "按鍵面板" });
  const KEY_IDS = {
    back: "calc-back", clear: "calc-clear-input", second: "calc-2nd", angle: "calc-angle", negate: "calc-negate",
  };
  const sciKeys = []; // 有 2nd 替代的鍵：[按鈕, 鍵定義]
  const addKey = (parent, k) => {
    const b = el("button", {
      type: "button", class: `key key-${k.kind}`, title: k.title || k.label,
      "data-insert": k.insert, "data-action": k.action, id: KEY_IDS[k.action],
    }, k.label);
    parent.append(b);
    if (k.second) sciKeys.push([b, k]);
    return b;
  };
  for (const row of SCI_ROWS) for (const k of row) addKey(sciPad, k);
  for (const row of KEY_ROWS) for (const k of row) addKey(pad, k);
  const back = sciPad.querySelector("#calc-back");
  const clr = sciPad.querySelector("#calc-clear-input");
  const secondKey = sciPad.querySelector("#calc-2nd");
  const angleKey = sciPad.querySelector("#calc-angle");
  secondKey.setAttribute("aria-pressed", "false");
  let second = false; // 2nd 狀態：插入一個第二功能後自動放開（同 TI）

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
  main.append(modeLine, hint, inputRow, error, status, result, sciPad, pad);
  root.append(main, memBox, tapeBox);
  container.replaceChildren(root);

  // ---- 狀態更新
  let busy = false;
  let memGen = 0;
  const reformatGuard = createGuard(); // 重新格式化的世代：較舊的一輪結果丟棄

  const showError = (text) => {
    error.textContent = text;
    error.hidden = !text;
    if (text) status.textContent = ""; // 失敗時不留上一個成功動作的說明
  };
  const say = (text) => { status.textContent = text; };

  function renderMode() {
    const { mode, angle } = settingsStore.get();
    modeLine.textContent = `運算順序：${mode === "CHAIN" ? "依序 Chain" : "代數 AOS"}（可在「設定」更改）`
      + `｜角度：${angleLabel(angle)}`;
    angleKey.textContent = angle;
    angleKey.title = `角度單位目前為 ${angleLabel(angle)}，按一下切換為 ${angle === "DEG" ? "RAD 弧度" : "DEG 度"}`;
    angleKey.setAttribute("aria-label", angleKey.title);
    hint.textContent = CHAIN_HINT;
    hint.hidden = mode !== "CHAIN";
  }

  function renderResult() {
    const angle = settingsStore.get().angle;
    const stale = Boolean(ansDisplay) && resultIsStale(ansAngle, angle);
    result.classList.toggle("stale", stale);
    result.replaceChildren();
    if (ansDisplay) result.append(el("span", { class: "calc-ans" }, `ANS = ${ansDisplay}`));
    if (stale) {
      result.append(el("span", { class: "calc-stale-note" },
        `${ansAngle} 模式的結果；目前是 ${angle}，請按 ＝ 重新計算`));
      result.title = "這是舊角度模式的結果";
    } else {
      result.removeAttribute("title");
    }
  }

  function setSecond(on) {
    second = on;
    secondKey.setAttribute("aria-pressed", String(on));
    secondKey.classList.toggle("key-on", on);
    for (const [b, k] of sciKeys) {
      const v = on ? k.second : k;
      b.textContent = v.label;
      b.title = v.title || v.label;
      b.dataset.insert = v.insert;
    }
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
      b.append(el("span", { class: "mem-name" }, `M${i}`), el("span", { class: "mem-val" }, texts[i] ?? "?"));
      frag.append(b);
    });
    cells.replaceChildren(frag);
    sigma.textContent = `Σ = ${texts[10] ?? "?"}　筆數 n = ${memory.count}`;
  }

  /** 設定（小數位數、千分位、運算順序）改變：紙帶與記憶面板重新由引擎格式化。 */
  async function reformatAll() {
    renderMode();
    const token = reformatGuard.bump("tape");
    const items = tape.list(); // 項目物件（含唯一編號）；之後以編號回寫，不用位置
    const ansAtStart = ans;
    const [a, ...rest] = await Promise.all([formatValue(ans), ...items.map((e) => formatValue(e.value))]);
    if (!root.isConnected || !reformatGuard.isCurrent("tape", token)) return; // 有更新的一輪，丟棄本輪
    items.forEach((e, i) => {
      if (rest[i] !== null) tape.setDisplayById(e.id, rest[i]); // 引擎失敗就保留舊字串；項目已不在則略過
    });
    if (ansDisplay && a !== null && ans === ansAtStart) ansDisplay = a;
    renderResult();
    renderTape();
    renderMemory();
    if (items.length) saveTape(); // 顯示字串改了：一併存起來
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
    if (busy) {
      say("計算中…請稍候");
      return null;
    }
    busy = true;
    eq.disabled = true;
    const settings = settingsStore.toEngine(); // 送出當下的設定（含角度單位）
    try {
      const r = await evaluate(expr, settings);
      if (r.ok !== true) {
        showError(r.error || "計算失敗（沒有原因）");
        return null;
      }
      const value = r.values.value;
      const display = r.display.value;
      ans = value;
      ansDisplay = display;
      ansAngle = settings.angle;
      if (record) {
        tape.add({ expr, value, display, ts: Date.now() });
        walker.reset();
        renderTape();
        saveTape();
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
    let shown = ansDisplay || (await formatValue(ans)) || "?";
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
    saveMemory();
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
  const onPad = (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    if (b === back) {
      const r = backspaceAt(input.value, input.selectionStart, input.selectionEnd);
      setInput(r.text, r.caret);
    } else if (b === clr) {
      setInput("");
      showError("");
    } else if (b === secondKey) {
      setSecond(!second);
    } else if (b === angleKey) {
      const next = settingsStore.get().angle === "DEG" ? "RAD" : "DEG";
      settingsStore.commit({ angle: next }); // 觸發 bacalc-settings → renderMode／renderResult
      say(`角度單位：${angleLabel(next)}`);
    } else if (b.dataset.action === "negate") {
      const r = toggleSign(input.value, input.selectionStart ?? input.value.length);
      setInput(r.text, r.caret);
      walker.reset();
    } else if (b.dataset.insert !== undefined) {
      insert(b.dataset.insert);
      if (second && sciPad.contains(b)) setSecond(false);
    }
  };
  sciPad.addEventListener("click", onPad);
  pad.addEventListener("click", onPad);
  memKeys.addEventListener("click", (e) => {
    const b = e.target.closest("button[data-op]");
    if (b) memOp(b.dataset.op);
  });
  memClear.addEventListener("click", () => {
    memory.clearAll();
    say("已清除全部記憶與 Σ");
    saveMemory();
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
    saveTape();
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
