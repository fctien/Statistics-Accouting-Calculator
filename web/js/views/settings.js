// View：設定 FORMAT。小數位數、千分位、日期格式、運算順序、外觀、稅率預設值；選了就立即生效並儲存
// （settingsStore.commit 會通知畫面重新顯示結果），下方「即時預覽」由引擎格式化。
// 「關於」區：APP 版本、SHELL_HASH（讀 sw.js 文字）、MicroPython 套件版本（讀 py/manifest.json）、啟動計時。
import { SHEETS, TAX_PRESETS } from "../sheets.js";
import { callEngine } from "../py-client.js";
import * as settingsStore from "../settings.js";
import { formatDate } from "../datefmt.js";

const SAMPLE_NUMBER = 1234567.891;
const SAMPLE_DATE = [2026, 12, 31];

function el(tag, attrs = {}, text = "") {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    node.setAttribute(k, v === true ? "" : String(v));
  }
  if (text) node.textContent = text;
  return node;
}

/** 控制項的 value 字串 ↔ 設定值：小數位數的「浮動」用空字串代表 null，其餘整數字串轉成數字。 */
function toSetting(id, text) {
  if (id === "decimals") return text === "" ? null : Number(text);
  return text;
}
function toText(value) {
  return value === null || value === undefined ? "" : String(value);
}

async function fetchText(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.text();
}

/** 從 sw.js 文字取 SHELL_HASH 與 CACHE_VERSION；取不到回傳 null（顯示「讀取失敗」，不編造）。 */
export function parseSwInfo(text) {
  const hash = /const SHELL_HASH = "([^"]*)";/.exec(text);
  const cache = /const CACHE_VERSION = "([^"]*)";/.exec(text);
  return hash ? { shellHash: hash[1], cacheVersion: cache ? cache[1] : null } : null;
}

