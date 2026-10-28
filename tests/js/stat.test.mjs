// stat.js 測試：統計頁（敘述統計、機率分配、信賴區間與檢定）的純函式。
// 請求組裝（每種分配／檢定）、標籤（機率 vs 臨界值）、結論句（H0／H1）、p 值格式請求、圖形幾何。
import test from "node:test";
import assert from "node:assert/strict";

import {
  DISTS, distFields, prepareDist, distRows, dfNote, floatSettings, floatKeys,
  INFER_TYPES, inferFields, prepareInfer, gridLayout, readInferGrid, hypotheses, inferRows,
  DESC_GROUPS, readDescribeTable, chartRange, discreteRange, chartXs, pointRequest, chartGeometry,
  withPoint, distHint,
} from "../../web/js/stat.js";
import { SHEETS, fieldMap } from "../../web/js/sheets.js";

// ---------------------------------------------------------------- 機率分配：請求組裝

test("常態 cdf：只送 FUNC、MU、SIGMA、X（PROB 等隱藏欄位不送、其錯誤忽略）", () => {
  const r = prepareDist("normal", "cdf",
    { FUNC: "cdf", MU: 0, SIGMA: 1, X: 1.96, PROB: null, DF: null, K: 3 },
    { PROB: "格式錯誤", DF: "格式錯誤" });
  assert.deepEqual(r.inputs, { FUNC: "cdf", MU: 0, SIGMA: 1, X: 1.96 });
  assert.deepEqual(r.errors, {});
});

test("t inv：送 DF、PROB，不送 X", () => {
  const r = prepareDist("t", "inv", { FUNC: "inv", DF: 5, X: 2, PROB: 0.975 }, {});
  assert.deepEqual(r.inputs, { FUNC: "inv", DF: 5, PROB: 0.975 });
});

test("卡方 pdf：送 DF、X", () => {
  const r = prepareDist("chi2", "pdf", { FUNC: "pdf", DF: 3, X: 2, PROB: 0.5 }, {});
  assert.deepEqual(r.inputs, { FUNC: "pdf", DF: 3, X: 2 });
});

test("二項：畫面上的 pdf 送成引擎的 pmf，用 K 不用 X", () => {
  const r = prepareDist("binom", "pdf", { FUNC: "pdf", N: 10, P: 0.3, K: 3, X: 9 }, { X: "錯" });
  assert.deepEqual(r.inputs, { FUNC: "pmf", N: 10, P: 0.3, K: 3 });
  assert.deepEqual(r.errors, {});
});

test("Poisson cdf：送 LAMBDA、K", () => {
  const r = prepareDist("poisson", "cdf", { FUNC: "cdf", LAMBDA: 2, K: 1 }, {});
  assert.deepEqual(r.inputs, { FUNC: "cdf", LAMBDA: 2, K: 1 });
});

test("離散分配不提供 inv：回傳 FUNC 欄位錯誤，不送出", () => {
  const r = prepareDist("binom", "inv", { FUNC: "inv", N: 10, P: 0.3, K: 3 }, {});
  assert.ok(r.errors.FUNC);
});

test("可見欄位依分配與功能而定", () => {
  assert.deepEqual(distFields("normal", "inv"), ["DIST", "FUNC", "MU", "SIGMA", "PROB"]);
  assert.deepEqual(distFields("poisson", "pdf"), ["DIST", "FUNC", "LAMBDA", "K"]);
  assert.deepEqual(distFields("t", "cdf"), ["DIST", "FUNC", "DF", "X"]);
  assert.deepEqual(Object.keys(DISTS), ["normal", "t", "chi2", "binom", "poisson"]);
});

// ---------------------------------------------------------------- 機率分配：標籤

test("cdf 的標籤寫明是機率（左尾、右尾、雙尾），且以浮動格式顯示", () => {
  const rows = distRows("normal", "cdf");
  assert.deepEqual(rows.map((r) => r.key), ["value", "right", "two"]);
  for (const r of rows) {
    assert.match(r.label, /機率/);
    assert.equal(r.kind, "prob");
  }
  assert.match(rows[0].label, /左尾/);
  assert.match(rows[1].label, /右尾/);
  assert.match(rows[2].label, /雙尾/);
});

