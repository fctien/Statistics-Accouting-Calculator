// 在 Node 中驗證 web/js/py-worker.js 與 py-client.js（不需瀏覽器）：
// 以假 Worker（FakeWorker，同一執行緒、setTimeout 傳訊）載入真正的 py-worker.js，
// fetch 改讀本機檔案（file: URL），MicroPython 用 web/vendor 的 wasm。
// 檢查：(1) ready 前送出的請求會排隊、ready 後正確回應；(2) golden 51 案與錯誤路徑案例全過
// （規則同 selftest.html）；(3) --broken：web/py 不存在時狀態轉 error，佇列與之後的請求都 reject。
// 用法：node tools/check_worker.mjs [web 目錄] [--broken]；失敗 exit 1。須先 python tools/build_web.py。
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const args = process.argv.slice(2);
const BROKEN = args.includes("--broken");
const WEB = args.find((a) => !a.startsWith("--")) || join(ROOT, "web");

globalThis.fetch = async (u) => {
  try {
    return new Response(readFileSync(fileURLToPath(String(u))), { status: 200 });
  } catch {
    return new Response("", { status: 404 });
  }
};
// 假 Worker：worker 端與主執行緒端共用這個 self 物件
let toMain = null;
const workerSelf = { postMessage: (d) => setTimeout(() => toMain && toMain({ data: d }), 0) };
globalThis.self = workerSelf;
globalThis.Worker = class FakeWorker {
  constructor(url, opts) {
    if (!opts || opts.type !== "module") throw new Error("必須是 module worker");
    toMain = (ev) => this.onmessage && this.onmessage(ev);
    import(url.href).catch((e) => this.onerror && this.onerror({ message: String(e) }));
  }
  postMessage(d) { setTimeout(() => workerSelf.onmessage({ data: d }), 0); }
};

const isNum = (x) => typeof x === "number" && Number.isFinite(x);
const pick = (o) => JSON.stringify({ ok: o.ok, error: o.error, field: o.field });
const client = await import(pathToFileURL(join(WEB, "js", "py-client.js")).href);
const statuses = [];
client.onStatus((s) => statuses.push(s));
const probe = { sheet: "iconv", action: "to_eff", inputs: { NOM: 12, CY: 12 }, settings: {} };
const fails = [];

if (BROKEN) {
  const r1 = await client.callEngine(probe).then(() => "resolved", (e) => e.message);
  const r2 = await client.callEngine(probe).then(() => "resolved", (e) => e.message);
  if (client.getStatus() !== "error") fails.push("狀態不是 error：" + client.getStatus());
  if (!r1.includes("載入失敗")) fails.push("排隊中的請求未 reject：" + r1);
  if (!r2.includes("載入失敗")) fails.push("error 後的請求未 reject：" + r2);
  console.log(`statuses ${statuses.join(" -> ")}；排隊請求：${r1}`);
} else {
  const early = client.callEngine(probe); // ready 前送出
  const statusAtSend = client.getStatus();
  const golden = JSON.parse(readFileSync(join(WEB, "py", "data", "excel.json"), "utf-8"));
  const errors = JSON.parse(readFileSync(join(WEB, "py", "data", "error_cases.json"), "utf-8"));
  if (!golden.length || !errors.length) fails.push("案例數為 0");
  const resps = await Promise.all(golden.map((c) => client.callEngine(c.call)));
  golden.forEach((c, i) => {
    const r = resps[i];
    const got = r.ok ? (r.values || {})[c.expect_key] : undefined;
    const tol = isNum(c.tol) ? c.tol : 1e-9;
    const ok = r.ok && isNum(got) && isNum(c.expected) &&
      Math.abs(got - c.expected) / Math.max(1, Math.abs(c.expected)) <= tol;
    if (!ok) fails.push(`golden ${c.id}: ${JSON.stringify(r)}`);
  });
  for (const c of errors) {
    const r = "raw" in c ? await client.callEngineRaw(c.raw) : await client.callEngine(c.request);
    if (pick(r) !== pick(c.expected)) fails.push(`error ${c.id}: ${JSON.stringify(r)}`);
  }
  const e = await early;
  if (statusAtSend !== "loading" || !(e.ok && isNum(e.values.EFF))) {
    fails.push(`佇列測試失敗：送出時 ${statusAtSend}，回應 ${JSON.stringify(e)}`);
  }
  console.log(`statuses ${statuses.join(" -> ")}；佇列：送出時 ${statusAtSend}，EFF=${e.values && e.values.EFF}`);
  console.log(`golden ${golden.length}、錯誤路徑 ${errors.length} 案`);
}
fails.forEach((f) => console.log("FAIL " + f));
console.log(fails.length ? `FAIL ${fails.length} 項` : "PASS");
process.exit(fails.length ? 1 : 0);
