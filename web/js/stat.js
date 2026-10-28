// 純函式：統計頁（敘述統計、機率分配、信賴區間與檢定）的請求組裝、標籤、結論句、表格讀取與分配圖幾何。
// 不碰 DOM、不呼叫引擎，可用 node --test 測試。
// 原則：所有分配值、統計量、p 值都由引擎（engine/bridge.py）計算並格式化；
// 這裡只決定「送哪些鍵」「怎麼標示」「圖要畫在哪裡」，不在 JS 自己算分配、不自己格式化數字。
import { parseNumber } from "./input.js";
import { readStatTable } from "./tables.js";

const blank = (s) => String(s ?? "").trim() === "";

/** p 值、機率類欄位的格式請求：小數位數改為浮動（null），引擎以 10 位有效數字、極小值科學記號顯示。 */
export function floatSettings(settings) {
  return { ...settings, decimals: null };
}

/** 結果列中要用浮動格式的鍵（kind 為 prob 或 density）。 */
export function floatKeys(rows) {
  return rows.filter((r) => r.kind === "prob" || r.kind === "density").map((r) => r.key);
}

// ================================================================ 機率分配（distributions）

/** 各分配：中文名、參數欄位、是否離散、是否有雙尾。 */
export const DISTS = {
  normal: { label: "常態 Normal", params: ["MU", "SIGMA"], discrete: false, two: true },
  t: { label: "t 分配", params: ["DF"], discrete: false, two: true },
  chi2: { label: "卡方 χ²", params: ["DF"], discrete: false, two: false },
  binom: { label: "二項 Binomial", params: ["N", "P"], discrete: true, two: false },
  poisson: { label: "Poisson", params: ["LAMBDA"], discrete: true, two: false },
};

/** 分配頁所有可能隱藏的欄位。 */
export const DIST_INPUTS = ["MU", "SIGMA", "DF", "N", "P", "LAMBDA", "X", "K", "PROB"];

/** 目前分配與功能下要顯示的欄位 id（依畫面順序）。 */
export function distFields(dist, func) {
  const d = DISTS[dist];
  const point = func === "inv" ? "PROB" : (d.discrete ? "K" : "X");
  return ["DIST", "FUNC", ...d.params, point];
}

/**
 * 版面同步判斷（純函式）：哪些事件之後要依選單重新決定顯示哪些欄位。
 * - 選單本身（controls）的 change
 * - 表單層級的 change（target 是 form 本身：情境載入 applyScenario 會這樣派送）
 * - scenario-apply（情境載入）、form-reset（清除鈕／Esc）
 * 否則情境載入後選單已換、欄位卻還是舊的，計算用的是看不到的參數（誤導）。
 */
export function layoutSyncNeeded(type, target, form, controls) {
  if (type === "scenario-apply" || type === "form-reset") return true;
  if (type !== "change") return false;
  return target === form || controls.includes(target);
}

/**
 * 組出分配的引擎 inputs：只送目前看得到的欄位；隱藏欄位的格式錯誤忽略（使用者看不到，也不會送出）。
 * 畫面上的 pdf 對離散分配送成 pmf；離散分配選 inv 回傳 FUNC 錯誤。
 * inputs 是 collect 的結果（引擎鍵）、errors 以欄位 id 為鍵；回傳 {inputs, errors}。
 */
export function prepareDist(dist, func, inputs, errors) {
  const d = DISTS[dist];
  const visible = distFields(dist, func);
  const outErr = {};
  for (const [id, msg] of Object.entries(errors || {})) if (visible.includes(id)) outErr[id] = msg;
  if (d.discrete && func === "inv") {
    outErr.FUNC = `${d.label} 是離散分配，不提供反查 inv；請改用 pmf 或 cdf`;
  }
  const out = { FUNC: d.discrete && func === "pdf" ? "pmf" : func };
  for (const id of visible.slice(2)) out[id] = inputs[id] ?? null;
  return { inputs: out, errors: outErr };
}

/**
 * 結果列（key＝引擎回傳鍵）：標籤明確區分「機率」與「臨界值」。
 * kind：prob（機率，浮動格式）、density（機率密度，浮動格式）、crit（臨界值，依小數位數設定）。
 */