test("inv 的標籤是臨界值、不是機率；雙尾寫 ±", () => {
  const rows = distRows("t", "inv");
  assert.deepEqual(rows.map((r) => r.key), ["value", "right", "two"]);
  for (const r of rows) {
    assert.match(r.label, /臨界值/);
    assert.doesNotMatch(r.label, /機率/);
    assert.equal(r.kind, "crit");
  }
  assert.match(rows[1].label, /右尾臨界值/);
  assert.match(rows[2].label, /雙尾臨界值 ±/);
  // 常態雙尾：μ 不一定為 0，說明下側臨界值
  assert.match(distRows("normal", "inv")[2].label, /2μ/);
});

test("卡方與離散分配沒有雙尾；卡方 inv 有右尾臨界值", () => {
  assert.deepEqual(distRows("chi2", "cdf").map((r) => r.key), ["value", "right"]);
  assert.deepEqual(distRows("chi2", "inv").map((r) => r.key), ["value", "right"]);
  assert.deepEqual(distRows("binom", "cdf").map((r) => r.key), ["value", "right"]);
  assert.deepEqual(distRows("poisson", "pdf").map((r) => r.key), ["value"]);
  assert.match(distRows("binom", "pdf")[0].label, /P\(X = k\)/);
});

test("pdf（連續）標成機率密度、不是機率，但仍用浮動格式（避免被 2 位小數吃掉）", () => {
  const [r] = distRows("normal", "pdf");
  assert.match(r.label, /機率密度/);
  assert.match(r.label, /不是機率/);
  assert.equal(r.kind, "density");
  assert.deepEqual(floatKeys(distRows("normal", "pdf")), ["value"]);
  assert.deepEqual(floatKeys(distRows("normal", "inv")), []);
  assert.deepEqual(floatKeys(distRows("normal", "cdf")), ["value", "right", "two"]);
});

test("非整數自由度的 Excel 註記：只有 t、卡方且 df 非整數", () => {
  assert.match(dfNote("t", 5.5), /T\.DIST/);
  assert.match(dfNote("chi2", 2.5), /CHISQ\.DIST/);
  assert.equal(dfNote("t", 5), null);
  assert.equal(dfNote("normal", 5.5), null);
  assert.equal(dfNote("t", null), null);
});

test("p 值格式請求：decimals 改為 null（浮動），其他設定保留", () => {
  assert.deepEqual(floatSettings({ decimals: 2, sep: "eu", mode: "AOS" }),
    { decimals: null, sep: "eu", mode: "AOS" });
});

// ---------------------------------------------------------------- 信賴區間與檢定：請求組裝

const base = {
  MEAN: 50, SIGMA: 10, N: 30, CONF: 0.95, SX: 12, X: 12, MU0: 25, EQUAL_VAR: false, ALPHA: 0.05,
};

test("平均數 CI z：送 MEAN、SIGMA、N、CONF", () => {
  const r = prepareInfer("ci_mean_z", {}, base, { MU0: "錯" });
  assert.deepEqual(r.inputs, { MEAN: 50, SIGMA: 10, N: 30, CONF: 0.95 });
  assert.deepEqual(r.errors, {});
});

test("平均數 CI t：摘要值模式送 MEAN、SX、N；資料模式只送 CONF（X 由表格提供）", () => {
  assert.deepEqual(prepareInfer("ci_mean_t", { ciInput: "summary" }, base, {}).inputs,
    { MEAN: 50, SX: 12, N: 30, CONF: 0.95 });
  const d = prepareInfer("ci_mean_t", { ciInput: "data" }, base, { MEAN: "錯", N: "錯" });
  assert.deepEqual(d.inputs, { CONF: 0.95 });
  assert.deepEqual(d.errors, {});
});

test("比例 CI：成功數 XC 欄送成引擎鍵 X", () => {
  const r = prepareInfer("ci_prop", {}, base, {});
  assert.deepEqual(r.inputs, { X: 12, N: 30, CONF: 0.95 });
  assert.deepEqual(inferFields("ci_prop", {}), ["TYPE", "XC", "N", "CONF"]);
});

