// backup.js 測試：匯出形狀、validateImport 各分支、normalizeData、mergeData（merge／replace）、importBackup。
import test from "node:test";
import assert from "node:assert/strict";

import {
  makeExport, validateImport, normalizeData, mergeData, importBackup, isoTaipei, localStamp,
  backupFilename, emptyData, MAX_TAPE,
} from "../../web/js/storage/backup.js";

const sc = (id, name, at, extra = {}) => ({
  id, worksheet: "tvm", name, inputs: { N: { text: "10", stale: false } }, updated_at: at, ...extra,
});
const entry = (ts, expr = "1+1", value = 2) => ({ expr, value, display: String(value), ts });
const good = (over = {}) => ({
  app: "BACalc", schema: 1, exported_at: "2026-10-19T10:00:00+08:00",
  data: { settings: { decimals: 4 }, scenarios: [sc("a", "A", "2026-10-19T10:00:00+08:00")], tape: [entry(1)], memory: { M1: 5 }, ...over },
});

test("isoTaipei：UTC 加 8 小時並標 +08:00", () => {
  assert.equal(isoTaipei(Date.UTC(2026, 9, 19, 2, 0, 0)), "2026-10-19T10:00:00+08:00");
  assert.equal(isoTaipei(new Date(Date.UTC(2026, 11, 31, 20, 30, 15))), "2027-01-01T04:30:15+08:00");
});

test("localStamp 與備份檔名格式", () => {
  assert.match(localStamp(Date.now()), /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/);
  assert.match(backupFilename(Date.now()), /^bacalc-backup-\d{8}\.json$/);
});

test("makeExport：app、schema、exported_at、四個資料區", () => {
  const data = { settings: { a: 1 }, scenarios: [], tape: [], memory: {} };
  const out = makeExport(data, Date.UTC(2026, 9, 19, 2, 0, 0));
  assert.deepEqual(Object.keys(out), ["app", "schema", "exported_at", "data"]);
  assert.equal(out.app, "BACalc");
  assert.equal(out.schema, 1);
  assert.equal(out.exported_at, "2026-10-19T10:00:00+08:00");
  assert.deepEqual(out.data, data);
});

test("validateImport：合格", () => {
  assert.deepEqual(validateImport(good()), { ok: true });
});

test("validateImport：拒絕非物件、app 不符、schema 不符、缺 data", () => {
  for (const bad of [null, 5, "x", [], undefined]) assert.equal(validateImport(bad).ok, false);
  const a = validateImport({ ...good(), app: "Other" });
  assert.equal(a.ok, false);
  assert.match(a.error, /BACalc/);
  assert.equal(validateImport({ ...good(), schema: 2 }).ok, false);
  assert.match(validateImport({ ...good(), schema: "1" }).error, /schema/);
  const noData = good();
  delete noData.data;
  assert.equal(validateImport(noData).ok, false);
  assert.equal(validateImport({ ...good(), data: [] }).ok, false);
});

test("validateImport：data 子欄位型別錯誤", () => {
  assert.equal(validateImport(good({ settings: [] })).ok, false);
  assert.equal(validateImport(good({ scenarios: {} })).ok, false);
  assert.equal(validateImport(good({ tape: "x" })).ok, false);
  assert.equal(validateImport(good({ memory: [] })).ok, false);
  const missing = good();
  delete missing.data.memory;
  assert.match(validateImport(missing).error, /memory/);
});

test("validateImport：情境項目缺欄位或型別錯、id 重複", () => {
  const base = sc("a", "A", "2026-10-19T10:00:00+08:00");
  for (const k of ["id", "worksheet", "name", "updated_at"]) {
    const s = { ...base };
    delete s[k];
    const r = validateImport(good({ scenarios: [s] }));
    assert.equal(r.ok, false, k);
    assert.match(r.error, new RegExp(k));
    assert.equal(validateImport(good({ scenarios: [{ ...base, [k]: 5 }] })).ok, false);
    assert.equal(validateImport(good({ scenarios: [{ ...base, [k]: "" }] })).ok, false);
  }
  const noInputs = { ...base };
  delete noInputs.inputs;
  assert.match(validateImport(good({ scenarios: [noInputs] })).error, /inputs/);
  assert.equal(validateImport(good({ scenarios: [{ ...base, inputs: [] }] })).ok, false);
  assert.equal(validateImport(good({ scenarios: [null] })).ok, false);
  assert.match(validateImport(good({ scenarios: [base, base] })).error, /重複/);
});