export function distRows(dist, func) {
  const d = DISTS[dist];
  const v = d.discrete ? "k" : "x";
  if (func === "pdf") {
    return d.discrete
      ? [{ key: "value", label: "機率 P(X = k)", kind: "prob" }]
      : [{ key: "value", label: "機率密度 f(x)（高度，不是機率）", kind: "density" }];
  }
  if (func === "cdf") {
    const rows = [
      { key: "value", label: `左尾機率 P(X ≤ ${v})`, kind: "prob" },
      { key: "right", label: `右尾機率 P(X > ${v})`, kind: "prob" },
    ];
    if (d.two) {
      rows.push({
        key: "two",
        label: dist === "t" ? "雙尾機率 P(|T| ≥ |x|)" : "雙尾機率 P(|X − μ| ≥ |x − μ|)",
        kind: "prob",
      });
    }
    return rows;
  }
  // inv：反查得到的是 x（臨界值），不是機率
  const rows = [
    { key: "value", label: "左尾臨界值 x（使 P(X ≤ x) = p）", kind: "crit" },
    { key: "right", label: "右尾臨界值 x（使 P(X > x) = p）", kind: "crit" },
  ];
  if (d.two) {
    rows.push(dist === "t"
      ? { key: "two", label: "雙尾臨界值 ±（使 P(|T| ≥ t) = p）", kind: "crit" }
      : { key: "two", label: "雙尾臨界值 ±：上側 x（下側為 2μ − x；μ = 0 時即 ±x）", kind: "crit" });
  }
  return rows;
}

/** 非整數自由度的提醒（Excel 會把 df 截成整數）；不需要時回傳 null。 */
export function dfNote(dist, df) {
  if ((dist !== "t" && dist !== "chi2") || typeof df !== "number" || Number.isInteger(df)) return null;
  return "Excel 的 T.DIST／CHISQ.DIST 會把自由度截成整數，本 App 依數學定義計算，結果可能與 Excel 不同";
}

// ---------------------------------------------------------------- 分配圖

export const CHART_POINTS = 61; // 連續分配取樣點數（≤ 100，每點一次引擎呼叫）
const MAX_BARS = 100; // 每根一次引擎呼叫，與連續分配同樣 ≤ 100

/** 圖的 x 範圍反查機率（左、右）：t 分配尾巴很厚，取較窄的分位數。 */
export function rangeProbs(dist) {
  return dist === "t" ? [0.005, 0.995] : [0.001, 0.999];
}

/**
 * 圖的 x 範圍：以引擎反查的 [lo, hi] 為準並納入標記點 mark；
 * mark 離範圍超過一個範圍寬度時不擴張（曲線會擠成一條線），回報 outside。
 */
export function chartRange(lo, hi, mark) {
  if (typeof mark !== "number" || (mark >= lo && mark <= hi)) return { lo, hi, outside: false };
  const span = hi - lo;
  if (mark < lo - span || mark > hi + span) return { lo, hi, outside: true };
  return { lo: Math.min(lo, mark), hi: Math.max(hi, mark), outside: false };
}

/** 等距取 n 個點（含兩端）。 */
export function chartXs(lo, hi, n = CHART_POINTS) {
  return Array.from({ length: n }, (_, i) => (i === n - 1 ? hi : lo + ((hi - lo) * i) / (n - 1)));
}

/**
 * 離散分配畫哪些 k：平均數 ± 5 個標準差（只是決定畫面範圍的算術，不是機率計算），
 * 一定包含 K，最多 MAX_BARS 根；二項不超過 N、不小於 0。
 */
export function discreteRange(dist, params, k) {
  let mean;
  let sd;
  let top = Infinity;
  if (dist === "binom") {
    mean = params.N * params.P;
    sd = Math.sqrt(params.N * params.P * (1 - params.P));
    top = params.N;
  } else {
    mean = params.LAMBDA;
    sd = Math.sqrt(params.LAMBDA);
  }
  let a = Math.max(0, Math.floor(mean - 5 * sd));
  let b = Math.min(top, Math.ceil(mean + 5 * sd));
  if (typeof k === "number") {
    a = Math.min(a, k);
    b = Math.max(b, k);
  }
  if (b - a + 1 > MAX_BARS) { // 太寬：以 K（或平均數）為中心取 MAX_BARS 根
    const c = typeof k === "number" ? k : Math.round(mean);
    a = Math.max(0, c - MAX_BARS / 2);
    b = Math.min(top, a + MAX_BARS - 1);
    a = Math.max(0, b - MAX_BARS + 1);
  }
  const out = [];
  for (let i = a; i <= b; i++) out.push(i);
  return out;
}

/**
 * 把陰影端點 x 精確插入已排序的取樣點（讓陰影面積的右緣正好在 x，而不是最近的取樣點）；
 * x 不在範圍內、已存在或不是數字時原樣回傳。
 */