test("單樣本 t：雙尾送 TAILS 2、不送 ALT；單尾送 TAILS 1 與 ALT", () => {
  assert.deepEqual(prepareInfer("t1", { h1: "two" }, base, {}).inputs,
    { MU0: 25, ALPHA: 0.05, TAILS: 2 });
  assert.deepEqual(prepareInfer("t1", { h1: "greater" }, base, {}).inputs,
    { MU0: 25, ALPHA: 0.05, TAILS: 1, ALT: "greater" });
  assert.deepEqual(prepareInfer("t1", { h1: "less" }, base, {}).inputs.ALT, "less");
});

test("兩樣本 t：送 EQUAL_VAR（合併／Welch）", () => {
  assert.deepEqual(prepareInfer("t2", { h1: "two" }, { ...base, EQUAL_VAR: true }, {}).inputs,
    { EQUAL_VAR: true, ALPHA: 0.05, TAILS: 2 });
});

test("成對 t、卡方：只送 ALPHA（與 TAILS），資料由表格提供", () => {
  assert.deepEqual(prepareInfer("tpaired", { h1: "less" }, base, {}).inputs,
    { ALPHA: 0.05, TAILS: 1, ALT: "less" });
  assert.deepEqual(prepareInfer("chi_gof", {}, base, {}).inputs, { ALPHA: 0.05 });
  assert.deepEqual(prepareInfer("chi_ind", {}, base, {}).inputs, { ALPHA: 0.05 });
  assert.equal(Object.keys(INFER_TYPES).length, 8);
});

// ---------------------------------------------------------------- 表格

test("表格版面：依類型決定欄位；卡方獨立性欄數可變", () => {
  assert.equal(gridLayout("ci_mean_z", {}), null);
  assert.equal(gridLayout("ci_mean_t", { ciInput: "summary" }), null);
  assert.equal(gridLayout("ci_mean_t", { ciInput: "data" }).columns.length, 1);
  assert.equal(gridLayout("t2", {}).columns.length, 2);
  assert.equal(gridLayout("chi_ind", { cols: 4 }).columns.length, 4);
  assert.match(gridLayout("chi_gof", { gof: "probs" }).columns[1].label, /機率/);
  assert.match(gridLayout("chi_gof", { gof: "exp" }).columns[1].label, /期望/);
});

test("讀兩樣本表格：兩欄可不等長（各自結尾空白忽略）", () => {
  const cells = [["23", "20"], ["25", "22"], ["28", ""], ["", ""]];
  assert.deepEqual(readInferGrid("t2", cells, "us", {}).inputs, { X: [23, 25, 28], Y: [20, 22] });
});

test("讀兩樣本表格：欄中間的空白是錯誤（指出列欄）", () => {
  const r = readInferGrid("t2", [["1", "2"], ["", "3"], ["4", "5"]], "us", {});
  assert.equal(r.row, 2);
  assert.equal(r.col, 1);
});

test("成對表格：每列兩格都要有值", () => {
  const r = readInferGrid("tpaired", [["1", "2"], ["3", ""]], "us", {});
  assert.equal(r.row, 2);
  assert.equal(r.col, 2);
  assert.deepEqual(readInferGrid("tpaired", [["1", "2"], ["3", "4"]], "us", {}).inputs,
    { X: [1, 3], Y: [2, 4] });
});

test("單欄表格（t1、CI t）：EU 千分位", () => {
  assert.deepEqual(readInferGrid("t1", [["1,5"], ["2"]], "eu", {}).inputs, { X: [1.5, 2] });
});

test("適合度：均等模式第二欄須空白；期望／機率模式送 EXP／PROBS", () => {
  const cells = [["18", "20"], ["22", "20"], ["20", "20"]];
  assert.deepEqual(readInferGrid("chi_gof", cells, "us", { gof: "exp" }).inputs,
    { OBS: [18, 22, 20], EXP: [20, 20, 20] });
  assert.deepEqual(readInferGrid("chi_gof", [["1", "0.5"], ["1", "0.5"]], "us", { gof: "probs" }).inputs,
    { OBS: [1, 1], PROBS: [0.5, 0.5] });
  assert.equal(readInferGrid("chi_gof", cells, "us", { gof: "uniform" }).col, 2);
  assert.deepEqual(readInferGrid("chi_gof", [["18", ""], ["22", ""]], "us", { gof: "uniform" }).inputs,
    { OBS: [18, 22] });
});

