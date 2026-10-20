// View：商業。一個畫面四個子分頁（毛利與加成／損益兩平／百分比變動／稅額），各自是通用表單。
// 四張表單同時存在 DOM，切換分頁只是顯示／隱藏，所以各分頁輸入的內容會保留。
// 稅額分頁多一個「稅率預設值」下拉（來自 sheets.js 的 TAX_PRESETS）並顯示出處連結與查證日期。
import { TAX_PRESETS } from "../sheets.js";
import { renderForm, setValues } from "./form.js";
import { runEngineAction, watchStale, markStale } from "./run.js";

const TABS = [
  { id: "business-profit", label: "毛利與加成" },
  { id: "business-breakeven", label: "損益兩平" },
  { id: "business-pct", label: "百分比變動" },
  { id: "tax", label: "稅額" },
];
const CUSTOM = "";

function el(tag, attrs = {}, text = "") {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (text) node.textContent = text;
  return node;
}

/** 稅額分頁的預設值下拉；回傳要放在表單前面的區塊。 */
function buildPresets(panel) {
  const box = el("div", { class: "tax-presets" });
  const label = el("label", { for: "tax-preset" }, "稅率預設值 ");
  const select = el("select", { id: "tax-preset", class: "control" });
  select.append(el("option", { value: CUSTOM }, "自訂稅率"));
  for (const [name, p] of Object.entries(TAX_PRESETS)) {
    select.append(el("option", { value: name }, `${name} ${p.rate}%`));
  }
  const source = el("p", { id: "tax-source", class: "tax-source", hidden: "" });
  box.append(label, select, source);

  const rateInput = () => panel.querySelector("#f-tax-RATE");
  const showSource = (name) => {
    const p = TAX_PRESETS[name];
    source.replaceChildren();
    source.hidden = !p;
    if (!p) return;
    const a = el("a", { href: p.source_url, target: "_blank", rel: "noopener noreferrer" }, "官方出處");
    source.append(`${name}：${p.rate}%（查證日 ${p.checked}）。`, a);
  };
  select.addEventListener("change", () => {
    const p = TAX_PRESETS[select.value];
    showSource(select.value);
    if (!p) return;
    setValues("tax", { RATE: String(p.rate) });
    markStale("tax"); // 稅率改了，舊結果失效
  });
  // 稅率與預設值不同（手動改、或按「清除」/ Esc 還原）：回到「自訂」，不再宣稱出自該來源
  const sync = (e) => {
    if (e.target === select) return; // 下拉自己的操作由 change 處理
    const p = TAX_PRESETS[select.value];
    if (p && String(p.rate) !== rateInput().value.trim()) {
      select.value = CUSTOM;
      showSource(CUSTOM);
    }
  };
  for (const type of ["input", "click", "keydown"]) panel.addEventListener(type, sync);
  return box;
}

/** ctx.sheetId：要先顯示哪個子分頁；ctx.onSelect(sheetId)：切換分頁時通知 Controller 更新標題與網址。 */
export function mount(container, ctx = {}) {
  const tablist = el("div", { class: "subtabs", role: "tablist", "aria-label": "商業計算" });
  const panels = {};
  const tabs = {};
  container.replaceChildren(tablist);

  for (const t of TABS) {
    const tab = el("button", {
      type: "button", role: "tab", id: `biz-tab-${t.id}`, class: "subtab",
      "aria-controls": `biz-panel-${t.id}`, "aria-selected": "false", tabindex: "-1",
    }, t.label);
    tablist.append(tab);
    tabs[t.id] = tab;
    const panel = el("div", { role: "tabpanel", id: `biz-panel-${t.id}`, "aria-labelledby": tab.id, hidden: "" });
    container.append(panel);
    panels[t.id] = panel;
    const formBox = el("div");
    panel.append(formBox);
    renderForm(t.id, formBox, { onAction: (actionId) => runEngineAction(t.id, actionId) });
    watchStale(t.id);
    if (t.id === "tax") formBox.before(buildPresets(panel));
  }

  const select = (id, focus = false) => {
    for (const t of TABS) {
      const on = t.id === id;
      panels[t.id].hidden = !on;
      tabs[t.id].setAttribute("aria-selected", String(on));
      tabs[t.id].tabIndex = on ? 0 : -1;
    }
    if (focus) tabs[id].focus();
    ctx.onSelect?.(id);
  };
  tablist.addEventListener("click", (e) => {
    const tab = e.target.closest("[role=tab]");
    if (tab) select(tab.id.replace("biz-tab-", ""));
  });
  tablist.addEventListener("keydown", (e) => {
    const dir = { ArrowRight: 1, ArrowLeft: -1 }[e.key];
    if (!dir && e.key !== "Home" && e.key !== "End") return;
    e.preventDefault();
    const i = TABS.findIndex((t) => tabs[t.id].getAttribute("aria-selected") === "true");
    const next = e.key === "Home" ? 0 : e.key === "End" ? TABS.length - 1
      : (i + dir + TABS.length) % TABS.length;
    select(TABS[next].id, true);
  });
  select(TABS.some((t) => t.id === ctx.sheetId) ? ctx.sheetId : TABS[0].id);
}