export function withPoint(xs, x) {
  if (typeof x !== "number" || !xs.length || x < xs[0] || x > xs[xs.length - 1] || xs.includes(x)) return xs;
  const i = xs.findIndex((v) => v > x);
  return [...xs.slice(0, i), x, ...xs.slice(i)];
}

/** inv 結果下的提示（引擎語意：雙尾臨界值使雙尾機率等於 p）；沒有雙尾的分配或其他功能回傳 null。 */
export function distHint(dist, func) {
  return func === "inv" && DISTS[dist].two ? "雙尾 α = 0.05 時請輸入 p = 0.05" : null;
}

/** 單點的 pdf／pmf 請求（參數照抄使用者輸入）。 */
export function pointRequest(dist, params, x) {
  const d = DISTS[dist];
  const inputs = { FUNC: d.discrete ? "pmf" : "pdf" };
  for (const p of d.params) inputs[p] = params[p];
  inputs[d.discrete ? "K" : "X"] = x;
  return { sheet: "dist", action: dist, inputs };
}

/** 反查請求（決定圖的範圍）。 */
export function invRequest(dist, params, prob) {
  const inputs = { FUNC: "inv", PROB: prob };
  for (const p of DISTS[dist].params) inputs[p] = params[p];
  return { sheet: "dist", action: dist, inputs };
}

const PAD = { l: 8, r: 8, t: 10, b: 22 };
const r2 = (v) => Math.round(v * 100) / 100;

/**
 * 圖形幾何（座標換算，不涉及機率計算）。
 * points：[[x, 高度], ...]（高度由引擎 pdf／pmf 算出）；shadeTo：陰影到此 x（含），null＝不畫陰影；
 * marker：標記線的 x（null＝不畫）。回傳 {curve, area, bars, markerX, base, ticks}。
 */
export function chartGeometry({ points, discrete, shadeTo = null, marker = null, width, height }) {
  const xs = points.map((p) => p[0]);
  const ymax = Math.max(...points.map((p) => p[1])) || 1;
  const lo = Math.min(...xs);
  const hi = Math.max(...xs);
  const half = discrete ? 0.5 : 0;
  const span = hi - lo + 2 * half || 1;
  const w = width - PAD.l - PAD.r;
  const h = height - PAD.t - PAD.b;
  const base = PAD.t + h;
  const sx = (x) => r2(PAD.l + ((x - lo + half) / span) * w);
  const sy = (y) => r2(base - (y / ymax) * h);
  const out = { curve: "", area: "", bars: [], markerX: null, base: r2(base), ticks: [] };
  if (discrete) {
    const bw = Math.max(1, (w / span) * 0.8);
    out.bars = points.map(([x, y]) => {
      const top = sy(y);
      return {
        x: r2(sx(x) - bw / 2), y: top, w: r2(bw), h: r2(base - top), k: x,
        shaded: shadeTo !== null && x <= shadeTo,
      };
    });
  } else {
    out.curve = points.map(([x, y], i) => `${i ? "L" : "M"}${sx(x)},${sy(y)}`).join(" ");
    if (shadeTo !== null) {
      const inside = points.filter(([x]) => x <= shadeTo);
      if (inside.length) {
        const last = inside[inside.length - 1][0];
        out.area = `M${sx(inside[0][0])},${r2(base)} `
          + inside.map(([x, y]) => `L${sx(x)},${sy(y)}`).join(" ")
          + ` L${sx(last)},${r2(base)} Z`;
      }
    }
  }
  if (marker !== null && marker >= lo - half && marker <= hi + half) out.markerX = sx(marker);
  out.ticks = [lo, hi].map((x) => ({ x: sx(x), value: x }));
  return out;
}

// ================================================================ 信賴區間與檢定（inference）

/** 各類型：標題、看得到的欄位（不含 TYPE）、是否為檢定、表格類型。 */
export const INFER_TYPES = {
  ci_mean_z: { label: "平均數信賴區間（σ 已知，z）", fields: ["MEAN", "SIGMA", "N", "CONF"], test: false },
  ci_mean_t: { label: "平均數信賴區間（σ 未知，t）", fields: ["CI_INPUT", "CONF"], test: false },
  ci_prop: { label: "比例信賴區間", fields: ["XC", "N", "CONF"], test: false },
  t1: { label: "單樣本 t 檢定", fields: ["MU0", "H1", "ALPHA"], test: true },
  t2: { label: "兩樣本 t 檢定（合併／Welch）", fields: ["EQUAL_VAR", "H1", "ALPHA"], test: true },
  tpaired: { label: "成對 t 檢定", fields: ["H1", "ALPHA"], test: true },
  chi_gof: { label: "卡方適合度檢定", fields: ["GOF_EXP", "ALPHA"], test: true },
  chi_ind: { label: "卡方獨立性檢定", fields: ["ALPHA"], test: true },
};