test("獨立性：r×c 表格，結尾空白列略過，任何空格是錯誤", () => {
  assert.deepEqual(readInferGrid("chi_ind", [["10", "20"], ["30", "40"], ["", ""]], "us", {}).inputs,
    { TABLE: [[10, 20], [30, 40]] });
  const r = readInferGrid("chi_ind", [["10", ""], ["30", "40"]], "us", {});
  assert.equal(r.row, 1);
  assert.equal(r.col, 2);
});

test("敘述統計表格 [X, 次數]：錯誤的欄號對應畫面（次數是第 2 欄）", () => {
  assert.deepEqual(readDescribeTable([["2", ""], ["4", ""]], "us"), { X: [2, 4], F: null });
  assert.deepEqual(readDescribeTable([["2", "1"], ["4", "3"]], "us"), { X: [2, 4], F: [1, 3] });
  const r = readDescribeTable([["2", "1"], ["4", "0.5"]], "us");
  assert.equal(r.row, 2);
  assert.equal(r.col, 2);
});

// ---------------------------------------------------------------- 結論句與結果列

test("H0／H1 文字依類型與單雙尾產生", () => {
  assert.deepEqual(hypotheses("t1", "two"), { h0: "H0：μ = μ0", h1: "H1：μ ≠ μ0" });
  assert.equal(hypotheses("t1", "greater").h1, "H1：μ > μ0");
  assert.equal(hypotheses("t2", "less").h1, "H1：μX < μY");
  assert.match(hypotheses("tpaired", "two").h0, /μd = 0/);
  assert.match(hypotheses("chi_gof", "two").h0, /服從/);
  assert.match(hypotheses("chi_ind", "two").h0, /獨立/);
  assert.equal(hypotheses("ci_mean_z", "two"), null);
});

test("檢定結果列：p 值為浮動格式；只列出引擎有回傳的鍵", () => {
  const rows = inferRows("t2", { t: 3.5, df: 11, p: 0.005, alpha: 0.05, sp: 2.3, method: "pooled" });
  const keys = rows.map((r) => r.key);
  assert.ok(keys.includes("p") && keys.includes("t") && keys.includes("sp"));
  assert.ok(!keys.includes("sx")); // 沒回傳就不列
  assert.deepEqual(floatKeys(rows), ["p"]);
  assert.match(rows.find((r) => r.key === "p").label, /p 值/);
});

test("比例 CI：比例與區間都用浮動格式", () => {
  const rows = inferRows("ci_prop", { p_hat: 0.4, se: 0.09, z_crit: 1.96, margin: 0.18, lower: 0.2, upper: 0.6 });
  assert.ok(floatKeys(rows).includes("p_hat") && floatKeys(rows).includes("lower"));
  assert.ok(!floatKeys(rows).includes("z_crit"));
});

test("敘述統計分組：集中趨勢、離散、四分位、形狀，涵蓋引擎的所有鍵", () => {
  assert.deepEqual(DESC_GROUPS.map((g) => g.title.slice(0, 4)), ["集中趨勢", "離散程度", "四分位數", "分配形狀"]);
  const keys = DESC_GROUPS.flatMap((g) => g.keys).sort();
  assert.deepEqual(keys, ["cv", "iqr", "kurt", "max", "mean", "median", "min", "modes", "n",
    "q1", "q3", "range", "sigma_x", "skew", "sum", "sx", "var"].sort());
});

// ---------------------------------------------------------------- 分配圖

test("圖的範圍：含標記點；標記點太遠時不擴張並回報 outside", () => {
  assert.deepEqual(chartRange(-3, 3, 1.96), { lo: -3, hi: 3, outside: false });
  assert.deepEqual(chartRange(-3, 3, 4), { lo: -3, hi: 4, outside: false });
  assert.equal(chartRange(-3, 3, 100).outside, true);
  assert.deepEqual(chartRange(-3, 3, null), { lo: -3, hi: 3, outside: false });
});

test("連續分配的取樣點數 ≤ 100", () => {
  const xs = chartXs(-4, 4, 61);
  assert.equal(xs.length, 61);
  assert.equal(xs[0], -4);
  assert.equal(xs[60], 4);
});

