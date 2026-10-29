// 教材截圖（screenshot）：用上層資料夾已安裝的 Playwright 驅動本機 Chrome（headless），
// 對 http://localhost:8765/ 實際操作 App 並存到 teaching/assets/
// 用法：先 python tools/build_web.py，再 python -m http.server 8765 -d web，
//       然後 node teaching/deck/capture_shots.mjs
// 不安裝任何套件；Chrome 路徑可用環境變數 CHROME 指定
import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.resolve(HERE, "..", "assets");
const BASE = process.env.BACALC_URL || "http://localhost:8765/";
const CHROME = process.env.CHROME || "C:/Program Files/Google/Chrome/Application/chrome.exe";

async function ready(page) {
  // 等 MicroPython 就緒（#py-status 顯示就緒）
  await page.waitForFunction(() => /就緒/.test(document.querySelector("#py-status")?.textContent || ""),
    null, { timeout: 30000 });
}

async function open(page, route) {
  await page.goto(BASE + "#" + route);
  await ready(page);
  await page.waitForSelector("#sheet form, #sheet .calc-expr, #sheet section", { timeout: 10000 });
}

async function fill(page, id, value) {
  const loc = page.locator("#" + id);
  await loc.fill(value);
  await loc.press("Tab"); // 觸發 change（正負號轉成方向鈕）
}

async function clickAction(page, label) {
  await page.locator("#sheet .actions button", { hasText: label }).first().click();
  await page.waitForTimeout(800);
}

async function snap(page, name) {
  const file = path.join(OUT, name);
  await page.screenshot({ path: file, fullPage: false });
  console.log("saved", file);
}

const browser = await chromium.launch({ executablePath: CHROME, headless: true });
try {
  // ---- 桌面版 1280×720
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1.5 });
  const page = await ctx.newPage();

  // TVM：房貸 PMT
  await open(page, "tvm");
  await fill(page, "f-tvm-N", "360");
  await fill(page, "f-tvm-IY", "6");
  await fill(page, "f-tvm-PV", "300000");
  await fill(page, "f-tvm-FV", "0");
  await clickAction(page, "計算");
  await snap(page, "tvm_result.png");

  // AMORT：帶入攤還後算完整攤還表
  await page.locator("#tvm-to-amort").click();
  await page.waitForTimeout(800);
  await fill(page, "f-amort-P1", "1");
  await fill(page, "f-amort-P2", "12");
  await clickAction(page, "計算區間");
  await clickAction(page, "完整攤還表");
  await page.waitForSelector("#amort-table");
  await page.evaluate(() => document.querySelector('.field[data-field="BAL"]').scrollIntoView({ block: "start" }));
  await snap(page, "amort_table.png");

  // CF：NPV 與 IRR
  await open(page, "cf");
  await fill(page, "f-cashflow-CF0", "-10000");
  const cells = page.locator("#cf-table input.grid-cell");
  const amounts = ["3000", "4200", "6800", "-1500"];
  for (let i = 0; i < amounts.length; i++) await cells.nth(i * 2).fill(amounts[i]);
  await fill(page, "f-cashflow-I", "10");
  await clickAction(page, "NPV");
  await clickAction(page, "IRR");
  await page.evaluate(() => document.querySelector("#cf-table").scrollIntoView({ block: "start" }));
  await snap(page, "cf_irr.png");

  // CALC：兩筆算式進紙帶
  await open(page, "calc");
  for (const expr of ["2+3*4", "1798.65*360", "(1+0.06/12)^12-1"]) {
    await page.locator("#calc-expr").fill(expr);
    await page.locator("#calc-expr").press("Enter");
    await page.waitForTimeout(600);
  }
  await page.evaluate(() => document.querySelector("#calc-tape-list").scrollIntoView({ block: "end" }));
  await snap(page, "calc_tape.png");

  // v0.2 工程頁：科學計算機 sin(30)（DEG）
  await open(page, "eng/calc");
  await page.locator("#calc-expr").fill("sin(30)");
  await page.locator("#calc-expr").press("Enter");
  await page.waitForTimeout(800);
  await page.evaluate(() => window.scrollTo(0, 0));
  await snap(page, "eng_calc.png");

  // v0.2 統計頁：常態分配累積機率 x=1.96 與分配圖
  await open(page, "stat/dist");
  await page.locator("#f-dist-DIST").selectOption("normal");
  await page.locator("#f-dist-FUNC").selectOption("cdf");
  await fill(page, "f-dist-MU", "0");
  await fill(page, "f-dist-SIGMA", "1");
  await fill(page, "f-dist-X", "1.96");
  await clickAction(page, "計算");
  await page.waitForTimeout(800);
  await page.evaluate(() => document.querySelector("#dist-result").scrollIntoView({ block: "start" }));
  await snap(page, "stat_dist.png");

  // v0.2 統計頁：兩樣本 t 檢定（5..9 對 3..7）與結論
  await open(page, "stat/infer");
  await page.locator("#f-infer-TYPE").selectOption("t2");
  await page.waitForTimeout(300);
  for (let i = 0; i < 5; i++) {
    await page.locator("#infer-table-r" + (i + 1) + "c1").fill(String(5 + i));
    await page.locator("#infer-table-r" + (i + 1) + "c2").fill(String(3 + i));
  }
  await clickAction(page, "計算");
  await page.evaluate(() => document.querySelector("#infer-result").scrollIntoView({ block: "center" }));
  await snap(page, "stat_infer.png");

  // 設定：捲到「關於」
  await open(page, "settings");
  await page.waitForTimeout(1500); // 等啟動計時填入
  await page.locator("#s-about-title").scrollIntoViewIfNeeded();
  await snap(page, "settings_about.png");
  await ctx.close();

  // ---- 手機版 375×812
  const m = await browser.newContext({
    viewport: { width: 375, height: 812 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true,
  });
  const mp = await m.newPage();
  await open(mp, "tvm");
  await fill(mp, "f-tvm-N", "360");
  await fill(mp, "f-tvm-IY", "6");
  await fill(mp, "f-tvm-PV", "300000");
  await fill(mp, "f-tvm-FV", "0");
  await clickAction(mp, "計算");
  await snap(mp, "mobile_tvm.png");
  // v0.2 手機版：工程頁與底部三分頁
  await open(mp, "eng/calc");
  await mp.locator("#calc-expr").fill("sin(30)");
  await mp.locator("#calc-expr").press("Enter");
  await mp.waitForTimeout(800);
  await snap(mp, "mobile_nav.png");
  await m.close();
} finally {
  await browser.close();
}