test("validateImport：紙帶超過 500 筆拒絕，500 筆可以", () => {
  const mk = (n) => Array.from({ length: n }, (_, i) => entry(i));
  assert.equal(validateImport(good({ tape: mk(MAX_TAPE) })).ok, true);
  const r = validateImport(good({ tape: mk(MAX_TAPE + 1) }));
  assert.equal(r.ok, false);
  assert.match(r.error, /500/);
});

test("normalizeData：丟掉不合格的設定、記憶、紙帶項目", () => {
  const out = normalizeData({
    settings: { decimals: 4, sep: "xx", bogus: 1 },
    scenarios: [sc("a", "A", "t", { extra: 1 })],
    tape: [entry(5), { expr: 3, value: 1 }, { expr: "x", value: NaN }, null, { expr: "ok", value: 1, ts: "bad" }],
    memory: { M0: 1, M1: "x", M99: 5, ACC: { sum: 2, count: -1 } },
  });
  assert.deepEqual(out.settings, { decimals: 4 });
  assert.equal(out.scenarios[0].extra, undefined);
  assert.deepEqual(out.tape.map((e) => e.expr), ["1+1", "ok"]);
  assert.equal(out.tape[1].ts, 0);
  assert.equal(out.memory.M0, 1);
  assert.equal(out.memory.M1, 0);
  assert.equal("M99" in out.memory, false);
  assert.deepEqual(out.memory.ACC, { sum: 0, count: 0 });
});

const local = () => ({
  settings: { decimals: 2, theme: "dark" },
  scenarios: [sc("a", "本機A", "2026-10-19T10:00:00+08:00"), sc("b", "本機B", "2026-10-19T12:00:00+08:00"), sc("l", "只在本機", "2026-10-01T00:00:00+08:00")],
  tape: [entry(10, "a"), entry(30, "c")],
  memory: { M0: 1, ACC: { sum: 0, count: 0 } },
});
const incoming = () => ({
  settings: { decimals: 6 },
  scenarios: [sc("a", "匯入A", "2026-10-19T11:00:00+08:00"), sc("b", "匯入B", "2026-10-19T09:00:00+08:00"), sc("n", "新的", "2026-10-02T00:00:00+08:00")],
  tape: [entry(20, "b"), entry(40, "d")],
  memory: { M0: 7, ACC: { sum: 0, count: 0 } },
});

test("mergeData replace：整份以 incoming 取代，且是複本", () => {
  const inc = incoming();
  const out = mergeData(local(), inc, "replace");
  assert.deepEqual(out, incoming());
  out.settings.decimals = 99;
  assert.equal(inc.settings.decimals, 6);
});

test("mergeData merge：情境依 id 取 updated_at 較新者、其餘都保留", () => {
  const out = mergeData(local(), incoming(), "merge");
  const by = Object.fromEntries(out.scenarios.map((s) => [s.id, s.name]));
  assert.deepEqual(by, { a: "匯入A", b: "本機B", l: "只在本機", n: "新的" });
  // 同時間：取 incoming
  const t = "2026-10-19T10:00:00+08:00";
  const same = mergeData({ ...local(), scenarios: [sc("a", "舊", t)] }, { ...incoming(), scenarios: [sc("a", "新", t)] }, "merge");
  assert.equal(same.scenarios[0].name, "新");
  // 不同時區寫法也依真正的時間比較
  const z = mergeData({ ...local(), scenarios: [sc("a", "L", "2026-10-19T03:00:00Z")] },
    { ...incoming(), scenarios: [sc("a", "I", "2026-10-19T11:30:00+08:00")] }, "merge");
  assert.equal(z.scenarios[0].name, "I");
});

test("mergeData merge：設定 incoming 覆蓋、記憶 incoming 覆蓋、紙帶依 ts 排序", () => {
  const out = mergeData(local(), incoming(), "merge");
  assert.deepEqual(out.settings, { decimals: 6, theme: "dark" });
  assert.equal(out.memory.M0, 7);
  assert.deepEqual(out.tape.map((e) => e.ts), [10, 20, 30, 40]);
});

test("mergeData merge：紙帶上限 500 保留最新、完全相同的項目只留一筆", () => {
  const many = (from, n) => Array.from({ length: n }, (_, i) => entry(from + i, `e${from + i}`, from + i));
  const out = mergeData({ ...local(), tape: many(0, 400) }, { ...incoming(), tape: many(300, 300) }, "merge");
  // 0..399 與 300..599 重疊 100 筆 → 600 筆唯一 → 取最新 500 筆（ts 100..599）
  assert.equal(out.tape.length, 500);
  assert.equal(out.tape[0].ts, 100);
  assert.equal(out.tape[499].ts, 599);
});

