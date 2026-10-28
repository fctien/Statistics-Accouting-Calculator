// View：機率分配（統計頁 #stat/dist）。分配選單（常態、t、卡方、二項、Poisson）→ 依分配顯示參數欄位
// → 功能（pdf／pmf、cdf、inv）。結果：
//   - 標籤明確區分機率（cdf：左尾、右尾、雙尾）與臨界值（inv）
//   - 機率類數值另以浮動小數位數向引擎取格式（不被 2 位小數吃掉，極小值為科學記號）
//   - 分配圖：以引擎算出的 pdf／pmf 點畫曲線或長條（≤ 100 點），陰影標示 cdf 的左尾區域
//   - 非整數自由度：提醒 Excel 會把 df 截成整數
// 所有請求都經 generation guard（run.js）；圖與浮動格式的後續請求另以序號丟棄過期回應。
import { callEngine } from "../py-client.js";
import * as settingsStore from "../settings.js";
import {
  DISTS, distFields, prepareDist, distRows, dfNote, rangeProbs, chartRange, chartXs, discreteRange,
  pointRequest, invRequest, CHART_POINTS,
} from "../stat.js";
import { renderForm } from "./form.js";
import { runEngineAction, watchStale, generation, isGeneration } from "./run.js";
import { el, ctrl, showOnly, onlyPrimaryButton, fetchFloat, resultList, chartFigure, statusBox } from "./statui.js";

const SHEET = "dist";

export function mount(container) {
  const box = document.createElement("div");
  container.replaceChildren(box);
  let seq = 0;

  const form = renderForm(SHEET, box, { onAction: () => run() });
  onlyPrimaryButton(form);
  const distSel = ctrl(form, SHEET, "DIST");
  const funcSel = ctrl(form, SHEET, "FUNC");
  const invOpt = funcSel.querySelector('option[value="inv"]');

  /** 依分配與功能顯示欄位；離散分配沒有 inv。 */
  function sync() {
    const d = DISTS[distSel.value];
    invOpt.disabled = d.discrete;
    if (d.discrete && funcSel.value === "inv") funcSel.value = "cdf";
    showOnly(form, distFields(distSel.value, funcSel.value));
  }

  form.addEventListener("change", (e) => {
    if (e.target === distSel || e.target === funcSel) sync();
  });
  form.addEventListener("form-reset", sync);
  watchStale(SHEET, () => { seq++; }); // 輸入改了：進行中的圖、浮動格式請求作廢
  sync();

  const alive = (my, token) => my === seq && isGeneration(SHEET, token) && form.isConnected;

  async function run() {
    const my = ++seq;
    const dist = distSel.value;
    const func = funcSel.value;
    const res = await runEngineAction(SHEET, dist, {
      prepare: (inputs, errors) => prepareDist(dist, func, inputs, errors),
      showValues: false, // 結果由下方清單顯示（標籤依功能而定）
    });
    if (!res || res.response.ok !== true || my !== seq) return;
    const token = generation(SHEET);
    const rows = distRows(dist, func);
    const needFloat = func !== "inv";
    const fl = needFloat ? await fetchFloat("dist", dist, res.inputs) : null;
    if (!alive(my, token)) return;
    const status = statusBox(form);
    status.append(el("h3", { class: "stat-head" }, `${DISTS[dist].label}：${func === "inv" ? "反查臨界值" : func === "cdf" ? "累積機率" : (DISTS[dist].discrete ? "機率 P(X = k)" : "機率密度")}`));
    status.append(resultList(rows, res.response.display, fl ? fl.display : null, "dist-result"));
    const note = dfNote(dist, res.inputs.DF);
    if (note) status.append(el("p", { class: "stat-note", id: "dist-df-note" }, note));
    const chartBox = el("div", { class: "stat-chart-box" }, "");
    chartBox.append(el("p", { class: "calc-note" }, "繪製分配圖中…"));
    status.append(chartBox);
    try {
      const fig = await buildChart(dist, func, res.inputs, res.response, () => alive(my, token));
      if (!alive(my, token)) return;
      chartBox.replaceChildren(fig || el("p", { class: "calc-note" }, "無法繪製分配圖（取樣點計算失敗）"));
    } catch (e) {
      if (alive(my, token)) chartBox.replaceChildren(el("p", { class: "calc-note" }, "無法繪製分配圖"));
    }
  }

  /** 以引擎算出的點畫圖；回傳 <figure> 或 null。 */
  async function buildChart(dist, func, inputs, resp, ok) {
    const d = DISTS[dist];
    const params = {};
    for (const p of d.params) params[p] = inputs[p];
    const settings = settingsStore.toEngine();
    const call = (req) => callEngine({ ...req, settings }).catch(() => null);
    const v = resp.values;
    if (d.discrete) {
      const ks = discreteRange(dist, params, inputs.K);
      const got = await Promise.all(ks.map((k) => call(pointRequest(dist, params, k))));
      if (!ok()) return null;
      const points = ks.map((k, i) => [k, got[i] && got[i].ok ? got[i].values.value : null]).filter((p) => p[1] !== null);
      if (points.length < 1) return null;
      return chartFigure({
        points, discrete: true,
        shadeTo: func === "cdf" ? inputs.K : null,
        hitK: inputs.K,
        caption: func === "cdf"
          ? `長條高度＝P(X = k)；著色長條（k ≤ ${inputs.K}，橘色為 k = ${inputs.K}）合計＝左尾機率 P(X ≤ ${inputs.K})`
          : `長條高度＝P(X = k)；標示的長條為 k = ${inputs.K}`,
      });
    }
    const [pl, ph] = rangeProbs(dist);
    const [rl, rh] = await Promise.all([call(invRequest(dist, params, pl)), call(invRequest(dist, params, ph))]);
    if (!ok() || !rl || !rh || !rl.ok || !rh.ok) return null;
    const mark = func === "inv" ? v.value : inputs.X;
    const range = chartRange(rl.values.value, rh.values.value, mark);
    const xs = chartXs(range.lo, range.hi, CHART_POINTS);
    const got = await Promise.all(xs.map((x) => call(pointRequest(dist, params, x))));
    if (!ok()) return null;
    const points = xs.map((x, i) => [x, got[i] && got[i].ok ? got[i].values.value : null]).filter((p) => p[1] !== null);
    if (points.length < 2) return null;
    const widened = range.lo !== rl.values.value || range.hi !== rh.values.value;
    return chartFigure({
      points, discrete: false,
      shadeTo: func === "pdf" ? null : mark,
      marker: range.outside ? null : mark,
      tickLabels: widened ? null : [rl.display.value, rh.display.value],
      caption: func === "pdf" ? "曲線為機率密度 f(x)；直線標示 x"
        : func === "cdf" ? "陰影面積＝左尾機率 P(X ≤ x)" : "陰影面積＝輸入的左尾機率 p；直線為左尾臨界值",
      outsideNote: range.outside ? "x 在圖的範圍外" : "",
    });
  }
}