test("離散分配的 k 範圍：含 K、最多 100 點、二項不超過 N", () => {
  const b = discreteRange("binom", { N: 10, P: 0.3 }, 3);
  assert.equal(b[0], 0);
  assert.equal(b[b.length - 1], 10);
  const big = discreteRange("binom", { N: 100000, P: 0.5 }, 50000);
  assert.ok(big.length <= 100 && big.includes(50000));
  assert.equal(big.length, 100);
  const p = discreteRange("poisson", { LAMBDA: 2 }, 1);
  assert.equal(p[0], 0);
  assert.ok(p.includes(1));
});

test("取點請求：連續用 pdf、離散用 pmf，參數照抄", () => {
  assert.deepEqual(pointRequest("normal", { MU: 0, SIGMA: 1 }, 0.5),
    { sheet: "dist", action: "normal", inputs: { FUNC: "pdf", MU: 0, SIGMA: 1, X: 0.5 } });
  assert.deepEqual(pointRequest("binom", { N: 10, P: 0.3 }, 3),
    { sheet: "dist", action: "binom", inputs: { FUNC: "pmf", N: 10, P: 0.3, K: 3 } });
});

test("圖形幾何：曲線、陰影到 shadeTo、標記線；座標在畫布內", () => {
  const pts = [[-1, 0.1], [0, 0.4], [1, 0.1]];
  const g = chartGeometry({ points: pts, discrete: false, shadeTo: 0, marker: 0, width: 300, height: 150 });
  assert.match(g.curve, /^M/);
  assert.match(g.area, /^M.*Z$/);
  assert.ok(g.markerX > 0 && g.markerX < 300);
  const d = chartGeometry({ points: [[0, 0.2], [1, 0.5], [2, 0.3]], discrete: true, shadeTo: 1, width: 300, height: 150 });
  assert.equal(d.bars.length, 3);
  assert.deepEqual(d.bars.map((b) => b.shaded), [true, true, false]);
  for (const b of d.bars) assert.ok(b.y >= 0 && b.y + b.h <= 150);
  const none = chartGeometry({ points: pts, discrete: false, shadeTo: null, width: 300, height: 150 });
  assert.equal(none.area, "");
});

// ---------------------------------------------------------------- matrix 欄位（列聯表）

import { parseMatrix, collect } from "../../web/js/input.js";

test("parseMatrix：分號或換行分列；列長不一、空白、非數字回傳 null", () => {
  assert.deepEqual(parseMatrix("10 20; 30 40"), [[10, 20], [30, 40]]);
  assert.deepEqual(parseMatrix("1,5 2\n3 4", "eu"), [[1.5, 2], [3, 4]]);
  assert.equal(parseMatrix("1 2; 3"), null);
  assert.equal(parseMatrix(""), null);
  assert.equal(parseMatrix("1 a; 3 4"), null);
  const r = collect({ TABLE: "1 2; 3" }, { TABLE: { kind: "matrix", label: "列聯表" } });
  assert.ok(r.errors.TABLE);
});

// ---------------------------------------------------------------- 情境匯出入：新工作表

import { normalizeData, emptyData, prepareScenarioForLoad } from "../../web/js/storage/backup.js";

test("匯入時 describe／dist／infer 的情境保留（含類型選單與 r×c 表格），不認得的欄位丟棄", () => {
  const data = {
    ...emptyData(),
    scenarios: [
      { id: "a", worksheet: "infer", name: "獨立性", updated_at: "2026-10-28T14:00:00+08:00", sep: "us",
        inputs: { TYPE: { text: "chi_ind" }, ALPHA: { text: "0.05" }, BOGUS: { text: "1" },
          __grid: [["10", "20", "5"], ["30", "40", "6"]] } },
      { id: "b", worksheet: "dist", name: "常態", updated_at: "2026-10-28T14:00:00+08:00", sep: "us",
        inputs: { DIST: { text: "normal" }, FUNC: { text: "cdf" }, X: { text: "1.96" } } },
      { id: "c", worksheet: "describe", name: "資料", updated_at: "2026-10-28T14:00:00+08:00", sep: "us",
        inputs: { __grid: [["2", ""], ["4", ""]] } },
    ],
  };
  const out = normalizeData(data).scenarios;
  assert.equal(out.length, 3);
  assert.deepEqual(out[0].inputs, {
    TYPE: { text: "chi_ind" }, ALPHA: { text: "0.05" }, __grid: [["10", "20", "5"], ["30", "40", "6"]],
  });
  assert.deepEqual(out[1].inputs.X, { text: "1.96" });
  assert.deepEqual(out[2].inputs.__grid, [["2", ""], ["4", ""]]);
  // US 存、EU 載入：表格內容改寫為 EU 寫法
  const prep = prepareScenarioForLoad({ ...out[1], inputs: { X: { text: "1.96" } } }, "eu");
  assert.equal(prep.inputs.X.text, "1,96");
});