test("mergeData：mode 不合法丟例外", () => {
  assert.throws(() => mergeData(local(), incoming(), "x"));
});

test("importBackup：成功回傳資料與數量；失敗回傳原因", () => {
  const r = importBackup(good(), local(), "merge");
  assert.equal(r.ok, true);
  assert.deepEqual(r.counts, { scenarios: 1, tape: 1, settings: 1, memory: 1 });
  assert.equal(r.data.scenarios.length, 3);
  const rep = importBackup(good(), local(), "replace");
  assert.deepEqual(rep.data.scenarios.map((s) => s.id), ["a"]);
  assert.equal(rep.data.memory.M1, 5);
  const bad = importBackup({ app: "X" }, local(), "merge");
  assert.equal(bad.ok, false);
  assert.ok(bad.error);
});

test("importBackup：不盲信，壞的紙帶與記憶值被丟棄", () => {
  const g = good({ tape: [entry(1), { expr: "x", value: "abc" }], memory: { M0: "evil", M2: 3 } });
  const r = importBackup(g, emptyData(), "replace");
  assert.equal(r.data.tape.length, 1);
  assert.equal(r.data.memory.M0, 0);
  assert.equal(r.data.memory.M2, 3);
});

test("匯出再匯入：往返後相同", () => {
  const data = normalizeData(good().data);
  const exported = JSON.parse(JSON.stringify(makeExport(data, 0)));
  const r = importBackup(exported, emptyData(), "replace");
  assert.deepEqual(r.data, data);
});

// ---- Task 25 修正輪 1：情境表格與匯入加固
import { sanitizeGrid, sanitizeScenarioInputs, MAX_SCENARIOS } from "../../web/js/storage/backup.js";

test("sanitizeGrid：表格往返不變；形狀不合回傳 null", () => {
  const g = [["-1500", "1"], ["300", "5"]];
  assert.deepEqual(sanitizeGrid(g), g);
  assert.notEqual(sanitizeGrid(g), g); // 複本
  for (const bad of [null, [], "x", [["1"], 5], [[1, 2]], [[]], Array.from({ length: 501 }, () => ["1"]), [[("x").repeat(101)]]]) {
    assert.equal(sanitizeGrid(bad), null);
  }
  assert.notEqual(sanitizeGrid(Array.from({ length: 500 }, () => ["1"])), null);
});

test("sanitizeScenarioInputs：只留已知輸入欄位、合法狀態與表格", () => {
  const out = sanitizeScenarioInputs("cashflow", {
    CF0: { text: "-1000", direction: "out", exact: -1000, stale: true, extra: 1 },
    IY: { text: "5" },
    bogus: { text: "1" },
    NPV: { text: "99" }, // 輸出欄位不收
    __grid: [["1", "1"]],
  });
  assert.deepEqual(out.CF0, { text: "-1000", direction: "out", exact: -1000 });
  assert.ok(!("bogus" in out));
  assert.deepEqual(out.__grid, [["1", "1"]]);
  const bad = sanitizeScenarioInputs("tvm", {
    N: { text: 5 }, IY: { text: "5", direction: "sideways", exact: Infinity }, PV: "x", BGN: { checked: true }, __grid: "no",
  });
  assert.ok(!("N" in bad) && !("PV" in bad) && !("__grid" in bad));
  assert.deepEqual(bad.IY, { text: "5" });
  assert.deepEqual(bad.BGN, { checked: true });
});

test("normalizeData：丟棄未知工作表、名稱截到 80 字、情境數上限 1000", () => {
  const mk = (id, ws, name = "n") => ({ id, worksheet: ws, name, inputs: {}, updated_at: "2026-10-19T10:00:00+08:00" });
  const out = normalizeData({
    settings: {}, tape: [], memory: {},
    scenarios: [mk("a", "tvm", "x".repeat(200)), mk("b", "nope"), mk("c", "constructor"), mk("d", "__proto__")],
  });
  assert.deepEqual(out.scenarios.map((s) => s.id), ["a"]);
  assert.equal(out.scenarios[0].name.length, 80);
  const many = Array.from({ length: MAX_SCENARIOS + 50 }, (_, i) => mk("s" + i, "tvm"));
  assert.equal(normalizeData({ settings: {}, tape: [], memory: {}, scenarios: many }).scenarios.length, MAX_SCENARIOS);
});