/** ctx.about：{appVersion, timings}（由 app.js 提供，timings 是會被更新的物件）。 */
export function mount(container, ctx = {}) {
  const sheet = SHEETS.settings;
  const form = el("form", { class: "sheet-form settings-form", "aria-label": sheet.title });
  form.addEventListener("submit", (e) => e.preventDefault());
  const grid = el("div", { class: "fields" });
  const controls = {};

  const addField = (id, label, help, select) => {
    const wrap = el("div", { class: "field", "data-field": id });
    const lab = el("label", { for: `s-${id}` }, label);
    select.id = `s-${id}`;
    select.classList.add("control");
    const h = el("p", { class: "field-help", id: `s-${id}-help` }, help);
    select.setAttribute("aria-describedby", h.id);
    wrap.append(lab, select, h);
    grid.append(wrap);
    controls[id] = select;
  };

  for (const f of sheet.fields) {
    const select = el("select");
    for (const o of f.options) select.append(el("option", { value: toText(o.value) }, o.label));
    addField(f.id, `${f.label} ${f.abbr}`, f.help, select);
    select.addEventListener("change", () => apply({ [f.id]: toSetting(f.id, select.value) }));
  }

  // 稅率預設值：來自 TAX_PRESETS（鏡射 engine/business.py），附出處連結與查證日期
  const taxSelect = el("select");
  taxSelect.append(el("option", { value: "" }, "自訂（不指定）"));
  for (const [name, p] of Object.entries(TAX_PRESETS)) {
    taxSelect.append(el("option", { value: name }, `${name} ${p.rate}%`));
  }
  addField("taxPreset", "稅率預設值 TAX", "開啟「稅額」時預先選好的稅率，例：營業稅 5%", taxSelect);
  taxSelect.addEventListener("change", () => apply({ taxPreset: taxSelect.value }));
  const taxSource = el("p", { id: "s-tax-source", class: "tax-source" });
  grid.querySelector('[data-field="taxPreset"]').append(taxSource);

  const message = el("div", { class: "form-message", role: "alert", hidden: true });
  const status = el("div", { class: "form-status", role: "status", "aria-live": "polite" });
  form.append(grid, message, status);

  // ---- 即時預覽
  const preview = el("section", { class: "settings-preview", "aria-labelledby": "s-preview-title" });
  preview.append(el("h3", { id: "s-preview-title" }, "即時預覽"));
  const pvNumber = el("p", { id: "s-preview-number" });
  const pvDate = el("p", { id: "s-preview-date" });
  preview.append(pvNumber, pvDate);

  // ---- 關於
  const about = el("section", { class: "settings-about", "aria-labelledby": "s-about-title" });
  about.append(el("h3", { id: "s-about-title" }, "關於"));
  const dl = el("dl", { id: "s-about-list", class: "about-list" });
  about.append(dl);
  const rows = {};
  for (const [key, label] of [
    ["version", "程式版本 APP_VERSION"],
    ["hash", "殼雜湊 SHELL_HASH"],
    ["mp", "MicroPython（WebAssembly 套件）"],
    ["shell", "殼顯示 shell"],
    ["py", "Python 就緒 py-ready"],
    ["worker", "Worker 內載入"],
  ]) {
    const dd = el("dd", { id: `s-about-${key}` });
    dl.append(el("dt", {}, label), dd);
    rows[key] = dd;
  }

  container.replaceChildren(form, preview, about);

  // ---- 狀態
  function syncControls() {
    const s = settingsStore.get();
    for (const [id, c] of Object.entries(controls)) c.value = toText(s[id]);
    const p = TAX_PRESETS[s.taxPreset];
    taxSource.replaceChildren();
    taxSource.hidden = !p;
    if (p) {
      const a = el("a", { href: p.source_url, target: "_blank", rel: "noopener noreferrer" }, "官方出處");
      taxSource.append(`${s.taxPreset}：${p.rate}%（查證日 ${p.checked}）。`, a);
    }
  }

  let gen = 0;
  async function renderPreview() {
    const my = ++gen;
    const s = settingsStore.get();
    pvDate.textContent = `日期：${formatDate(...SAMPLE_DATE, s.dateFmt)}`;
    let text;
    try {
      const r = await callEngine({
        sheet: "calc", action: "eval", inputs: { EXPR: String(SAMPLE_NUMBER) }, settings: settingsStore.toEngine(s),
      });
      text = r.ok === true ? r.display.value : "（引擎無法格式化）";
    } catch (e) {
      text = "（引擎尚未就緒）";
    }
    if (my === gen && container.isConnected) pvNumber.textContent = `數字：${text}`;
  }

  function apply(patch) {
    const { errors } = settingsStore.commit(patch);
    const bad = Object.values(errors);
    message.hidden = bad.length === 0;
    message.textContent = bad.join("；");
    status.replaceChildren(el("p", { class: "result-line" }, "已套用（只存在這台裝置）"));
    syncControls();
    renderPreview();
  }

  // 其他地方（例：頁首的小數位數選單）改了設定時同步顯示
  const onChange = () => {
    if (!container.isConnected) {
      document.removeEventListener("bacalc-settings", onChange);
      return;
    }
    syncControls();
    renderPreview();
  };
  document.addEventListener("bacalc-settings", onChange);

  syncControls();
  renderPreview();

  // ---- 關於（啟動計時可能還沒就緒：每 0.5 秒更新直到 py-ready，最多 1 分鐘）
  const about_ = ctx.about || {};
  const t = about_.timings || {};
  const ms = (v) => (v === null || v === undefined ? "—" : `${v} ms`);
  const renderTimings = () => {
    rows.shell.textContent = ms(t.shell);
    rows.py.textContent = ms(t.pyReady);
    rows.worker.textContent = ms(t.workerMs);
  };
  rows.version.textContent = about_.appVersion ? `v${about_.appVersion}` : "—";
  rows.hash.textContent = "讀取中…";
  rows.mp.textContent = "讀取中…";
  renderTimings();
  let ticks = 0;
  const timer = setInterval(() => {
    renderTimings();
    ticks += 1;
    if ((t.pyReady !== null && t.pyReady !== undefined) || ticks > 120 || !container.isConnected) clearInterval(timer);
  }, 500);

  fetchText(new URL("sw.js", document.baseURI)).then((text) => {
    const info = parseSwInfo(text);
    rows.hash.textContent = info ? `${info.shellHash}（快取 ${info.cacheVersion}）` : "讀取失敗";
  }).catch(() => { rows.hash.textContent = "讀取失敗"; });
  fetchText(new URL("py/manifest.json", document.baseURI)).then((text) => {
    const v = JSON.parse(text).vendor;
    rows.mp.textContent = v ? `micropython-webassembly-pyscript ${v}` : "讀取失敗";
  }).catch(() => { rows.mp.textContent = "讀取失敗"; });
}