/** 只控制畫面、不送引擎的欄位。 */
const UI_ONLY = new Set(["TYPE", "CI_INPUT", "H1", "GOF_EXP"]);
/** 欄位 id 與引擎鍵不同的欄位。 */
const KEY_OF = { XC: "X" };

/** 目前類型下要顯示的欄位 id（含 TYPE）。opts.ciInput：data｜summary。 */
export function inferFields(type, opts = {}) {
  const out = ["TYPE", ...INFER_TYPES[type].fields];
  if (type === "ci_mean_t" && opts.ciInput === "summary") out.splice(2, 0, "MEAN", "SX", "N");
  return out;
}

/**
 * 組出檢定／區間的引擎 inputs（表格資料另由 readInferGrid 提供）：只送看得到且會送引擎的欄位，
 * 隱藏欄位的錯誤忽略；H1（雙尾／左尾／右尾）轉成 TAILS 與 ALT（雙尾不送 ALT）。
 * opts：{ciInput, h1}。回傳 {inputs, errors}。
 */
export function prepareInfer(type, opts, inputs, errors) {
  const visible = inferFields(type, opts);
  const outErr = {};
  for (const [id, msg] of Object.entries(errors || {})) if (visible.includes(id)) outErr[id] = msg;
  const out = {};
  for (const id of visible) {
    if (UI_ONLY.has(id)) continue;
    const key = KEY_OF[id] || id;
    out[key] = inputs[key] ?? null;
  }
  if (visible.includes("H1")) {
    const h1 = opts.h1 || "two";
    out.TAILS = h1 === "two" ? 2 : 1;
    if (h1 !== "two") out.ALT = h1;
  }
  return { inputs: out, errors: outErr };
}

/**
 * 表格版面：{key, caption, columns}；不用表格（摘要值）回傳 null。
 * opts：{ciInput, gof: uniform|exp|probs, cols: 卡方獨立性的欄數}。
 */
export function gridLayout(type, opts = {}) {
  const col = (label, abbr, example) => ({ label, abbr, example });
  switch (type) {
    case "ci_mean_t":
      if (opts.ciInput === "summary") return null;
    // fall through：原始資料
    case "t1":
      return { key: "one", caption: "樣本資料 X（每列一筆，可從 Excel 貼上）", columns: [col("X", "X", "23")] };
    case "t2":
      return {
        key: "two", caption: "兩組樣本 X、Y（筆數可不同，可從 Excel 貼上）",
        columns: [col("X 組", "X", "23"), col("Y 組", "Y", "20")],
      };
    case "tpaired":
      return {
        key: "paired", caption: "成對資料（每列一對，差值 d = X − Y）",
        columns: [col("X（前）", "X", "23"), col("Y（後）", "Y", "20")],
      };
    case "chi_gof": {
      const second = opts.gof === "probs" ? col("機率", "PROB", "0.25")
        : opts.gof === "exp" ? col("期望次數", "EXP", "20") : col("（均等時留空）", "—", "");
      return { key: "gof", caption: "各類別的觀察次數（與期望次數或機率）", columns: [col("觀察次數", "OBS", "18"), second] };
    }
    case "chi_ind": {
      const n = Math.min(10, Math.max(2, opts.cols || 2));
      return {
        key: "ind", caption: "列聯表（r × c 觀察次數，每列一個類別）",
        columns: Array.from({ length: n }, (_, j) => col(`第 ${j + 1} 欄`, `C${j + 1}`, "10")),
      };
    }
    default:
      return null;
  }
}

function fail(error, row, col) {
  return { error, row, col };
}

/** 讀一欄：結尾空白忽略，中間空白是錯誤。回傳 {values} 或 fail。 */
function readColumn(cells, j, sep, name) {
  let last = cells.length - 1;
  while (last >= 0 && blank(cells[last][j])) last--;
  const values = [];
  for (let i = 0; i <= last; i++) {
    const t = cells[i][j];
    if (blank(t)) return fail(`第 ${i + 1} 列 ${name} 是空白（中間不可空白，請補上或刪除該列）`, i + 1, j + 1);
    const v = parseNumber(t, sep);
    if (v === null) return fail(`第 ${i + 1} 列 ${name}「${String(t).trim()}」不是數字`, i + 1, j + 1);
    values.push(v);
  }
  return { values };
}

