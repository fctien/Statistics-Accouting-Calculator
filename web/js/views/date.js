// View：DATE 日期。通用表單：日期欄位是 <input type="date">（input.js 轉成 [年, 月, 日]），
// 星期標籤由引擎回傳（weekday1／weekday2），改任何輸入就清掉舊的星期與天數結果。
// 日期欄位旁依設定顯示美式／歐式格式（datereadout.js）。
import { renderForm } from "./form.js";
import { runEngineAction, watchStale } from "./run.js";
import { attachDateReadouts } from "./datereadout.js";

const SHEET = "date";

export function mount(container) {
  let refresh = () => {};
  const form = renderForm(SHEET, container, {
    onAction: async (actionId) => {
      const res = await runEngineAction(SHEET, actionId);
      refresh(); // 引擎求出的日期是程式填入的，不會觸發 input 事件
      return res;
    },
  });
  watchStale(SHEET);
  refresh = attachDateReadouts(form);
}
