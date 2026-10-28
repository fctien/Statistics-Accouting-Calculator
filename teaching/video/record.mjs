// 錄影（screen recording）：依 build/script.json 的 SEGMENTS 用 Playwright 實際操作 App 並錄成 webm。
// 用法：node teaching/video/record.mjs <base_url> [--only id,id] [--dry]
//   base_url  例 http://127.0.0.1:8765/（伺服器由 run_video.py 啟動與關閉）
//   --dry     不錄影、快速跑完所有動作並核對 expect（開發腳本用）
// 每段一個新的瀏覽器情境（context）＋ recordVideo（1280×640；合成時底部加 80px 字幕帶成 1280×720）→ build/seg-XX.webm；
// 段落開始前先載入 start 路由並等引擎「就緒」，這段載入時間記在 build/record.json 的 trim，合成時剪掉。
// 畫面加上游標圓點（跟隨滑鼠）、點擊漣漪、元素外框 highlight 與段落字卡（2 秒）。
// 動作節奏對齊旁白：第 i 個動作最早在 (旁白秒數 × i / 動作數 × 0.85) 開始；段落至少錄到旁白長度＋0.5 秒。
// 每段錄完核對 expect（與中途的 check），不符就整個失敗、不產出錯誤影片（exit 1）。
import { createRequire } from "module";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const require = createRequire(path.resolve(fileURLToPath(import.meta.url), "../../../../node_modules/"));
const { chromium } = require("playwright");

const HERE = path.dirname(fileURLToPath(import.meta.url));
const BUILD = path.join(HERE, "build");
const W = 1280, H = 640; // App 畫面；字幕帶在合成時另加，不蓋住任何 UI

const args = process.argv.slice(2);
const BASE = args.find((a) => /^https?:/.test(a)) || "http://127.0.0.1:8765/";
const DRY = args.includes("--dry");
const onlyIdx = args.indexOf("--only");
const ONLY = onlyIdx >= 0 ? args[onlyIdx + 1].split(",") : null;

const SEGMENTS = JSON.parse(fs.readFileSync(path.join(BUILD, "script.json"), "utf-8"));
const durPath = path.join(BUILD, "durations.json");
const DUR = fs.existsSync(durPath) ? JSON.parse(fs.readFileSync(durPath, "utf-8")) : {};

// 注入頁面的游標、漣漪、外框、字卡（只影響錄影畫面，不改 App 原始碼）
const OVERLAY_JS = `
(() => {
  const css = \`
  #video-cursor{position:fixed;z-index:2147483647;width:22px;height:22px;margin:-11px 0 0 -11px;border-radius:50%;
    background:rgba(231,76,60,.55);border:2px solid #fff;box-shadow:0 0 0 2px rgba(231,76,60,.8);pointer-events:none;
    left:-50px;top:-50px;transition:transform .12s}
  #video-cursor.down{transform:scale(.7)}
  .video-ripple{position:fixed;z-index:2147483646;width:44px;height:44px;margin:-22px 0 0 -22px;border-radius:50%;
    border:3px solid rgba(231,76,60,.9);pointer-events:none;animation:vr .5s ease-out forwards}
  @keyframes vr{from{transform:scale(.3);opacity:1}to{transform:scale(1.4);opacity:0}}
  #video-hl{position:fixed;z-index:2147483645;border:3px solid #e67e22;border-radius:8px;pointer-events:none;
    box-shadow:0 0 0 4px rgba(230,126,34,.25);transition:all .2s}
  #video-title{position:fixed;z-index:2147483644;left:50%;top:38%;transform:translate(-50%,-50%);
    background:rgba(20,40,80,.92);color:#fff;font:600 40px "Microsoft JhengHei",sans-serif;padding:28px 56px;
    border-radius:14px;box-shadow:0 10px 40px rgba(0,0,0,.35);pointer-events:none;white-space:nowrap}
  #video-card{position:fixed;inset:0;z-index:2147483640;background:linear-gradient(135deg,#14284f,#1f4e8c);
    color:#fff;font-family:"Microsoft JhengHei",sans-serif;display:flex;flex-direction:column;justify-content:center;
    padding:0 120px;box-sizing:border-box}
  #video-card h1{font-size:54px;margin:0 0 36px}
  #video-card li{font-size:28px;line-height:1.9}
  #video-card .url{margin-top:40px;font:600 30px Consolas,monospace;color:#ffd479}\`;
  const add = () => {
    if (document.getElementById("video-style")) return;
    const st = document.createElement("style"); st.id = "video-style"; st.textContent = css;
    document.head.append(st);
    const c = document.createElement("div"); c.id = "video-cursor"; document.body.append(c);
    addEventListener("mousemove", (e) => { c.style.left = e.clientX + "px"; c.style.top = e.clientY + "px"; }, true);
    addEventListener("mousedown", (e) => {
      c.classList.add("down");
      const r = document.createElement("div"); r.className = "video-ripple";
      r.style.left = e.clientX + "px"; r.style.top = e.clientY + "px"; document.body.append(r);
      setTimeout(() => r.remove(), 600);
    }, true);
    addEventListener("mouseup", () => c.classList.remove("down"), true);
  };
  if (document.readyState === "loading") addEventListener("DOMContentLoaded", add); else add();
})();`;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let mouse = { x: W / 2, y: H / 2 };