// ---------------------------------------------------------------- 審查修正第 1 輪

test("Q1／Q3 說明寫明 Excel QUARTILE.INC 的 (n−1)·p 線性內插（不是半部中位數法）", () => {
  const fm = fieldMap("describe");
  for (const [id, ex] of [["q1", "4"], ["q3", "5.5"]]) {
    assert.match(fm[id].help, /QUARTILE\.INC/, id);
    assert.match(fm[id].help, /\(n−1\)·p/, id);
    assert.match(fm[id].help, /線性內插/, id);
    assert.ok(fm[id].help.includes(`例：${ex}`), id);
    assert.doesNotMatch(fm[id].help, /^下半部|^上半部/, id);
  }
  assert.ok(SHEETS.describe);
});

test("陰影端點：把 shadeTo 精確插入取樣點（已存在或超出範圍則不插）", () => {
  assert.deepEqual(withPoint([0, 1, 2], 1.5), [0, 1, 1.5, 2]);
  assert.deepEqual(withPoint([0, 1, 2], 1), [0, 1, 2]);
  assert.deepEqual(withPoint([0, 1, 2], 5), [0, 1, 2]);
  assert.deepEqual(withPoint([0, 1, 2], null), [0, 1, 2]);
  assert.ok(withPoint(chartXs(-4, 4, 61), 1.96).length <= 100);
});

test("陰影面積的右緣正好在 shadeTo", () => {
  const pts = [[-1, 0.1], [0, 0.4], [0.5, 0.35], [1, 0.1]];
  const g = chartGeometry({ points: pts, discrete: false, shadeTo: 0.5, marker: 0.5, width: 300, height: 150 });
  const xs = [...g.area.matchAll(/[ML](-?[\d.]+),/g)].map((m) => Number(m[1]));
  assert.equal(Math.max(...xs), g.markerX);
});

test("inv 結果的提示：雙尾 α = 0.05 時輸入 p = 0.05；其他功能沒有提示", () => {
  assert.equal(distHint("t", "inv"), "雙尾 α = 0.05 時請輸入 p = 0.05");
  assert.equal(distHint("normal", "inv"), "雙尾 α = 0.05 時請輸入 p = 0.05");
  assert.equal(distHint("chi2", "inv"), null); // 卡方沒有雙尾臨界值
  assert.equal(distHint("t", "cdf"), null);
});

// ---------------------------------------------------------------- 版面同步判斷（情境載入後欄位要跟著選單）

test("layoutSyncNeeded：情境載入（scenario-apply、表單層級 change）與選單改變都要重新同步欄位", async () => {
  const { layoutSyncNeeded } = await import("../../web/js/stat.js");
  const form = { name: "form" };
  const distSel = { name: "DIST" };
  const funcSel = { name: "FUNC" };
  const other = { name: "X" };
  const controls = [distSel, funcSel];
  // 回歸：applyScenario 在 form 上派送 change（target 是 form 本身）與 scenario-apply
  assert.equal(layoutSyncNeeded("change", form, form, controls), true);
  assert.equal(layoutSyncNeeded("scenario-apply", form, form, controls), true);
  assert.equal(layoutSyncNeeded("form-reset", form, form, controls), true);
  assert.equal(layoutSyncNeeded("change", distSel, form, controls), true);
  assert.equal(layoutSyncNeeded("change", funcSel, form, controls), true);
  // 一般數值欄位改變不必重排版面
  assert.equal(layoutSyncNeeded("change", other, form, controls), false);
  assert.equal(layoutSyncNeeded("input", form, form, controls), false);
});
