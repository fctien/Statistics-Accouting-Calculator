// View：TVM 貨幣時間價值。通用表單（form.js）＋「帶入攤還」按鈕：
// 把目前 TVM 輸入（N、I/Y、PV、PMT、FV、P/Y、C/Y、BGN）原樣（含完整精度）搬到 AMORT。
import { renderForm, getFieldState, showInfo } from "./form.js";
import { runEngineAction, watchStale } from "./run.js";

const SHEET = "tvm";
const HANDOFF = ["N", "IY", "PV", "PMT", "FV", "PY", "CY", "BGN"];

function showHandoffError(form, text) {
  const msg = form.querySelector(".form-message");
  msg.textContent = text;
  msg.hidden = false;
}

/**
 * 掛載 TVM 畫面。ctx.openSheet(sheetId, prefill) 由 Controller（app.js）提供，負責切換工作表。
 */
export function mount(container, ctx = {}) {
  const form = renderForm(SHEET, container, {
    onAction: (actionId) => runEngineAction(SHEET, actionId),
  });
  watchStale(SHEET);
  const btn = document.createElement("button");
  btn.type = "button";
  btn.id = "tvm-to-amort";
  btn.className = "btn";
  btn.textContent = "帶入攤還";
  btn.title = "把目前的 N、I/Y、PV、PMT、FV、P/Y、C/Y、BGN 帶到「攤還 AMORT」";
  btn.addEventListener("click", () => {
    const state = Object.fromEntries(HANDOFF.map((id) => [id, getFieldState(SHEET, id)]));
    const pmt = state.PMT;
    if (!pmt || pmt.text.trim() === "") {
      showHandoffError(form, "請先求出或輸入每期付款 PMT，再帶入攤還");
      return;
    }
    const stale = HANDOFF.filter((id) => state[id]?.stale);
    if (stale.length) {
      showHandoffError(form, `${stale.join("、")} 是舊的計算結果，請先按「計算」重新求出再帶入攤還`);
      return;
    }
    showInfo(SHEET, "已帶入攤還");
    ctx.openSheet?.("amort", state);
  });
  form.querySelector(".actions").append(btn);
}