async function moveTo(page, loc) {
  await loc.scrollIntoViewIfNeeded();
  const box = await loc.boundingBox();
  if (!box) throw new Error("元素不可見");
  const x = box.x + box.width / 2, y = box.y + Math.min(box.height / 2, 18);
  const dist = Math.hypot(x - mouse.x, y - mouse.y);
  await page.mouse.move(x, y, { steps: DRY ? 1 : Math.max(8, Math.min(30, Math.round(dist / 25))) });
  mouse = { x, y };
}

async function textOf(page, sel) {
  return page.locator(sel).first().evaluate((e) => {
    const isField = ["INPUT", "TEXTAREA", "SELECT"].includes(e.tagName);
    return (isField ? e.value : e.innerText || e.textContent || "").replace(/\s+/g, " ").trim();
  });
}

async function check(page, sel, text, where) {
  let got = "";
  for (let t = 0; t < 20; t++) { // 最多等 4 秒（計算是非同步）
    got = await textOf(page, sel).catch(() => "");
    if (got.includes(text) || got.replace(/\s/g, "").includes(text.replace(/\s/g, ""))) return;
    await sleep(200);
  }
  throw new Error(`${where}：${sel} 應含「${text}」，實際「${got.slice(0, 120)}」`);
}

async function highlight(page, sel, ms) {
  const loc = page.locator(sel).first();
  await loc.scrollIntoViewIfNeeded();
  await moveTo(page, loc);
  await page.evaluate((s) => {
    const e = document.querySelector(s);
    const r = e.getBoundingClientRect();
    let hl = document.getElementById("video-hl");
    if (!hl) { hl = document.createElement("div"); hl.id = "video-hl"; document.body.append(hl); }
    Object.assign(hl.style, { left: r.left - 6 + "px", top: r.top - 6 + "px", width: r.width + 12 + "px", height: r.height + 12 + "px", display: "block" });
  }, sel.replace(/:text-is\(.*\)$/, ""));
  await sleep(DRY ? 50 : ms);
  await page.evaluate(() => { const hl = document.getElementById("video-hl"); if (hl) hl.style.display = "none"; });
}

async function showCard(page, a) {
  await page.evaluate((a) => {
    let c = document.getElementById("video-card");
    if (!c) { c = document.createElement("div"); c.id = "video-card"; document.body.append(c); }
    c.innerHTML = "";
    const h = document.createElement("h1"); h.textContent = a.title; c.append(h);
    const ul = document.createElement("ul");
    for (const line of a.lines || []) { const li = document.createElement("li"); li.textContent = line; ul.append(li); }
    c.append(ul);
    if (a.url) { const u = document.createElement("div"); u.className = "url"; u.textContent = a.url; c.append(u); }
  }, a);
}

async function titleCard(page, title) {
  await page.evaluate((t) => {
    const d = document.createElement("div"); d.id = "video-title"; d.textContent = t; document.body.append(d);
  }, title);
  await sleep(DRY ? 50 : 2000);
  await page.evaluate(() => document.getElementById("video-title")?.remove());
}

async function selectOpt(page, sel, value) {
  const loc = page.locator(sel).first();
  const values = await loc.evaluate((e) => [...e.options].map((o) => [o.value, o.text]));
  let v = values.find((o) => o[0] === value);
  if (!v) v = values.find((o) => o[1].startsWith(value));
  if (!v) throw new Error(`${sel} 沒有選項 ${value}`);
  await loc.selectOption(v[0]);
}

async function gotoRoute(page, route) {
  // 優先點畫面上的導覽連結（觀眾看得到操作），找不到才直接改網址
  const link = page.locator(`#page-tabs a[href="#${route}"], #side-nav a[href="#${route}"], a#settings-link[href="#${route}"]`);
  const n = await link.count();
  for (let i = 0; i < n; i++) {
    const l = link.nth(i);
    if (await l.isVisible()) { await moveTo(page, l); await l.click(); await sleep(DRY ? 100 : 700); return; }
  }
  // 子頁不在目前的側欄：先點頁籤再點子項目
  const top = route.split("/")[0];
  const tab = page.locator(`#page-tabs a[href^="#${top}/"]`).first();
  if (route.includes("/") && await tab.count()) {
    await moveTo(page, tab); await tab.click(); await sleep(DRY ? 100 : 600);
    const sub = page.locator(`#side-nav a[href="#${route}"]`).first();
    if (await sub.count() && await sub.isVisible()) { await moveTo(page, sub); await sub.click(); await sleep(DRY ? 100 : 700); return; }
  }
  await page.evaluate((r) => { location.hash = "#" + r; }, route);
  await sleep(DRY ? 100 : 700);
}

