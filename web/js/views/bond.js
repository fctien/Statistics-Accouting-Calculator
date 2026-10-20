// View：BOND 債券。交割日 SDT／到期日 RDT 用 <input type="date">，解析重用 input.js 的 parseDate
// （通用表單的 date 欄位已經如此處理，不使用 new Date()）。
// 殖利率 YLD 與價格 PRI「留一格空白」：留空的那格就是要求的；按「計算」（或 Enter）自動選擇
// 求價格（price）或求殖利率（yield）。兩格都填、都空時說明原因。求出的格子變綠色，
// 改了其他輸入再按計算會重新求它（沿用通用表單的重新求解規則）。
import { renderForm, showResult } from "./form.js";
import { runEngineAction, watchStale } from "./run.js";

const SHEET = "bond";

const q = (form, id) => form.querySelector(`.field[data-field="${id}"]`);
const filled = (wrap) => wrap.querySelector(".control").value.trim() !== "";
const engineValue = (wrap) => wrap.classList.contains("solved"); // 上次由引擎求出（含過期）

/** 依 YLD、PRI 哪一格空白決定動作；回傳動作 id 或 {error}。 */
export function chooseAction(form) {
  const yld = q(form, "YLD");
  const pri = q(form, "PRI");
  const hasY = filled(yld);
  const hasP = filled(pri);
  if (hasY && !hasP) return "price";
  if (hasP && !hasY) return "yield";
  if (hasY && hasP) {
    // 兩格都有值：若其中一格是上次引擎求出的，改別的輸入後重新求它
    if (engineValue(pri) && !engineValue(yld)) return "price";
    if (engineValue(yld) && !engineValue(pri)) return "yield";
    return { error: "殖利率 YLD 與價格 PRI 請只留一格空白，留空的那格會被求出來" };
  }
  return { error: "請填入殖利率 YLD（求價格）或價格 PRI（求殖利率）其中一格，另一格留空" };
}

export function mount(container) {
  const formBox = document.createElement("div");
  container.replaceChildren(formBox);
  const form = renderForm(SHEET, formBox, {
    onAction: () => {
      const act = chooseAction(form);
      if (typeof act !== "string") {
        showResult({ ok: false, error: act.error, field: null }, SHEET, "price");
        return undefined;
      }
      return runEngineAction(SHEET, act);
    },
  });
  // 兩個固定動作鈕換成一顆「計算」：由空白的那格決定算什麼
  const actions = form.querySelector(".actions");
  for (const b of actions.querySelectorAll("button[data-action]")) b.remove();
  const calc = document.createElement("button");
  calc.type = "submit";
  calc.className = "btn btn-primary";
  calc.dataset.action = "solve";
  calc.id = "bond-calc";
  calc.textContent = "計算";
  calc.title = "留空殖利率就求價格，留空價格就求殖利率（Enter）";
  actions.prepend(calc);
  watchStale(SHEET);
}
