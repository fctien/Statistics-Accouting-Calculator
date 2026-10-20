// View：設定 FORMAT。小數位數、千分位、日期格式、運算順序、外觀、稅率預設值；選了就立即生效並儲存
// （settingsStore.commit 會通知畫面重新顯示結果），下方「即時預覽」由引擎格式化。
// 「資料」區：匯出／匯入 JSON 備份（合併或取代，取代前 confirm）、清除全部資料。
// 「Google Drive 同步」區（選用，預設關閉）：Client ID、連結、上傳、下載（合併／取代）、衝突詢問、中斷連結。
// 「關於」區：APP 版本、SHELL_HASH（讀 sw.js 文字）、MicroPython 套件版本（讀 py/manifest.json）、啟動計時。
import { SHEETS, TAX_PRESETS } from "../sheets.js";
import { callEngine } from "../py-client.js";
import * as settingsStore from "../settings.js";
import { formatDate } from "../datefmt.js";
import { download } from "../csv.js";
import * as persist from "../storage/persist.js";
import { makeExport, importBackup, backupFilename, emptyData, localStamp } from "../storage/backup.js";
import { replaceState } from "./calc.js";
import * as gdrive from "../storage/gdrive.js";

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

  // ---- 資料（備份）
  const data = el("section", { class: "settings-data", "aria-labelledby": "s-data-title" });
  data.append(el("h3", { id: "s-data-title" }, "資料 Data"));
  data.append(el("p", { class: "calc-note" },
    "所有資料只存在這台裝置的瀏覽器（IndexedDB）。匯出的 JSON 檔可存到任何雲端資料夾，在另一台裝置匯入。"));
  const exportBtn = el("button", { type: "button", id: "data-export", class: "btn", title: "下載 bacalc-backup-日期.json" }, "匯出 JSON");
  const fileInput = el("input", { type: "file", id: "data-file", accept: ".json,application/json", "aria-label": "選擇備份檔" });
  const modeRow = el("div", { class: "data-mode", role: "radiogroup", "aria-label": "匯入方式" });
  for (const [value, label, checked] of [["merge", "合併", true], ["replace", "取代", false]]) {
    const lab = el("label");
    lab.append(el("input", { type: "radio", name: "data-mode", value, id: `data-mode-${value}`, checked }), ` ${label} `);
    modeRow.append(lab);
  }
  const importBtn = el("button", { type: "button", id: "data-import", class: "btn" }, "匯入 JSON");
  const clearBtn = el("button", { type: "button", id: "data-clear", class: "btn btn-ghost", title: "刪除這台裝置上的情境、紙帶、記憶並還原預設設定" }, "清除所有資料");
  const dataError = el("div", { id: "data-error", class: "form-message", role: "alert", hidden: true });
  const dataStatus = el("p", { id: "data-status", class: "result-line", role: "status", "aria-live": "polite" });
  const row1 = el("div", { class: "scenario-row" });
  row1.append(exportBtn, clearBtn);
  const row2 = el("div", { class: "scenario-row" });
  row2.append(fileInput, modeRow, importBtn);
  data.append(row1, row2, dataError, dataStatus);

  const showDataError = (text) => {
    dataError.textContent = text;
    dataError.hidden = !text;
    if (text) dataStatus.textContent = "";
  };
  const showDataOk = (text) => {
    showDataError("");
    dataStatus.textContent = text;
  };

  /** 目前本機的整份資料（設定用記憶體中的完整設定，含預設值）。 */
  async function localData() {
    const d = { ...emptyData(), ...(await persist.readAll()) };
    d.settings = settingsStore.get();
    return d;
  }

  /** 把整份資料寫進 IndexedDB 並更新目前畫面用的記憶體狀態。 */
  async function applyData(d) {
    await persist.writeAll(d);
    settingsStore.replace(d.settings);
    replaceState(d.tape, d.memory);
    document.dispatchEvent(new Event("bacalc-data-changed"));
  }

  exportBtn.addEventListener("click", async () => {
    try {
      const d = await localData();
      const out = makeExport(d, Date.now());
      download(backupFilename(), JSON.stringify(out, null, 2), "application/json;charset=utf-8");
      showDataOk(`已匯出：情境 ${d.scenarios.length} 個、紙帶 ${d.tape.length} 筆`);
    } catch (e) {
      showDataError("匯出失敗：" + ((e && e.message) || e));
    }
  });

  importBtn.addEventListener("click", async () => {
    const file = fileInput.files && fileInput.files[0];
    if (!file) {
      showDataError("請先選擇要匯入的 JSON 備份檔");
      return;
    }
    const mode = data.querySelector('input[name="data-mode"]:checked').value;
    let obj;
    try {
      obj = JSON.parse(await file.text());
    } catch (e) {
      showDataError("不是有效的 JSON 檔：" + ((e && e.message) || e));
      return;
    }
    try {
      const r = importBackup(obj, await localData(), mode);
      if (!r.ok) {
        showDataError("無法匯入：" + r.error);
        return;
      }
      const c = r.counts;
      const summary = `情境 ${c.scenarios} 個、紙帶 ${c.tape} 筆、設定 ${c.settings} 項、記憶 ${c.memory} 格`;
      if (mode === "replace"
          && !globalThis.confirm(`取代會刪除這台裝置目前的全部資料，改成備份檔的內容（${summary}）。確定要取代嗎？`)) {
        showDataOk("已取消，資料沒有改變");
        return;
      }
      await applyData(r.data);
      showDataOk(`已匯入（${mode === "merge" ? "合併" : "取代"}）：${summary}`);
    } catch (e) {
      showDataError("匯入失敗：" + ((e && e.message) || e));
    }
  });

  clearBtn.addEventListener("click", async () => {
    if (!globalThis.confirm("要刪除這台裝置上的全部情境、紙帶、記憶，並還原預設設定嗎？刪除後無法復原（建議先匯出備份）。")) return;
    try {
      await applyData({ ...emptyData(), settings: {} });
      showDataOk("已清除全部資料");
    } catch (e) {
      showDataError("清除失敗：" + ((e && e.message) || e));
    }
  });

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

  container.replaceChildren(form, preview, data, about);

  // ---- Google Drive 同步（選用）
  const gd = el("section", { class: "settings-gdrive", "aria-labelledby": "s-gd-title" });
  gd.append(el("h3", { id: "s-gd-title" }, "Google Drive 同步（選用）"));
  gd.append(el("p", { class: "calc-note" },
    "預設關閉：沒有設定 Client ID 並按下按鈕之前，不會連到 Google。只使用 App 專屬的隱藏資料夾（drive.appdata），看不到你其他的檔案。"));
  const gdHelp = el("a", { href: "https://github.com/fctien/Statistics-Accouting-Calculator/blob/main/docs/google-oauth-setup.md", target: "_blank", rel: "noopener noreferrer" }, "如何申請 Client ID");
  const gdHelpP = el("p", { class: "calc-note" });
  gdHelpP.append(gdHelp);
  const gdInput = el("input", {
    type: "text", id: "gd-client-id", class: "control", autocomplete: "off", spellcheck: "false",
    placeholder: "xxxx.apps.googleusercontent.com", "aria-label": "Google OAuth Client ID",
  });
  const gdSave = el("button", { type: "button", id: "gd-save", class: "btn" }, "儲存");
  const gdConnect = el("button", { type: "button", id: "gd-connect", class: "btn" }, "連結 Google Drive");
  const gdUp = el("button", { type: "button", id: "gd-upload", class: "btn" }, "上傳到雲端");
  const gdDown = el("button", { type: "button", id: "gd-download", class: "btn" }, "從雲端下載");
  const gdOff = el("button", { type: "button", id: "gd-disconnect", class: "btn btn-ghost" }, "中斷連結");
  const gdModeRow = el("div", { class: "data-mode", role: "radiogroup", "aria-label": "下載方式" });
  for (const [value, label, checked] of [["merge", "合併", true], ["replace", "取代", false]]) {
    const lab = el("label");
    lab.append(el("input", { type: "radio", name: "gd-mode", value, id: `gd-mode-${value}`, checked }), ` ${label} `);
    gdModeRow.append(lab);
  }
  const gdConflict = el("div", { id: "gd-conflict", class: "form-message", role: "alertdialog", "aria-label": "雲端與本機版本不同", hidden: true });
  const gdError = el("div", { id: "gd-error", class: "form-message", role: "alert", hidden: true });
  const gdStatus = el("p", { id: "gd-status", class: "result-line", role: "status", "aria-live": "polite" });
  const gdRow0 = el("div", { class: "scenario-row" });
  gdRow0.append(gdInput, gdSave);
  const gdRow1 = el("div", { class: "scenario-row" });
  gdRow1.append(gdConnect, gdOff);
  const gdRow2 = el("div", { class: "scenario-row" });
  gdRow2.append(gdUp, gdDown, gdModeRow);
  gd.append(gdHelpP, gdRow0, gdRow1, gdRow2, gdConflict, gdError, gdStatus);
  data.after(gd);

  const showGdError = (text) => {
    gdError.textContent = text;
    gdError.hidden = !text;
    if (text) gdStatus.textContent = "";
  };
  const showGdOk = (text) => {
    showGdError("");
    gdStatus.textContent = text;
  };
  const stamp = (iso) => (iso && Number.isFinite(Date.parse(iso)) ? localStamp(Date.parse(iso)) : "（無）");
  const gdModeValue = () => gd.querySelector('input[name="gd-mode"]:checked').value;

  function syncGd() {
    const s = settingsStore.get();
    const hasId = gdrive.isValidClientId(s.gdriveClientId);
    const offline = globalThis.navigator && globalThis.navigator.onLine === false;
    if (document.activeElement !== gdInput) gdInput.value = s.gdriveClientId;
    gdConnect.disabled = !hasId || offline;
    gdConnect.title = offline ? "目前離線，無法連結 Google Drive" : hasId ? "載入 Google 登入程式庫並授權" : "請先輸入並儲存 Client ID";
    gdUp.disabled = !hasId || offline;
    gdDown.disabled = !hasId || offline;
    gdOff.disabled = !gdrive.isConnected();
    if (offline && !gdStatus.textContent && gdError.hidden) gdStatus.textContent = "目前離線：Google Drive 同步暫時無法使用（其他功能照常）";
  }

  async function doUpload() {
    gdConflict.hidden = true;
    const d = gdrive.stripLocalOnly(await localData());
    const r = await gdrive.upload(JSON.stringify(makeExport(d, Date.now()), null, 2));
    settingsStore.commit({ gdriveLastSync: r.modifiedTime || "" });
    showGdOk(`已上傳到雲端（情境 ${d.scenarios.length} 個、紙帶 ${d.tape.length} 筆），雲端時間 ${stamp(r.modifiedTime)}`);
  }

  async function doDownload() {
    gdConflict.hidden = true;
    const got = await gdrive.download();
    if (!got) {
      showGdOk("雲端還沒有備份檔");
      return;
    }
    let obj;
    try {
      obj = JSON.parse(got.text);
    } catch (e) {
      showGdError("雲端的備份檔不是有效的 JSON，本機資料沒有改變");
      return;
    }
    const mode = gdModeValue();
    const local = await localData();
    // 先驗證、清理、合併，全部通過才寫入本機（不留下寫一半的狀態）
    const r = importBackup(obj, gdrive.stripLocalOnly(local), mode);
    if (!r.ok) {
      showGdError("雲端備份無法匯入，本機資料沒有改變：" + r.error);
      return;
    }
    const c = r.counts;
    const summary = `情境 ${c.scenarios} 個、紙帶 ${c.tape} 筆、設定 ${c.settings} 項、記憶 ${c.memory} 格`;
    if (mode === "replace"
        && !globalThis.confirm(`取代會刪除這台裝置目前的全部資料，改成雲端備份的內容（${summary}）。確定要取代嗎？`)) {
      showGdOk("已取消，資料沒有改變");
      return;
    }
    const keep = { gdriveClientId: local.settings.gdriveClientId || "" };
    await applyData({ ...r.data, settings: { ...r.data.settings, ...keep } });
    settingsStore.commit({ gdriveLastSync: got.modifiedTime || "" });
    showGdOk(`已從雲端下載（${mode === "merge" ? "合併" : "取代"}）：${summary}`);
  }

  /** 顯示雙方時間，讓使用者選擇；不自動覆蓋。 */
  function askConflict(localIso, remoteIso, lastSync) {
    gdConflict.replaceChildren(
      el("p", {}, `雲端與本機版本不同。本機最後更新：${stamp(localIso)}；雲端最後修改：${stamp(remoteIso)}；上次同步：${stamp(lastSync)}。請選擇要保留哪一份：`),
    );
    const useCloud = el("button", { type: "button", class: "btn", id: "gd-use-cloud" }, "用雲端版本（下載）");
    const useLocal = el("button", { type: "button", class: "btn", id: "gd-use-local" }, "用本機版本（上傳覆蓋雲端）");
    const cancel = el("button", { type: "button", class: "btn btn-ghost", id: "gd-cancel" }, "取消");
    useCloud.addEventListener("click", () => guarded(doDownload));
    useLocal.addEventListener("click", () => guarded(doUpload));
    cancel.addEventListener("click", () => {
      gdConflict.hidden = true;
      showGdOk("已取消，資料沒有改變");
    });
    const r = el("div", { class: "scenario-row" });
    r.append(useCloud, useLocal, cancel);
    gdConflict.append(r);
    gdConflict.hidden = false;
    showGdError("");
    gdStatus.textContent = "";
  }

  /** 執行同步動作：先確保已連結（須在使用者點擊中，授權視窗才不會被擋），統一處理錯誤與按鈕狀態。 */
  async function guarded(fn) {
    for (const b of [gdConnect, gdUp, gdDown]) b.disabled = true;
    try {
      if (!gdrive.isConnected()) await gdrive.connect(settingsStore.get().gdriveClientId);
      await fn();
    } catch (e) {
      showGdError((e && e.message) || String(e));
    } finally {
      syncGd();
    }
  }

  async function decideAndRun(kind) {
    const local = await localData();
    const info = await gdrive.find();
    const lastSync = settingsStore.get().gdriveLastSync || null;
    const localIso = gdrive.localUpdatedAt(local);
    const remoteIso = info ? info.modifiedTime : null;
    if (kind === "download" && !info) {
      showGdOk("雲端還沒有備份檔");
      return;
    }
    const decision = gdrive.decideConflict(localIso, remoteIso, lastSync);
    if (decision === "ask" || (kind === "upload" && decision === "download")) {
      askConflict(localIso, remoteIso, lastSync);
      return;
    }
    await (kind === "upload" ? doUpload() : doDownload());
  }

  gdSave.addEventListener("click", () => {
    const v = gdInput.value.trim();
    if (v !== "" && !gdrive.isValidClientId(v)) {
      showGdError("Client ID 格式不正確：應以 .apps.googleusercontent.com 結尾");
      return;
    }
    const cur = settingsStore.get();
    settingsStore.commit({ gdriveClientId: v, gdriveLastSync: v === cur.gdriveClientId ? cur.gdriveLastSync : "" });
    showGdOk(v ? "已儲存 Client ID（只存在這台裝置）" : "已清除 Client ID，Google Drive 同步已關閉");
    syncGd();
  });
  gdConnect.addEventListener("click", () => guarded(async () => {
    showGdOk("已連結 Google Drive（權杖只放在記憶體，關閉頁面即失效）");
  }));
  gdUp.addEventListener("click", () => guarded(() => decideAndRun("upload")));
  gdDown.addEventListener("click", () => guarded(() => decideAndRun("download")));
  gdOff.addEventListener("click", async () => {
    gdOff.disabled = true;
    await gdrive.disconnect();
    gdConflict.hidden = true;
    showGdOk("已中斷連結，並向 Google 撤銷這次的授權");
    syncGd();
  });
  const onGdEvent = () => {
    if (!container.isConnected) {
      document.removeEventListener("bacalc-settings", onGdEvent);
      globalThis.removeEventListener?.("online", onGdEvent);
      globalThis.removeEventListener?.("offline", onGdEvent);
      return;
    }
    syncGd();
  };
  document.addEventListener("bacalc-settings", onGdEvent);
  globalThis.addEventListener?.("online", onGdEvent);
  globalThis.addEventListener?.("offline", onGdEvent);
  syncGd();


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
