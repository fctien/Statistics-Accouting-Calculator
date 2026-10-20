// View：日期欄位旁的「顯示格式」讀數。<input type="date"> 的輸入畫面由瀏覽器決定，
// 這裡在每個日期欄位旁加一行小字，依設定（美式 mm/dd/yyyy 或歐式 dd.mm.yyyy）顯示同一個日期。
// 只影響顯示；送給引擎的仍是 [年, 月, 日]。
import * as settingsStore from "../settings.js";
import { formatIso } from "../datefmt.js";

/** 為表單內的日期欄位加讀數；回傳 refresh()（程式填值、設定改變後呼叫）。 */
export function attachDateReadouts(form) {
  const items = [];
  for (const ctrl of form.querySelectorAll('input[type="date"]')) {
    const span = document.createElement("span");
    span.className = "date-readout";
    span.setAttribute("aria-live", "polite");
    ctrl.closest(".field").append(span);
    items.push({ ctrl, span });
  }
  const refresh = () => {
    const fmt = settingsStore.get().dateFmt;
    for (const { ctrl, span } of items) {
      const text = formatIso(ctrl.value, fmt);
      span.textContent = text ? `顯示為 ${text}（${fmt === "eu" ? "dd.mm.yyyy" : "mm/dd/yyyy"}）` : "";
    }
  };
  form.addEventListener("input", refresh);
  form.addEventListener("change", refresh);
  form.addEventListener("form-reset", refresh);
  document.addEventListener("bacalc-settings", () => { if (form.isConnected) refresh(); });
  refresh();
  return refresh;
}
