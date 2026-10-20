// View：DATE 日期。通用表單：日期欄位是 <input type="date">（input.js 轉成 [年, 月, 日]），
// 星期標籤由引擎回傳（weekday1／weekday2），改任何輸入就清掉舊的星期與天數結果。
import { renderForm } from "./form.js";
import { runEngineAction, watchStale } from "./run.js";

const SHEET = "date";

export function mount(container) {
  renderForm(SHEET, container, {
    onAction: (actionId) => runEngineAction(SHEET, actionId),
  });
  watchStale(SHEET);
}
