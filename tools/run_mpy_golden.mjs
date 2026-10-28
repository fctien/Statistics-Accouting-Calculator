// 雙執行環境 golden 測試：在 Node 上的 MicroPython（WebAssembly）跑 engine.bridge，
// (1) golden 案例：runner.run 全過，且數值與 CPython 相對差 <= 1e-9（以 max(1,|b|) 為底）
// (2) 錯誤路徑案例：回應 ok／error／field 必須與 CPython（committed expected）完全相同
// 用法：node tools/run_mpy_golden.mjs [--golden 路徑] [--errors 路徑] | --self-test
// 失敗時 exit 1。--self-test 會在暫存目錄弄壞 expected 的副本，確認工具確實 exit 1（不動 repo）。
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { ROOT, cpython, grab, loadEngine, sortDeep } from "./mpy_util.mjs";

const TOL = 1e-9;
const argv = process.argv.slice(2);
const opt = (name, dflt) => {
  const i = argv.indexOf(name);
  return i >= 0 ? argv[i + 1] : dflt;
};
const GOLDEN = opt("--golden", join(ROOT, "tests", "golden", "excel.json"));
const ERRORS = opt("--errors", join(ROOT, "tests", "golden", "error_cases.json"));
const CUSTOM = argv.includes("--golden") || argv.includes("--errors");

const MP_SRC = String.raw`
import sys, json, io
try:
    from golden import runner
    import engine.bridge
    _cases = runner.load("/bacalc/tests/golden/excel.json")
    _ad = lambda req: json.loads(engine.bridge.call(json.dumps(req)))
    _fails = runner.run(_cases, _ad)
    _dump = runner.dump(_cases, _ad)
    _errs = {}
    for _e in runner.load("/bacalc/tests/golden/error_cases.json"):
        _raw = _e["raw"] if "raw" in _e else json.dumps(_e["request"])
        _errs[_e["id"]] = json.loads(engine.bridge.call(_raw))
    print("@@MPY@@" + json.dumps({"n": len(_cases), "fails": _fails, "dump": _dump, "errs": _errs}))
except Exception as e:
    s = io.StringIO()
    sys.print_exception(e, s)
    print("@@MPY@@" + json.dumps({"error": s.getvalue()}))
`;

async function runChecks() {
  const { mp, out } = await loadEngine({
    "/bacalc/tests/golden/excel.json": GOLDEN,
    "/bacalc/tests/golden/error_cases.json": ERRORS,
  });
  mp.runPython(MP_SRC);
  const res = grab(out, "@@MPY@@");
  if (res.error) {
    console.log("MicroPython 執行失敗：\n" + res.error);
    return false;
  }
  let ok = true;

  // (1) golden：runner 失敗清單 + 與 CPython 的數值差
  const cpyDump = JSON.parse(cpython([join("tools", "golden_dump.py")]));
  let maxDiff = 0, maxId = null;
  const bad = [];
  const isNum = (x) => typeof x === "number" && Number.isFinite(x);
  for (const [id, b] of Object.entries(cpyDump)) {
    const a = res.dump[id];
    if (a === null || a === undefined || b === null) {
      if ((a ?? null) !== b || b === null) bad.push(`${id}: MicroPython=${a} CPython=${b}（無數值）`);
      continue;
    }
    if (Array.isArray(a) || Array.isArray(b)) {  // 數值 list（眾數）：長度相同、逐項相對誤差
      if (!Array.isArray(a) || !Array.isArray(b) || a.length !== b.length) {
        bad.push(`${id}: MicroPython=${JSON.stringify(a)} CPython=${JSON.stringify(b)}（list 長度或型別不同）`);
        continue;
      }
      a.forEach((x, k) => {
        if (!isNum(x) || !isNum(b[k])) { bad.push(`${id}[${k}]: 非有限數值 MicroPython=${x} CPython=${b[k]}`); return; }
        const dk = Math.abs(x - b[k]) / Math.max(1, Math.abs(b[k]));
        if (dk > maxDiff) { maxDiff = dk; maxId = id; }
        if (!(dk <= TOL)) bad.push(`${id}[${k}]: MicroPython=${x} CPython=${b[k]} diff=${dk}`);
      });
      continue;
    }
    if (typeof a === "string" || typeof b === "string") {  // 字串值（base）：完全相等
      if (a !== b) bad.push(`${id}: MicroPython=${JSON.stringify(a)} CPython=${JSON.stringify(b)}（字串不相等）`);
      continue;
    }
    if (!isNum(a) || !isNum(b)) { bad.push(`${id}: 非有限數值 MicroPython=${a} CPython=${b}`); continue; }
    const d = Math.abs(a - b) / Math.max(1, Math.abs(b));
    if (d > maxDiff) { maxDiff = d; maxId = id; }
    if (!(d <= TOL)) bad.push(`${id}: MicroPython=${a} CPython=${b} diff=${d}`);
  }
  // 防空集合／截斷：案例數必須 > 0，且兩邊 dump 的 id 集合一致（預設模式）
  if (res.n === 0) bad.push("golden 案例數為 0");
  if (!CUSTOM) {
    const ids = JSON.parse(readFileSync(GOLDEN, "utf-8")).map((c) => c.id);
    if (Object.keys(cpyDump).length !== res.n) bad.push(`CPython dump 筆數 ${Object.keys(cpyDump).length} != 案例數 ${res.n}`);
    for (const id of ids) {
      if (!(id in cpyDump)) bad.push(`CPython dump 缺少 ${id}`);
      if (!(id in res.dump)) bad.push(`MicroPython dump 缺少 ${id}`);
    }
  }
  const passed = res.n - res.fails.length;
  res.fails.forEach((f) => console.log("FAIL golden: " + f));
  bad.forEach((f) => console.log("FAIL 與 CPython 不符: " + f));
  console.log(`${passed}/${res.n} passed, max diff vs CPython ${maxDiff.toExponential(2)}` +
              (maxId ? ` (${maxId})` : ""));
  if (res.fails.length || bad.length) ok = false;

  // (2) 錯誤路徑：MicroPython 回應 === committed expected（非自訂檔時另用 CPython 即時重算，防期望值過期）
  const cases = JSON.parse(readFileSync(ERRORS, "utf-8"));
  const mism = [];
  if (cases.length === 0) mism.push("錯誤路徑案例數為 0");
  for (const c of cases) {
    if (!(c.id in res.errs)) { mism.push(`${c.id}
  MicroPython 缺少回應`); continue; }
    const a = JSON.stringify(sortDeep(res.errs[c.id])), b = JSON.stringify(sortDeep(c.expected));
    if (a !== b) mism.push(`${c.id}\n  MicroPython: ${a}\n  expected   : ${b}`);
  }
  if (!CUSTOM) {
    const live = JSON.parse(cpython([join("tools", "error_dump.py")]));
    for (const c of cases) {
      if (JSON.stringify(sortDeep(live[c.id])) !== JSON.stringify(sortDeep(c.expected))) {
        mism.push(`${c.id}\n  CPython 即時結果與 committed expected 不同（請重跑 tools/error_dump.py --write）`);
      }
    }
  }
  mism.forEach((m) => console.log("FAIL error case: " + m));
  console.log(`${cases.length - mism.length}/${cases.length} error cases identical`);
  if (mism.length) ok = false;
  return ok;
}