/** 去掉結尾的全空白列。 */
function trimRows(cells) {
  let last = cells.length - 1;
  while (last >= 0 && cells[last].every(blank)) last--;
  return cells.slice(0, last + 1);
}

/**
 * 讀檢定表格 → {inputs: {X, Y}｜{OBS, EXP/PROBS}｜{TABLE}} 或 {error, row, col}（1 起算）。
 * 空格不補 0、不略過（避免看似正常卻錯誤的結果）；只有結尾的空白列忽略。
 */
export function readInferGrid(type, cells, sep = "us", opts = {}) {
  if (type === "ci_mean_t" || type === "t1") {
    const x = readColumn(cells, 0, sep, "X");
    return x.error ? x : { inputs: { X: x.values } };
  }
  if (type === "t2") {
    const x = readColumn(cells, 0, sep, "X");
    if (x.error) return x;
    const y = readColumn(cells, 1, sep, "Y");
    return y.error ? y : { inputs: { X: x.values, Y: y.values } };
  }
  if (type === "tpaired") {
    const rows = trimRows(cells);
    for (let i = 0; i < rows.length; i++) {
      for (let j = 0; j < 2; j++) {
        if (blank(rows[i][j])) return fail(`第 ${i + 1} 列是成對資料，X、Y 都要填`, i + 1, j + 1);
      }
    }
    const x = readColumn(rows, 0, sep, "X");
    if (x.error) return x;
    const y = readColumn(rows, 1, sep, "Y");
    return y.error ? y : { inputs: { X: x.values, Y: y.values } };
  }
  if (type === "chi_gof") {
    const rows = trimRows(cells);
    const obs = readColumn(rows, 0, sep, "觀察次數");
    if (obs.error) return obs;
    if (rows.length > obs.values.length) {
      return fail(`第 ${obs.values.length + 1} 列沒有觀察次數`, obs.values.length + 1, 1);
    }
    if (opts.gof !== "exp" && opts.gof !== "probs") {
      const i = rows.findIndex((r) => !blank(r[1]));
      if (i >= 0) return fail(`均等期望時第 2 欄須空白（第 ${i + 1} 列有值）；要自訂請改選期望次數或機率`, i + 1, 2);
      return { inputs: { OBS: obs.values } };
    }
    const name = opts.gof === "exp" ? "期望次數" : "機率";
    for (let i = 0; i < rows.length; i++) {
      if (blank(rows[i][1])) return fail(`第 ${i + 1} 列請輸入${name}`, i + 1, 2);
    }
    const sec = readColumn(rows, 1, sep, name);
    if (sec.error) return sec;
    return { inputs: { OBS: obs.values, [opts.gof === "exp" ? "EXP" : "PROBS"]: sec.values } };
  }
  if (type === "chi_ind") {
    const rows = trimRows(cells);
    const table = [];
    for (let i = 0; i < rows.length; i++) {
      const row = [];
      for (let j = 0; j < rows[i].length; j++) {
        const t = rows[i][j];
        if (blank(t)) return fail(`第 ${i + 1} 列第 ${j + 1} 欄是空白（沒有觀察值請輸入 0）`, i + 1, j + 1);
        const v = parseNumber(t, sep);
        if (v === null) return fail(`第 ${i + 1} 列第 ${j + 1} 欄「${String(t).trim()}」不是數字`, i + 1, j + 1);
        row.push(v);
      }
      table.push(row);
    }
    return { inputs: { TABLE: table } };
  }
  return { inputs: {} };
}

const H = {
  t1: { h0: "μ = μ0", two: "μ ≠ μ0", less: "μ < μ0", greater: "μ > μ0" },
  t2: { h0: "μX = μY", two: "μX ≠ μY", less: "μX < μY", greater: "μX > μY" },
  tpaired: { h0: "μd = 0（d = X − Y）", two: "μd ≠ 0", less: "μd < 0", greater: "μd > 0" },
};

/** H0／H1 文字（依類型與單雙尾）；信賴區間回傳 null。 */
export function hypotheses(type, h1 = "two") {
  if (H[type]) return { h0: `H0：${H[type].h0}`, h1: `H1：${H[type][h1] || H[type].two}` };
  if (type === "chi_gof") return { h0: "H0：資料服從指定的分配（各類別比例如期望）", h1: "H1：資料不服從指定的分配" };
  if (type === "chi_ind") return { h0: "H0：列變數與行變數獨立", h1: "H1：列變數與行變數不獨立（有關聯）" };
  return null;
}

