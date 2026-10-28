// View 共用（統計頁：敘述統計、機率分配、信賴區間與檢定）：欄位顯示／隱藏、結果清單、
// 機率類欄位的浮動格式請求、分配圖（SVG）。數字一律來自引擎的 display，這裡不格式化數字。
import { callEngine } from "../py-client.js";
import * as settingsStore from "../settings.js";
import { floatSettings, floatKeys, chartGeometry } from "../stat.js";

const SVG_NS = "http://www.w3.org/2000/svg";

export function el(tag, attrs = {}, text = "") {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    node.setAttribute(k, v === true ? "" : String(v));
  }
  if (text) node.textContent = text;
  return node;
}

function svg(tag, attrs = {}) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
  return node;
}

/** 表單內某欄位的控制項（form.js 的 id 規則 f-<sheet>-<field>）。 */
export function ctrl(form, sheetId, fieldId) {
  return form.querySelector("#" + CSS.escape(`f-${sheetId}-${fieldId}`));
}

/** 只顯示 visible 中的欄位（其餘 .field 加 hidden；值保留，切回來還在）。 */
export function showOnly(form, visible) {
  const keep = new Set(visible);
  for (const wrap of form.querySelectorAll(".fields .field")) wrap.hidden = !keep.has(wrap.dataset.field);
}

/** 動作＝選單決定時，只留主要的「計算」鈕（其餘動作鈕隱藏）。 */
export function onlyPrimaryButton(form) {
  for (const b of form.querySelectorAll(".actions button[data-action]")) {
    if (b.type !== "submit") b.hidden = true;
  }
}

/** 同一請求改用浮動小數位數（機率、p 值不可被 2 位小數吃掉）；失敗回傳 null。 */
export async function fetchFloat(sheet, action, inputs) {
  try {
    const r = await callEngine({ sheet, action, inputs, settings: floatSettings(settingsStore.toEngine()) });
    return r && r.ok === true ? r : null;
  } catch (e) {
    return null;
  }
}

/**
 * 結果清單 <dl>：rows 為 [{key, label, kind}]；機率類（prob、density）用 floatDisplay，
 * 其餘用一般 display（依使用者小數位數）。浮動格式取得失敗時，機率類顯示「無法取得」而不是 2 位小數。
 */
export function resultList(rows, display, floatDisplay, id) {
  const fl = new Set(floatKeys(rows));
  const dl = el("dl", { class: "stat-result", id });
  for (const r of rows) {
    const text = fl.has(r.key) ? (floatDisplay ? floatDisplay[r.key] : null) : display[r.key];
    const dt = el("dt", {}, r.label);
    const dd = el("dd", { "data-key": r.key, class: `kind-${r.kind}` }, text ?? "（無法取得浮動格式，請重新計算）");
    dl.append(dt, dd);
  }
  return dl;
}

/**
 * 分配圖（SVG）。opts：{points, discrete, shadeTo, marker, hitK, caption, outsideNote}。
 * 曲線／長條高度都是引擎算出的 pdf／pmf 值；這裡只做座標換算與繪製。
 */
export function chartFigure(opts) {
  const W = 360;
  const H = 180;
  const g = chartGeometry({ ...opts, width: W, height: H });
  const fig = el("figure", { class: "stat-chart", id: "dist-chart" });
  const root = svg("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": opts.caption });
  root.append(svg("line", { x1: 0, y1: g.base, x2: W, y2: g.base, class: "axis" }));
  if (opts.discrete) {
    for (const b of g.bars) {
      const cls = b.k === opts.hitK ? "bar hit" : b.shaded ? "bar shaded" : "bar";
      root.append(svg("rect", { x: b.x, y: b.y, width: b.w, height: b.h, class: cls }));
    }
  } else {
    if (g.area) root.append(svg("path", { d: g.area, class: "area" }));
    root.append(svg("path", { d: g.curve, class: "curve" }));
  }
  if (g.markerX !== null) {
    root.append(svg("line", { x1: g.markerX, y1: 4, x2: g.markerX, y2: g.base, class: "marker" }));
  }
  for (const [i, t] of g.ticks.entries()) {
    const label = svg("text", { x: t.x, y: H - 6, class: "tick", "text-anchor": i ? "end" : "start" });
    // 端點標籤：引擎格式化的文字（tickLabels）；離散的 k 是整數，直接顯示
    label.textContent = opts.tickLabels?.[i] ?? (Number.isInteger(t.value) ? String(t.value) : "");
    root.append(label);
  }
  const cap = el("figcaption", {}, opts.caption + (opts.outsideNote ? `（${opts.outsideNote}）` : ""));
  fig.append(root, cap);
  return fig;
}

/** 目前表單的狀態區（結果與警告都放這裡；markStale／重新計算時自動清空）。 */
export function statusBox(form) {
  return form.querySelector(".form-status");
}