function selfTest() {
  const dir = mkdtempSync(join(tmpdir(), "bacalc-mpy-"));
  try {
    const g = JSON.parse(readFileSync(join(ROOT, "tests", "golden", "excel.json"), "utf-8"));
    const e = JSON.parse(readFileSync(join(ROOT, "tests", "golden", "error_cases.json"), "utf-8"));
    const gp = join(dir, "excel.json"), ep = join(dir, "error_cases.json");
    const run = (gc, ec) => {
      writeFileSync(gp, JSON.stringify(gc));
      writeFileSync(ep, JSON.stringify(ec));
      return spawnSync(process.execPath, [join(ROOT, "tools", "run_mpy_golden.mjs"), "--golden", gp, "--errors", ep],
                       { encoding: "utf-8" });
    };
    const base = run(g, e);
    const g2 = structuredClone(g); g2[0].expected = g2[0].expected * 1.5 + 1;
    const e2 = structuredClone(e); e2[0].expected.error += "X";
    const g3 = structuredClone(g); g3[0].expected = "abc";
    // 字串案例：把第一個 base 案例的期望字串弄壞，必須被擋下
    const g4 = structuredClone(g); const bi = g4.findIndex((c) => typeof c.expected === "string");
    g4[bi].expected += "0";
    const r6 = run(g4, e);
    // list 案例：把第一個 list 期望值的某項弄壞，必須被擋下
    const g5 = structuredClone(g); const li = g5.findIndex((c) => Array.isArray(c.expected));
    g5[li].expected[0] += 1;
    const r7 = run(g5, e);
    const r1 = run(g2, e), r2 = run(g, e2), r3 = run([], e), r4 = run(g3, e), r5 = run(g, []);
    const res = [
      ["未損壞副本", base.status === 0],
      ["壞 golden", r1.status === 1 && r1.stdout.includes("FAIL golden")],
      ["壞 error expected", r2.status === 1 && r2.stdout.includes("FAIL error case")],
      ["空 golden", r3.status === 1],
      ["golden expected 為字串", r4.status === 1],
      ["空 error 集合", r5.status === 1],
      ["壞字串 golden", r6.status === 1 && r6.stdout.includes("FAIL golden")],
      ["壞 list golden", r7.status === 1 && r7.stdout.includes("FAIL golden")],
    ];
    res.forEach(([n, ok]) => console.log(`${ok ? "OK  " : "FAIL"} self-test: ${n}`));
    return res.every(([, ok]) => ok);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

const main = argv.includes("--self-test") ? async () => selfTest() : runChecks;
main().then((ok) => process.exit(ok ? 0 : 1)).catch((e) => { console.error(e); process.exit(1); });