const P_ROW = { key: "p", label: "p 值 p-value", kind: "prob" };

/** 各類型的結果列（依序；kind：prob＝機率類，浮動格式；num＝依小數位數設定）。 */
const INFER_ROWS = {
  ci_mean_z: [
    ["z_crit", "臨界值 z"], ["se", "標準誤 SE = σ/√n"], ["margin", "誤差界限 E"],
    ["lower", "下限 Lower"], ["upper", "上限 Upper"],
  ],
  ci_mean_t: [
    ["n", "樣本數 n"], ["mean", "樣本平均 x̄"], ["sx", "樣本標準差 Sx"], ["df", "自由度 df"],
    ["t_crit", "臨界值 t"], ["se", "標準誤 SE"], ["margin", "誤差界限 E"],
    ["lower", "下限 Lower"], ["upper", "上限 Upper"],
  ],
  ci_prop: [
    ["p_hat", "樣本比例 p̂", "prob"], ["z_crit", "臨界值 z"], ["se", "標準誤 SE（Wald）", "prob"],
    ["margin", "誤差界限 E（Wald）", "prob"], ["lower", "下限（Wald）", "prob"], ["upper", "上限（Wald）", "prob"],
    ["wilson_center", "Wilson 中心", "prob"], ["wilson_margin", "Wilson 誤差界限", "prob"],
    ["wilson_lower", "下限（Wilson）", "prob"], ["wilson_upper", "上限（Wilson）", "prob"],
  ],
  t1: [["n", "樣本數 n"], ["mean", "樣本平均 x̄"], ["sx", "樣本標準差 Sx"], ["se", "標準誤 SE"],
    ["mu0", "假設平均 μ0"], ["t", "檢定統計量 t"], ["df", "自由度 df"]],
  t2: [["n_x", "X 樣本數"], ["n_y", "Y 樣本數"], ["mean_x", "X 平均"], ["mean_y", "Y 平均"],
    ["diff", "平均差 x̄ − ȳ"], ["sx", "X 標準差"], ["sy", "Y 標準差"], ["sp", "合併標準差 Sp"],
    ["se", "標準誤 SE"], ["t", "檢定統計量 t"], ["df", "自由度 df"]],
  tpaired: [["n", "成對數 n"], ["mean_diff", "差值平均 d̄"], ["sd", "差值標準差 Sd"], ["se", "標準誤 SE"],
    ["t", "檢定統計量 t"], ["df", "自由度 df"]],
  chi_gof: [["chi2", "檢定統計量 χ²"], ["df", "自由度 df = k − 1"]],
  chi_ind: [["chi2", "檢定統計量 χ²"], ["df", "自由度 df = (r − 1)(c − 1)"]],
};

/** 結果列：只列出引擎有回傳的鍵；檢定另加 p 值（浮動格式）。 */
export function inferRows(type, values) {
  const rows = (INFER_ROWS[type] || []).map(([key, label, kind]) => ({ key, label, kind: kind || "num" }));
  if (INFER_TYPES[type]?.test) rows.push(P_ROW);
  return rows.filter((r) => values && Object.prototype.hasOwnProperty.call(values, r.key));
}

// ================================================================ 敘述統計（describe）

/** 結果分組（引擎回傳鍵）；modes 是清單，另外顯示。 */
export const DESC_GROUPS = [
  { title: "集中趨勢 Central tendency", keys: ["n", "sum", "mean", "median", "modes"] },
  { title: "離散程度 Dispersion", keys: ["min", "max", "range", "var", "sx", "sigma_x", "cv"] },
  { title: "四分位數 Quartiles", keys: ["q1", "q3", "iqr"] },
  { title: "分配形狀 Shape", keys: ["skew", "kurt"] },
];

/**
 * 讀敘述統計表格 [X, 次數] → {X, F} 或 {error, row, col}。
 * 沿用 tables.readStatTable（單變數規則）；它的次數欄是第 3 欄，這裡換回畫面上的第 2 欄。
 */
export function readDescribeTable(cells, sep = "us") {
  const r = readStatTable(cells.map((c) => [c[0], "", c[1]]), "one_var", sep);
  if (r.error) return { ...r, col: r.col === 3 ? 2 : r.col };
  return { X: r.X, F: r.F };
}
