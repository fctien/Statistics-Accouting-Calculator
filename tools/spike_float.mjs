// Task 18 spike：驗證 engine/ 能否在 MicroPython 1.29 WebAssembly（雙精度 double）上執行。
// 用法：node tools/spike_float.mjs [--out 結果.json]
// 流程：載入 MicroPython → 把 engine/*.py、golden/*.py、excel.json 寫入 VFS（virtual file system）
//      → 在 MicroPython 內跑檢查清單 a～g → 與 CPython（子行程）結果比對 → 印出 JSON。
import { loadMicroPython } from "@micropython/micropython-webassembly-pyscript";
import { execFileSync } from "node:child_process";
import { readFileSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const HEAPSIZE = Number(process.env.MP_HEAPSIZE) || 16 * 1024 * 1024; // MicroPython heap（位元組）；套件預設 1 MB，此處預設 16 MB，可用 MP_HEAPSIZE 覆寫
const PYSTACK = 2048; // 預設值，與瀏覽器端一致

// ---- CPython 參考值（reference）：用子行程跑 python，避免手抄 ----
const PY = process.env.PYTHON || "python";
// 兩端共用的探測程式（同一份原始碼分別在 MicroPython 與 CPython 跑，輸出逐字比對）：
// 1) 以整數 LCG 產生 4000 個可重現浮點數（m/2**53*10**e，兩端 IEEE 運算結果相同），比對 '%.15g' 與 fmt.format_number
// 2) 剛好落在進位中點（tie）的值  3) business/tax 大金額（money.to_cents 用 '%.6f'）
const SHARED_PROBE = String.raw`
import json
from engine.fmt import format_number
from engine.bridge import call
_seed = 12345
_g15 = []
_fmt = []
for _i in range(4000):
    _seed = (_seed * 6364136223846793005 + 1442695040888963407) % (2 ** 64)
    _m = _seed >> 11
    _e = (_seed % 31) - 12
    _x = _m / 2 ** 53 * 10.0 ** _e
    if _i % 2:
        _x = -_x
    _g15.append('%.15g' % _x)
    _fmt.append(format_number(_x, (None, 0, 2, 4, 9)[_i % 5], ("us", "eu")[_i % 2]))
_ties = {}
for _x in (100000000000000.5, 0.125, 2 ** -7, 0.375, 2.5, 1e15 + 0.5):
    _ties[repr(_x)] = ['%.15g' % _x, '%.6f' % _x, '%.2f' % _x, format_number(_x, 2), format_number(_x, None)]
_tax = {}
for _a in (1e12, 1e15, 1e16, 1e18, 1e20, 1e22, 1e23, 1e24, 1e25, 1e30, 1e100, 1e299, 123456789.125):
    _tax[repr(_a)] = json.loads(call(json.dumps({"sheet": "business", "action": "tax",
        "inputs": {"AMOUNT": _a, "RATE": 5, "MODE": "exclusive"}, "settings": {}})))
_calc = {}
for _ex in ("2²+√9", "3×4÷2", "10!", "1e400", "π", "é+1", "abc"):
    _calc[_ex] = json.loads(call(json.dumps({"sheet": "calc", "action": "eval",
        "inputs": {"EXPR": _ex}, "settings": {}})))
# 輸入驗證錯誤路徑（bridge._InputError）
_bad = {}
for _name, _req in (
        ("tvm_N_string", {"sheet": "tvm", "action": "solve", "inputs": {"N": "abc", "IY": 5, "PV": -100, "PMT": 0, "FV": None}, "settings": {}}),
        ("bad_decimals", {"sheet": "tvm", "action": "solve", "inputs": {"N": 10, "IY": 5, "PV": -100, "PMT": 0, "FV": None}, "settings": {"decimals": 12}}),
        ("unknown_sheet", {"sheet": "nope", "action": "x", "inputs": {}, "settings": {}}),
        ("amort_N_too_big", {"sheet": "amort", "action": "schedule", "inputs": {"N": 20000, "IY": 5, "PV": 100, "PMT": -1, "FV": 0}, "settings": {}})):
    _bad[_name] = json.loads(call(json.dumps(_req)))
_bad["not_json"] = json.loads(call("not json"))
print("@@PROBE@@" + json.dumps({"g15": _g15, "fmt": _fmt, "ties": _ties, "tax": _tax, "calc": _calc, "bad": _bad}))
`;

// CPython 端：每個 golden 案例的完整 bridge 回應（含 display 字串）
const CPY_RESP_SRC = `import json, sys
sys.path.insert(0, '.')
from engine.bridge import call
from golden import runner
print(json.dumps({c['id']: call(json.dumps(c['call'])) for c in runner.load('tests/golden/excel.json')}))`;
const CPY_FMT_SRC = `import json
print(json.dumps({
 "fmt_1_3": '%.15g' % (1/3), "fmt_2675": '%.15g' % 2.675, "fmt_1e5": '%.15g' % 1e-5,
 "fmt_15e12": '%.15g' % 1.5e12, "fmt17_01": '%.17g' % 0.1,
 "fmt16_01": '%.16g' % 0.1, "fmt17_1_3": '%.17g' % (1/3), "fmt20f_01": '%.20f' % 0.1,
 "a1": repr(1e300 * 10),
 "sweep": [['%.15g' % x, '%.6f' % x, '%.2f' % x] for x in [0.1, 1 / 3, 2 / 3, 2.675, 1.005, 0.125, 0.5, 1.5, 2.5, 1e-5, 1.5e12, 123456.789, 9.995,
         -0.0049999, 1e15, 1e16 / 3, 99999.995, 0.045, 1234.5678, 7.0, 1e-300, 1e300, 3.14159265358979,
         -2.5e-7, 10.0 / 7, 1e9 + 0.5, 0.000123456789, 2 ** 52 + 0.5, 1 - 1e-12]],
 "isdigit_sup2": '\\u00b2'.isdigit()}))`;

function cpython(args) {
  return execFileSync(PY, args, { cwd: ROOT, encoding: "utf-8", maxBuffer: 64 << 20 });
}

// ---- MicroPython 端檢查程式（Python 原始碼）----
const MP_CHECKS = String.raw`
import sys, json, io
R = {}
def chk(name, fn):
    try:
        ok, val = fn()
        R[name] = {"pass": bool(ok), "value": val}
    except Exception as e:
        s = io.StringIO()
        sys.print_exception(e, s)
        R[name] = {"pass": False, "value": "EXC: " + s.getvalue()}

inf = float('inf')
# a. 雙精度（double）
# 註：brief 原文 1e300*10 == inf 在 CPython 也是 False（1e301 < 1.797e308），故 a1 改為「與 CPython 相同」，另加真正溢位 a1b
R["_a1"] = repr(1e300 * 10)
chk("a1b_overflow_1e308x10_inf", lambda: (1e308 * 10 == inf, repr(1e308 * 10)))
chk("a2_point1_plus_point2", lambda: (0.1 + 0.2 == 0.30000000000000004, repr(0.1 + 0.2)))
chk("a3_subnormal", lambda: (2 ** -1074 > 0, repr(2 ** -1074)))
chk("a4_2pow53", lambda: (2.0 ** 53 + 1 == 2.0 ** 53, repr(2.0 ** 53 + 1)))
# a+. repr 能否往返（round-trip）——影響 json 傳輸精度
def _rt():
    xs = [0.1, 1 / 3, 2.675, 1e-5, 1.5e12, 0.30000000000000004, 123456.789012345678, 2 ** -1074, 1e300]
    bad = [repr(x) for x in xs if float(repr(x)) != x]
    return (not bad, {"repr_1_3": repr(1 / 3), "repr_0.1+0.2": repr(0.1 + 0.2), "not_roundtrip": bad})
chk("a5_repr_roundtrip", _rt)
# b. 格式化（與 CPython 比對在 JS 端做）
FMT = {"fmt_1_3": '%.15g' % (1 / 3), "fmt_2675": '%.15g' % 2.675, "fmt_1e5": '%.15g' % 1e-5,
       "fmt_15e12": '%.15g' % 1.5e12, "fmt17_01": '%.17g' % 0.1}
FMT["fmt16_01"] = '%.16g' % 0.1
FMT["fmt17_1_3"] = '%.17g' % (1 / 3)
FMT["fmt20f_01"] = '%.20f' % 0.1
R["_fmt"] = FMT
# b+. 引擎實際用到的格式（%.15g、%.6f、%.2f）掃描
SWEEP = [0.1, 1 / 3, 2 / 3, 2.675, 1.005, 0.125, 0.5, 1.5, 2.5, 1e-5, 1.5e12, 123456.789, 9.995,
         -0.0049999, 1e15, 1e16 / 3, 99999.995, 0.045, 1234.5678, 7.0, 1e-300, 1e300, 3.14159265358979,
         -2.5e-7, 10.0 / 7, 1e9 + 0.5, 0.000123456789, 2 ** 52 + 0.5, 1 - 1e-12]
R["_sweep"] = [['%.15g' % x, '%.6f' % x, '%.2f' % x] for x in SWEEP]
# c. math／json
import math
chk("c1_math_funcs", lambda: (all(hasattr(math, n) for n in ("log", "exp", "sqrt", "pow", "floor")),
                             [n for n in ("log", "exp", "sqrt", "pow", "floor") if hasattr(math, n)]))
def _json_rt():
    d = {"a": 1.5, "b": [1, 2]}
    s = json.dumps(d)
    return (json.loads(s) == d, s)
chk("c2_json_roundtrip", _json_rt)
def _json_inf():
    try:
        return (True, "produces " + repr(json.dumps(inf)))
    except Exception as e:
        return (True, "raises %s: %s" % (type(e).__name__, e))
chk("c3_json_dumps_inf", _json_inf)
# d. 例外類別與深度遞迴
chk("d1_RuntimeError_exists", lambda: ("RuntimeError" in dir(__import__("builtins")), "RuntimeError"))
chk("d2_RecursionError_exists", lambda: (True, "RecursionError" in dir(__import__("builtins"))))
def _deep():
    def f(n):
        return f(n + 1) + 1
    try:
        f(0)
        return (False, "no exception")
    except RuntimeError as e:
        return (True, "RuntimeError: %s" % e)
chk("d3_deep_recursion_RuntimeError", _deep)
# e. 大整數與浮點比較
def _big1():
    v = abs(10 ** 400) <= 1e300
    return (v is False, repr(v))
chk("e1_bigint_le_float", _big1)
def _big2():
    v = (10 ** 400) == inf
    return (True, repr(v))
chk("e2_bigint_eq_inf", _big2)
# f. isdigit（只記錄）
chk("f1_isdigit_sup2", lambda: (True, '²'.isdigit()))
print("@@CHECKS@@" + json.dumps(R))
`;

const MP_GOLDEN = String.raw`
import sys, json, io
try:
    from golden import runner
    import engine.bridge
    _cases = runner.load("/bacalc/tests/golden/excel.json")
    _ad = lambda req: json.loads(engine.bridge.call(json.dumps(req)))
    _fails = runner.run(_cases, _ad)
    _dump = runner.dump(_cases, _ad)
    _resp = {c["id"]: engine.bridge.call(json.dumps(c["call"])) for c in _cases}
    print("@@GOLDEN@@" + json.dumps({"n": len(_cases), "fails": _fails, "dump": _dump, "resp": _resp}))
except Exception as e:
    s = io.StringIO()
    sys.print_exception(e, s)
    print("@@GOLDEN@@" + json.dumps({"error": s.getvalue()}))
`;

// 遞迴排序物件鍵（dict 鍵順序在 MicroPython 與 CPython 不同，比對時忽略順序）
function sortDeep(v) {
  if (Array.isArray(v)) return v.map(sortDeep);
  if (v && typeof v === "object") {
    return Object.fromEntries(Object.keys(v).sort().map((k) => [k, sortDeep(v[k])]));
  }
  return v;
}

function grab(lines, tag) {
  const l = lines.find((x) => x.startsWith(tag));
  if (!l) throw new Error("找不到輸出標記 " + tag + "\n" + lines.join("\n"));
  return JSON.parse(l.slice(tag.length));
}

async function main() {
  const out = [];
  const errs = [];
  // h. 計時：載入 MicroPython + 匯入 engine.bridge
  const t0 = performance.now();
  const mp = await loadMicroPython({
    heapsize: HEAPSIZE, pystack: PYSTACK,
    stdout: (s) => out.push(s), stderr: (s) => errs.push(s),
  });
  const tLoaded = performance.now();
  // 寫入 VFS：/bacalc/engine、/bacalc/golden、/bacalc/tests/golden/excel.json
  for (const d of ["/bacalc", "/bacalc/engine", "/bacalc/golden", "/bacalc/tests", "/bacalc/tests/golden"]) {
    mp.FS.mkdir(d);
  }
  for (const pkg of ["engine", "golden"]) {
    for (const f of readdirSync(join(ROOT, pkg)).filter((n) => n.endsWith(".py"))) {
      mp.FS.writeFile(`/bacalc/${pkg}/${f}`, readFileSync(join(ROOT, pkg, f), "utf-8"));
    }
  }
  mp.FS.writeFile("/bacalc/tests/golden/excel.json",
    readFileSync(join(ROOT, "tests", "golden", "excel.json"), "utf-8"));
  mp.runPython("import sys\nsys.path.insert(0, '/bacalc')");
  const tImp0 = performance.now();
  let importError = null;
  try {
    mp.runPython("import engine.bridge");
  } catch (e) {
    importError = String(e);
  }
  const tImported = performance.now();

  mp.runPython(MP_CHECKS);
  const checks = grab(out, "@@CHECKS@@");

  const tG0 = performance.now();
  mp.runPython(MP_GOLDEN);
  const tG1 = performance.now();
  const golden = grab(out, "@@GOLDEN@@");
  mp.runPython(SHARED_PROBE);
  const probeMp = grab(out, "@@PROBE@@");

  // ---- CPython 參考 ----
  const cpy = JSON.parse(cpython(["-c", CPY_FMT_SRC]));
  const cpyDump = JSON.parse(cpython([join("tools", "golden_dump.py")]));

  // b. 格式化比對
  checks.a1_1e300x10_same_as_cpython = { pass: checks._a1 === cpy.a1,
    value: { micropython: checks._a1, cpython: cpy.a1, note: "brief 原文期望 inf，但雙精度下 1e301 為有限值，CPython 亦同" } };
  delete checks._a1;
  const sweepBad = [];
  checks._sweep.forEach((row, i) => row.forEach((v, j) => {
    if (v !== cpy.sweep[i][j]) sweepBad.push({ i, fmt: ["%.15g", "%.6f", "%.2f"][j], micropython: v, cpython: cpy.sweep[i][j] });
  }));
  checks.b_sweep_engine_formats = { pass: sweepBad.length === 0,
    value: { values: checks._sweep.length, mismatches: sweepBad } };
  delete checks._sweep;
  for (const k of ["fmt16_01", "fmt17_1_3", "fmt20f_01"]) {
    checks["b_info_" + k] = { pass: true, value: { micropython: checks._fmt[k], cpython: cpy[k], same: checks._fmt[k] === cpy[k] } };
  }
  for (const k of ["fmt_1_3", "fmt_2675", "fmt_1e5", "fmt_15e12", "fmt17_01"]) {
    checks["b_" + k] = { pass: checks._fmt[k] === cpy[k], value: { micropython: checks._fmt[k], cpython: cpy[k] } };
  }
  delete checks._fmt;
  checks.f1_isdigit_sup2.value = { micropython: checks.f1_isdigit_sup2.value, cpython: cpy.isdigit_sup2 };

  // g. golden：失敗清單 + 與 CPython dump 的最大相對差
  let maxRel = 0, maxRelId = null;
  const mismatched = [];
  if (!golden.error) {
    for (const [id, b] of Object.entries(cpyDump)) {
      const a = golden.dump[id];
      if (a === null || a === undefined || b === null) {
        if (a !== b) mismatched.push({ id, micropython: a ?? null, cpython: b });
        continue;
      }
      const rel = b === 0 ? Math.abs(a - b) : Math.abs(a - b) / Math.abs(b);
      if (rel > maxRel) { maxRel = rel; maxRelId = id; }
    }
  }
  checks.g1_golden_fails_empty = {
    pass: !golden.error && golden.fails.length === 0,
    value: golden.error ? golden.error : { cases: golden.n, fails: golden.fails },
  };
  checks.g2_dump_vs_cpython = {
    pass: !golden.error && maxRel < 1e-9 && mismatched.length === 0,
    value: { max_rel_diff: maxRel, at: maxRelId, null_mismatch: mismatched,
             compared: Object.keys(cpyDump).length },
  };

  // b/g. 共用探測：MicroPython 與 CPython 逐項比對
  const probeCpy = grab(cpython(["-c", "import sys; sys.path.insert(0, '.')\n" + SHARED_PROBE]).split(/\r?\n/),
    "@@PROBE@@");
  const diffList = (a, b) => a.map((v, i) => [i, v, b[i]]).filter(([, v, w]) => v !== w);
  const g15d = diffList(probeMp.g15, probeCpy.g15), fmtd = diffList(probeMp.fmt, probeCpy.fmt);
  checks.b_random_15g_4000 = { pass: g15d.length === 0, value: { mismatches: g15d.length, list: g15d } };
  checks.b_random_format_number_4000 = { pass: fmtd.length === 0, value: { mismatches: fmtd.length, list: fmtd } };
  const tieD = Object.keys(probeCpy.ties).filter((k) => JSON.stringify(probeMp.ties[k]) !== JSON.stringify(probeCpy.ties[k]))
    .map((k) => ({ x: k, micropython: probeMp.ties[k], cpython: probeCpy.ties[k], cols: "%.15g,%.6f,%.2f,fmt(2),fmt(None)" }));
  checks.b_info_ties = { pass: true, value: { differing: tieD } };
  const taxD = Object.keys(probeCpy.tax).filter((k) => JSON.stringify(sortDeep(probeMp.tax[k])) !== JSON.stringify(sortDeep(probeCpy.tax[k])))
    .map((k) => ({ amount: k, micropython: probeMp.tax[k], cpython: probeCpy.tax[k] }));
  const calcD = Object.keys(probeCpy.calc).filter((k) => JSON.stringify(sortDeep(probeMp.calc[k])) !== JSON.stringify(sortDeep(probeCpy.calc[k])))
    .map((k) => ({ expr: k, micropython: probeMp.calc[k], cpython: probeCpy.calc[k] }));
  checks.g5_calc_unicode = { pass: calcD.length === 0, value: { compared: Object.keys(probeCpy.calc).length, diffs: calcD } };
  const badD = Object.keys(probeCpy.bad).filter((k) => JSON.stringify(sortDeep(probeMp.bad[k])) !== JSON.stringify(sortDeep(probeCpy.bad[k])))
    .map((k) => ({ req: k, micropython: probeMp.bad[k], cpython: probeCpy.bad[k] }));
  checks.g6_bridge_input_errors = { pass: badD.length === 0, value: { compared: Object.keys(probeCpy.bad).length, diffs: badD } };
  checks.g4_tax_large_amounts = { pass: taxD.length === 0, value: { compared: Object.keys(probeCpy.tax).length, diffs: taxD } };

  // g3. 完整 bridge 回應（含 display 格式化字串）逐字比對
  const cpyResp = JSON.parse(cpython(["-c", CPY_RESP_SRC]));
  const respDiff = [];
  if (!golden.error) {
    for (const [id, r] of Object.entries(cpyResp)) {
      const a = JSON.parse(golden.resp[id]), b = JSON.parse(r);
      if (JSON.stringify(sortDeep(a.display)) !== JSON.stringify(sortDeep(b.display)) || a.ok !== b.ok) {
        respDiff.push({ id, micropython: a.display, cpython: b.display });
      }
    }
  }
  checks.g3_display_strings_same = { pass: !golden.error && respDiff.length === 0,
    value: { compared: Object.keys(cpyResp).length, diffs: respDiff } };

  const result = {
    env: { node: process.version, package: "@micropython/micropython-webassembly-pyscript@1.29.0-6",
           heapsize: HEAPSIZE, pystack: PYSTACK, cpython: cpython(["--version"]).trim() },
    import_error: importError,
    timing_ms: {
      load_micropython: +(tLoaded - t0).toFixed(1),
      import_engine_bridge: +(tImported - tImp0).toFixed(1),
      load_plus_import_total: +(tImported - t0).toFixed(1),
      golden_run_and_dump: +(tG1 - tG0).toFixed(1),
    },
    checks,
    all_pass: Object.values(checks).every((c) => c.pass),
    stderr: errs,
  };
  const outIdx = process.argv.indexOf("--out");
  if (outIdx > 0) writeFileSync(process.argv[outIdx + 1], JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result, null, 2));
}

main().catch((e) => { console.error(e); process.exit(1); });
