// View：ICONV 利率換算。即時雙向換算：改 NOM 就更新 EFF，改 EFF 就更新 NOM（防抖 250 ms）；
// 改 C/Y 則依「最後編輯的那一格」重算。程式填值不會觸發 input 事件，所以不會互相呼叫造成迴圈。
// 每次編輯都讓進行中的舊請求失效（seq），避免舊回應蓋掉新結果。
import { renderForm, setValues } from "./form.js";
import { runEngineAction, watchStale } from "./run.js";
import { debounce } from "../util.js";

const SHEET = "iconv";
const DELAY_MS = 250;
const LIVE = {
  NOM: { action: "to_eff", target: "EFF" },
  EFF: { action: "to_nom", target: "NOM" },
};

export function mount(container) {
  let seq = 0;
  let source = "NOM"; // 最後編輯的來源欄位

  const form = renderForm(SHEET, container, {
    onAction: (actionId) => {
      const my = ++seq;
      return runEngineAction(SHEET, actionId, { isCurrent: () => my === seq });
    },
  });
  watchStale(SHEET);

  const live = debounce(async () => {
    if (!form.isConnected) return; // 畫面已換掉（teardown）：不再送請求
    const { action, target } = LIVE[source];
    const input = form.querySelector(`#f-${SHEET}-${source}`);
    setValues(SHEET, { [target]: "" }); // 目標欄位交給引擎填（不是使用者值）
    if (input.value.trim() === "") { // 來源空白：只清掉目標（連同綠色／過期標記）
      form.querySelector(`.field[data-field="${target}"]`)?.classList.remove("solved", "stale");
      return;
    }
    const my = ++seq;
    await runEngineAction(SHEET, action, { live: true, isCurrent: () => my === seq });
  }, DELAY_MS);

  form.addEventListener("input", (e) => {
    const id = e.target.dataset?.field;
    if (!(id in LIVE) && id !== "CY") return;
    if (id in LIVE) source = id;
    seq += 1; // 舊的進行中請求作廢
    live();
  });
}
