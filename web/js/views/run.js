// View 共用：執行引擎動作並維持「絕不讓舊結果看起來像目前結果」。
// - runEngineAction：讀輸入 → 格式錯誤標紅 → 呼叫引擎 → 顯示結果；失敗或格式錯誤時把輸出清掉、
//   已求出的輸入欄位標為過期（stale）。
// - watchStale：使用者改了任何輸入，就清掉輸出欄位與結果列、把已求出的欄位標為過期；
//   下一次成功計算才解除。專屬畫面（tvm.js、amort.js …）都經由這裡，不各自重寫。
import { callEngine } from "../py-client.js";
import { SHEETS, staleBlock, staleAfterSuccess } from "../sheets.js";
import * as settingsStore from "../settings.js";
import { createGuard } from "../generation.js";
import { readInputs, showErrors, showResult, setBusy, showFormMessage, getOnAction } from "./form.js";

const guard = createGuard(); // 世代：輸入改變或結果失效就 bump，進行中的請求回來時檢查
const lastOk = new Map(); // sheetId -> {form, actionId}：目前畫面上仍有效的最後一次成功計算
const STALE_TITLE = "這是舊的計算結果，輸入已改變，請按計算重新求出";

function formOf(sheetId) {
  return document.querySelector(`form.sheet-form[data-sheet="${CSS.escape(sheetId)}"]`);
}

/** 目前標為過期的欄位 id。 */
function staleIds(form) {
  return form ? [...form.querySelectorAll(".field.stale")].map((w) => w.dataset.field) : [];
}

/**
 * 解除過期標記（成功計算後呼叫）。onlyIds 指定時只解除這些欄位（這次回應求出／填入的），
 * 其餘過期欄位保持過期（例：STAT 預測成功不代表 a、b 已依新模型重算）；省略時全部解除。
 */
export function clearStale(sheetId, onlyIds = null) {
  const form = formOf(sheetId);
  if (!form) return;
  const keep = new Set(onlyIds ? staleAfterSuccess(staleIds(form), onlyIds) : []);
  for (const wrap of form.querySelectorAll(".field.stale")) {
    if (keep.has(wrap.dataset.field)) continue;
    wrap.classList.remove("stale");
    wrap.querySelector(".control")?.removeAttribute("title");
  }
}

/**
 * 讓目前顯示的結果失效：輸出欄位清空、結果列（已求出／警告）移除、
 * 已求出的輸入欄位標為過期（仍保留，讓再按計算時可重新求解）。
 * exceptWrap：剛被使用者編輯的欄位（不標過期）。
 */
export function markStale(sheetId, exceptWrap = null) {
  guard.bump(sheetId);
  lastOk.delete(sheetId);
  const form = formOf(sheetId);
  if (!form) return;
  for (const wrap of form.querySelectorAll(".field")) {
    const ctrl = wrap.querySelector(".control");
    if (wrap.classList.contains("output")) {
      ctrl.value = "";
    } else if (wrap.classList.contains("solved") && wrap !== exceptWrap) {
      wrap.classList.add("stale");
      ctrl.title = STALE_TITLE;
    }
  }
  form.querySelector(".form-status")?.replaceChildren();
}

/**
 * 監看表單編輯：任何輸入、選單、方向鈕變動都呼叫 markStale。
 * onStale(event) 讓專屬畫面清除自己的額外輸出（例：攤還表）。
 */
export function watchStale(sheetId, onStale) {
  const form = formOf(sheetId);
  if (!form) return;
  const handler = (e) => {
    const wrap = e.target.closest?.(".field") || null;
    if (!wrap && !form.contains(e.target)) return;
    if (e.type === "click" && !e.target.closest(".dir")) return;
    markStale(sheetId, wrap);
    onStale?.(e);
  };
  form.addEventListener("input", handler);
  form.addEventListener("change", handler);
  form.addEventListener("click", handler);
  form.addEventListener("form-reset", (e) => { // 清除鈕／Esc：等同編輯
    markStale(sheetId);
    onStale?.(e);
  });
}

/** 目前世代 token（給需要自行檢查的畫面，例：攤還 CSV 的第二次請求）。 */
export function generation(sheetId) {
  return guard.get(sheetId);
}

/** token 是否仍是目前世代。 */
export function isGeneration(sheetId, token) {
  return guard.isCurrent(sheetId, token);
}