async function runAction(page, a, where) {
  if ("goto" in a) return gotoRoute(page, a.goto);
  if ("click" in a) {
    const loc = page.locator(a.click).first();
    await moveTo(page, loc); await loc.click(); await sleep(DRY ? 100 : 450); return;
  }
  if ("fill" in a) {
    const loc = page.locator(a.fill).first();
    await moveTo(page, loc); await loc.click(); await loc.fill("");
    await loc.pressSequentially(a.value, { delay: DRY ? 0 : 70 });
    await loc.dispatchEvent("change");
    await sleep(DRY ? 50 : 250); return;
  }
  if ("select" in a) {
    const loc = page.locator(a.select).first();
    await moveTo(page, loc); await selectOpt(page, a.select, a.value); await sleep(DRY ? 100 : 500); return;
  }
  if ("press" in a) { await page.keyboard.press(a.press); await sleep(DRY ? 50 : 300); return; }
  if ("wait" in a) { await sleep(DRY ? Math.min(a.wait, 300) : a.wait); return; }
  if ("highlight" in a) return highlight(page, a.highlight, a.ms || 1500);
  if ("card" in a) return showCard(page, a);
  if ("uncard" in a) { await page.evaluate(() => document.getElementById("video-card")?.remove()); await sleep(DRY ? 50 : 400); return; }
  if ("check" in a) return check(page, a.check, a.text, where);
  throw new Error(`${where}：未知動作 ${JSON.stringify(a)}`);
}

async function waitReady(page) {
  await page.waitForFunction(() => document.getElementById("py-status")?.className.includes("pill-ready"), null, { timeout: 90000 });
}

async function recordSegment(browser, seg, idx) {
  const name = `seg-${String(idx + 1).padStart(2, "0")}`;
  const ctxOpts = { viewport: { width: W, height: H }, deviceScaleFactor: 1, acceptDownloads: true, locale: "zh-TW" };
  if (!DRY) ctxOpts.recordVideo = { dir: path.join(BUILD, "raw"), size: { width: W, height: H } };
  const ctx = await browser.newContext(ctxOpts);
  await ctx.addInitScript(OVERLAY_JS);
  const t0 = Date.now();
  const page = await ctx.newPage();
  page.on("pageerror", (e) => console.error(`[${seg.id}] pageerror: ${e.message}`));
  await page.goto(BASE + "index.html#" + seg.start);
  await waitReady(page);
  await sleep(DRY ? 100 : 800); // 等畫面穩定
  mouse = { x: W / 2, y: H / 2 };
  await page.mouse.move(mouse.x, mouse.y);
  const trim = (Date.now() - t0) / 1000;
  const tStart = Date.now();
  const narr = DUR[seg.id] || 0;
  const where = `${name} ${seg.id}`;
  await titleCard(page, seg.title);
  const n = seg.actions.length;
  for (let i = 0; i < n; i++) {
    if (!DRY && narr) {
      const due = 2000 + (narr * 1000 - 2000) * 0.85 * (i / n);
      const left = due - (Date.now() - tStart);
      if (left > 0) await sleep(left);
    }
    await runAction(page, seg.actions[i], `${where} 第 ${i + 1} 步`);
  }
  for (const e of seg.expect) {
    if (e.at === "check") continue; // 已由中途的 check 動作核對
    await check(page, e.selector, e.text, `${where} expect`);
  }
  if (!DRY) {
    const left = (narr + 0.5) * 1000 - (Date.now() - tStart);
    if (left > 0) await sleep(left);
  }
  const length = (Date.now() - tStart) / 1000;
  const video = page.video();
  await ctx.close();
  let file = null;
  if (video) {
    file = path.join(BUILD, name + ".webm");
    await video.saveAs(file);
    await video.delete();
  }
  console.log(`${where} OK 錄製 ${length.toFixed(1)} 秒（旁白 ${narr.toFixed(1)} 秒，剪掉開頭 ${trim.toFixed(1)} 秒）`);
  return { id: seg.id, name, trim, length, narration: narr, file };
}

async function main() {
  fs.mkdirSync(BUILD, { recursive: true });
  const browser = await chromium.launch();
  const results = [];
  try {
    for (let i = 0; i < SEGMENTS.length; i++) {
      if (ONLY && !ONLY.includes(SEGMENTS[i].id)) continue;
      results.push(await recordSegment(browser, SEGMENTS[i], i));
    }
  } finally {
    await browser.close();
  }
  if (!DRY) {
    const recPath = path.join(BUILD, "record.json");
    const prev = ONLY && fs.existsSync(recPath) ? JSON.parse(fs.readFileSync(recPath, "utf-8")) : [];
    const merged = SEGMENTS.map((s) => results.find((r) => r.id === s.id) || prev.find((r) => r.id === s.id)).filter(Boolean);
    fs.writeFileSync(recPath, JSON.stringify(merged, null, 1));
  }
  console.log(`完成 ${results.length} 段${DRY ? "（dry run，未錄影）" : ""}`);
}

main().catch((e) => { console.error("錄影失敗：" + e.message); process.exit(1); });
