// MicroPython（WebAssembly）載入共用工具：載入直譯器、把 engine/、golden/ 與測試資料寫入 VFS。
import { loadMicroPython } from "@micropython/micropython-webassembly-pyscript";
import { execFileSync } from "node:child_process";
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

export const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const HEAPSIZE = Number(process.env.MP_HEAPSIZE) || 16 * 1024 * 1024; // MicroPython heap（位元組）
const PYSTACK = 2048;
export const PY = process.env.PYTHON || "python";

/** 執行 CPython 並回傳 stdout（UTF-8）。 */
export function cpython(args) {
  return execFileSync(PY, args, {
    cwd: ROOT, encoding: "utf-8", maxBuffer: 64 << 20,
    env: { ...process.env, PYTHONIOENCODING: "utf-8" },
  });
}

/** 載入 MicroPython，寫入 engine/、golden/ 與 dataFiles（{vfs 路徑: 本機路徑}），回傳 {mp, out, errs}。 */
export async function loadEngine(dataFiles = {}) {
  const out = [];
  const errs = [];
  const mp = await loadMicroPython({
    heapsize: HEAPSIZE, pystack: PYSTACK,
    stdout: (s) => out.push(s), stderr: (s) => errs.push(s),
  });
  const dirs = new Set(["/bacalc", "/bacalc/engine", "/bacalc/golden"]);
  for (const p of Object.keys(dataFiles)) {
    let d = dirname(p);
    const chain = [];
    while (d !== "/" && d !== ".") { chain.unshift(d); d = dirname(d); }
    chain.forEach((x) => dirs.add(x));
  }
  for (const d of [...dirs].sort((a, b) => a.length - b.length)) mp.FS.mkdir(d);
  for (const pkg of ["engine", "golden"]) {
    for (const f of readdirSync(join(ROOT, pkg)).filter((n) => n.endsWith(".py"))) {
      mp.FS.writeFile(`/bacalc/${pkg}/${f}`, readFileSync(join(ROOT, pkg, f), "utf-8"));
    }
  }
  for (const [vfs, local] of Object.entries(dataFiles)) {
    mp.FS.writeFile(vfs, readFileSync(local, "utf-8"));
  }
  mp.runPython("import sys\nsys.path.insert(0, '/bacalc')");
  return { mp, out, errs };
}

/** 從輸出行中取出 tag 之後的 JSON。 */
export function grab(lines, tag) {
  const l = lines.find((x) => x.startsWith(tag));
  if (!l) throw new Error("找不到輸出標記 " + tag + "\n" + lines.join("\n"));
  return JSON.parse(l.slice(tag.length));
}

/** 遞迴排序物件鍵（dict 鍵順序在兩個執行環境不同，比對時忽略順序）。 */
export function sortDeep(v) {
  if (Array.isArray(v)) return v.map(sortDeep);
  if (v && typeof v === "object") {
    return Object.fromEntries(Object.keys(v).sort().map((k) => [k, sortDeep(v[k])]));
  }
  return v;
}