/**
 * 執行工作表動作。回傳 {response, shown}；格式錯誤或被取代（isCurrent 為 false）時回傳 null。
 * opts.isCurrent：回應到達時仍為最新請求才套用（避免舊回應蓋掉新結果）。
 * opts.live：即時換算用，不停用按鈕，並把焦點還給原本的欄位（錯誤標示不搶焦點）。
 * 專屬畫面有表格（CF、STAT）時另有三個掛鉤：
 *   opts.extra()            讀表格，回傳 {inputs?: {引擎鍵: 值}, error?: {message, ...}}；
 *                           inputs 併入送出的輸入，error 會中止計算（與欄位格式錯誤同樣處理）
 *   opts.onExtraError(err)  表格讀取錯誤時通知畫面標出出錯的格子
 *   opts.mapError(response) 引擎失敗時先讓畫面認領錯誤（例：field 指向表格而非某個欄位）；
 *                           回傳要顯示的 response（例：field 改為 null 變成表單層級訊息）
 */
export async function runEngineAction(sheetId, actionId, opts = {}) {
  const { isCurrent = () => true, live = false, onFail, extra, onExtraError, mapError } = opts;
  const sheet = SHEETS[sheetId];
  const active = live ? document.activeElement : null;
  const restore = () => {
    if (active && active.isConnected && document.activeElement !== active) active.focus();
  };
  // 要用到的係數是過期的（例：STAT 預測的 a、b）：不送出，不讓舊係數算出看似正常的數字
  const blocked = staleBlock(sheetId, actionId, staleIds(formOf(sheetId)));
  if (blocked) {
    showErrors(sheetId, {});
    showFormMessage(sheetId, blocked.message);
    onFail?.();
    restore();
    return null;
  }
  const { inputs, errors } = readInputs(sheetId, actionId);
  const more = extra ? extra() : null;
  const extraError = more && more.error ? more.error : null;
  if (Object.keys(errors).length || extraError) {
    markStale(sheetId);
    showErrors(sheetId, errors);
    if (extraError) {
      const n = Object.keys(errors).length;
      showFormMessage(sheetId, n ? `${extraError.message}（另有 ${n} 個欄位格式不正確，請修正紅色欄位）` : extraError.message);
      onExtraError?.(extraError);
    }
    onFail?.();
    restore();
    return null;
  }
  Object.assign(inputs, more && more.inputs);
  const token = guard.get(sheetId);
  if (!live) setBusy(sheetId, true);
  let response;
  try {
    response = await callEngine({
      sheet: sheet.engine, action: actionId, inputs, settings: settingsStore.toEngine(),
    });
  } catch (e) {
    response = { ok: false, error: (e && e.message) || String(e), field: null };
  } finally {
    if (!live) setBusy(sheetId, false);
  }
  if (!isCurrent() || !guard.isCurrent(sheetId, token)) return null; // 請求期間輸入已改：丟棄舊回應
  const toShow = response.ok !== true && mapError ? (mapError(response) || response) : response;
  const shown = showResult(toShow, sheetId, actionId);
  if (response.ok === true) {
    clearStale(sheetId, shown.filled); // 只解除這次求出／填入的欄位
    lastOk.set(sheetId, { form: formOf(sheetId), actionId });
  }
  if (response.ok !== true) {
    markStale(sheetId);
    onFail?.();
  }
  restore();
  return { response, shown, inputs };
}

/**
 * 設定（小數位數、千分位）改變後，重新執行每張工作表「目前仍有效」的最後一次計算，
 * 讓畫面上的結果用新格式重新顯示（由引擎格式化，JS 不自己改字串）。
 * 已被編輯或失敗而失效的結果不會重算；表單已被換掉（換頁）的紀錄一律忽略。
 */
export async function refreshAfterSettings() {
  for (const [sheetId, rec] of [...lastOk]) {
    if (!rec.form || !rec.form.isConnected || rec.form !== formOf(sheetId)) {
      lastOk.delete(sheetId);
      continue;
    }
    const onAction = getOnAction(sheetId);
    if (onAction) await onAction(rec.actionId);
  }
}

if (typeof document !== "undefined") {
  document.addEventListener("bacalc-settings", () => { refreshAfterSettings(); });
}
