// gdrive.js 測試：純函式與以假 fetch 驗證的 Drive REST 路徑（找／建立／更新／下載、401／403／網路錯誤）、decideConflict 矩陣。
import test from "node:test";
import assert from "node:assert/strict";

import {
  FILE_NAME, SCOPE, GIS_URL, isValidClientId, buildMultipartBody, parseFileList, decideConflict,
  localUpdatedAt, stripLocalOnly, stableStringify, hashData, isLocalEmpty, isLocalChanged, overwriteSummary, describeHttpError, createDrive, GDriveError, currentToken, isConnected,
} from "../../web/js/storage/gdrive.js";

const resp = (status, body, text) => ({
  ok: status >= 200 && status < 300, status,
  json: async () => body,
  text: async () => (text !== undefined ? text : JSON.stringify(body)),
});

/** 假 fetch：依序回傳 queue 內的回應，並記錄每次呼叫。 */
function fake(queue) {
  const calls = [];
  const fn = async (url, init) => {
    calls.push({ url, init });
    const next = queue.shift();
    if (next instanceof Error) throw next;
    return next;
  };
  fn.calls = calls;
  return fn;
}
const FILE = { id: "F1", name: FILE_NAME, modifiedTime: "2026-10-20T01:00:00.000Z" };

test("常數：檔名、scope、GIS 網址", () => {
  assert.equal(FILE_NAME, "bacalc-backup.json");
  assert.equal(SCOPE, "https://www.googleapis.com/auth/drive.appdata");
  assert.equal(GIS_URL, "https://accounts.google.com/gsi/client");
});

test("isValidClientId：只收 .apps.googleusercontent.com 結尾", () => {
  assert.equal(isValidClientId("123-abc.apps.googleusercontent.com"), true);
  assert.equal(isValidClientId("123-abc.apps.googleusercontent.com.evil.com"), false);
  assert.equal(isValidClientId("abc"), false);
  assert.equal(isValidClientId(""), false);
  assert.equal(isValidClientId(null), false);
  assert.equal(isValidClientId(".apps.googleusercontent.com"), false);
});

test("buildMultipartBody：兩段、邊界、parents appDataFolder", () => {
  const { body, contentType } = buildMultipartBody({ name: FILE_NAME, parents: ["appDataFolder"] }, '{"a":1}', "BND");
  assert.equal(contentType, "multipart/related; boundary=BND");
  const parts = body.split("--BND");
  assert.equal(parts.length, 4); // 前導空字串、中繼資料、內容、結尾 "--"
  assert.match(parts[1], /Content-Type: application\/json/);
  assert.deepEqual(JSON.parse(parts[1].split("\r\n\r\n")[1].trim()), { name: FILE_NAME, parents: ["appDataFolder"] });
  assert.equal(parts[2].split("\r\n\r\n")[1].trim(), '{"a":1}');
  assert.equal(parts[3], "--");
  assert.ok(body.endsWith("--BND--"));
});

test("parseFileList：空、同名多筆取最新、忽略其他名稱、壞輸入", () => {
  assert.equal(parseFileList({ files: [] }), null);
  assert.equal(parseFileList(null), null);
  assert.equal(parseFileList({}), null);
  assert.equal(parseFileList({ files: [{ id: "x", name: "other.json", modifiedTime: "2026-01-01T00:00:00Z" }] }), null);
  const r = parseFileList({ files: [
    { id: "old", name: FILE_NAME, modifiedTime: "2026-01-01T00:00:00Z" },
    { id: "new", name: FILE_NAME, modifiedTime: "2026-02-01T00:00:00Z" },
  ] });
  assert.equal(r.id, "new");
});

test("decideConflict 矩陣（本機是否改過由內容雜湊決定）", () => {
  const T = (n) => `2026-10-${String(n).padStart(2, "0")}T00:00:00Z`;
  // 雲端沒有 → 上傳
  assert.equal(decideConflict(true, null, T(1)), "upload");
  assert.equal(decideConflict(false, undefined, null), "upload");
  // 從未同步：本機有資料 → ask；本機空 → download
  assert.equal(decideConflict(true, T(6), null, true), "ask");
  assert.equal(decideConflict(false, T(6), null, false), "download");
  // 雲端新、本機沒動 → download
  assert.equal(decideConflict(false, T(6), T(2)), "download");
  // 雲端新、本機也動過 → ask（不自動覆蓋）
  assert.equal(decideConflict(true, T(6), T(2)), "ask");
  // 雲端沒動、本機動過 → upload；都沒動 → upload
  assert.equal(decideConflict(true, T(2), T(2)), "upload");
  assert.equal(decideConflict(false, T(2), T(2)), "upload");
  // 無法解析的雲端時間當作沒有
  assert.equal(decideConflict(true, "garbage", T(2)), "upload");
});

const DATA = () => ({
  settings: { decimals: 4, mode: "AOS", gdriveClientId: "a.apps.googleusercontent.com" },
  scenarios: [{ id: "a", worksheet: "tvm", name: "A", inputs: { N: { text: "1" } }, updated_at: "2026-10-19T10:00:00+08:00" }],
  tape: [{ expr: "1+1", value: 2, ts: 5 }], memory: { M1: 5, ACC: { count: 0 } },
});

test("stableStringify／hashData：與鍵順序無關、忽略只屬本機的鍵、內容改變則雜湊改變", () => {
  assert.equal(stableStringify({ b: 1, a: [2, { d: 1, c: 2 }] }), stableStringify({ a: [2, { c: 2, d: 1 }], b: 1 }));
  const d = DATA();
  const reordered = { memory: { ACC: { count: 0 }, M1: 5 }, tape: [{ ts: 5, value: 2, expr: "1+1" }],
    scenarios: [{ updated_at: "2026-10-19T10:00:00+08:00", inputs: { N: { text: "1" } }, name: "A", worksheet: "tvm", id: "a" }],
    settings: { mode: "AOS", decimals: 4 } };
  assert.equal(hashData(d), hashData(reordered));
  assert.equal(hashData(d), hashData({ ...d, settings: { ...d.settings, gdriveLastSync: "x", gdriveLastSyncHash: "y", gdriveClientId: "z" } }));
  assert.match(hashData(d), /^[0-9a-f]{14}$/);
  for (const mut of [(x) => { x.memory.M1 = 6; }, (x) => { x.settings.decimals = 5; }, (x) => { x.tape[0].value = 3; }, (x) => { x.scenarios[0].name = "B"; }]) {
    const x = DATA();
    mut(x);
    assert.notEqual(hashData(x), hashData(d));
  }
});

test("isLocalEmpty：只看情境、紙帶、記憶", () => {
  assert.equal(isLocalEmpty({ settings: { decimals: 9 }, scenarios: [], tape: [], memory: {} }), true);
  assert.equal(isLocalEmpty({ scenarios: [], tape: [], memory: { M0: 0, M1: 0, ACC: { count: 0 } } }), true);
  assert.equal(isLocalEmpty({ scenarios: [], tape: [], memory: { M3: 1 } }), false);
  assert.equal(isLocalEmpty({ scenarios: [], tape: [], memory: { ACC: { count: 2 } } }), false);
  assert.equal(isLocalEmpty({ scenarios: [], tape: [{ expr: "1", value: 1, ts: 1 }], memory: {} }), false);
  assert.equal(isLocalEmpty({ scenarios: [{}], tape: [], memory: {} }), false);
});

test("isLocalChanged：無儲存雜湊時有資料即視為改過；有雜湊時比對內容（包含只改記憶或設定）", () => {
  const d = DATA();
  assert.equal(isLocalChanged(d, ""), true);
  assert.equal(isLocalChanged({ scenarios: [], tape: [], memory: {} }, ""), false);
  const h = hashData(d);
  assert.equal(isLocalChanged(d, h), false);
  const m = DATA();
  m.memory.M1 = 99;
  assert.equal(isLocalChanged(m, h), true);
  const st = DATA();
  st.settings.decimals = 0;
  assert.equal(isLocalChanged(st, h), true);
});

test("overwriteSummary：記憶或設定有差異才標記", () => {
  const a = DATA();
  assert.deepEqual(overwriteSummary(a, DATA()), { memory: false, settings: false });
  const b = DATA();
  b.memory.M1 = 1;
  assert.deepEqual(overwriteSummary(a, b), { memory: true, settings: false });
  const c = DATA();
  c.settings.mode = "CHAIN";
  assert.deepEqual(overwriteSummary(a, c), { memory: false, settings: true });
  const e = DATA();
  e.settings.gdriveClientId = "other.apps.googleusercontent.com";
  assert.deepEqual(overwriteSummary(a, e), { memory: false, settings: false });
});

test("雲端在決定動作後又被改過：上傳與下載都中止且不寫入", async () => {
  const changed = { ...FILE, modifiedTime: "2026-10-20T05:00:00.000Z" };
  const f = fake([resp(200, { files: [changed] })]);
  await assert.rejects(createDrive(f, () => "T").upload("{}", FILE.modifiedTime), (e) => e.code === "conflict" && /被更新過/.test(e.message));
  assert.equal(f.calls.length, 1, "沒有送出 PATCH／POST");
  const f2 = fake([resp(200, { files: [changed] })]);
  await assert.rejects(createDrive(f2, () => "T").download(FILE.modifiedTime), (e) => e.code === "conflict");
  assert.equal(f2.calls.length, 1, "沒有下載內容");
  // 當時沒有檔案、現在出現了 → 上傳中止
  const f3 = fake([resp(200, { files: [FILE] })]);
  await assert.rejects(createDrive(f3, () => "T").upload("{}", null), (e) => e.code === "conflict");
  // 沒變 → 照常；未傳 expected → 不檢查
  const f4 = fake([resp(200, { files: [FILE] }), resp(200, { id: "F1", modifiedTime: "2026-10-20T06:00:00.000Z" })]);
  assert.equal((await createDrive(f4, () => "T").upload("{}", FILE.modifiedTime)).id, "F1");
});

test("localUpdatedAt：取情境與紙帶的最大時間", () => {
  assert.equal(localUpdatedAt({ scenarios: [], tape: [] }), null);
  assert.equal(localUpdatedAt(null), null);
  const d = {
    scenarios: [{ updated_at: "2026-10-19T10:00:00+08:00" }, { updated_at: "bad" }],
    tape: [{ ts: Date.parse("2026-10-20T00:00:00Z") }, { ts: 0 }],
  };
  assert.equal(localUpdatedAt(d), "2026-10-20T00:00:00.000Z");
});

test("stripLocalOnly：拿掉 Client ID 與上次同步時間，其餘設定保留且不改動原物件", () => {
  const d = { settings: { decimals: 4, gdriveClientId: "a.apps.googleusercontent.com", gdriveLastSync: "x" }, scenarios: [] };
  const o = stripLocalOnly(d);
  assert.deepEqual(o.settings, { decimals: 4 });
  assert.equal(d.settings.gdriveClientId, "a.apps.googleusercontent.com");
});

test("describeHttpError：401／403／404／429／5xx 為中文", () => {
  assert.match(describeHttpError(401), /授權已失效/);
  assert.match(describeHttpError(403, JSON.stringify({ error: { errors: [{ reason: "accessNotConfigured" }] } })), /尚未啟用 Drive API/);
  assert.match(describeHttpError(403, JSON.stringify({ error: { errors: [{ reason: "rateLimitExceeded" }] } })), /頻繁/);
  assert.match(describeHttpError(403, "not json"), /測試使用者/);
  assert.match(describeHttpError(404), /找不到/);
  assert.match(describeHttpError(429), /頻繁/);
  assert.match(describeHttpError(503), /暫時發生問題/);
});

test("find：查詢 appDataFolder 與檔名，帶 Bearer 權杖", async () => {
  const f = fake([resp(200, { files: [FILE] })]);
  const d = createDrive(f, () => "TOK");
  const r = await d.find();
  assert.equal(r.id, "F1");
  const u = new URL(f.calls[0].url);
  assert.equal(u.origin + u.pathname, "https://www.googleapis.com/drive/v3/files");
  assert.equal(u.searchParams.get("spaces"), "appDataFolder");
  assert.equal(u.searchParams.get("q"), `name='${FILE_NAME}'`);
  assert.match(u.searchParams.get("fields"), /modifiedTime/);
  assert.equal(f.calls[0].init.headers.Authorization, "Bearer TOK");
});

test("remoteModified：有檔回傳時間、沒檔回傳 null", async () => {
  assert.equal(await createDrive(fake([resp(200, { files: [FILE] })]), () => "T").remoteModified(), FILE.modifiedTime);
  assert.equal(await createDrive(fake([resp(200, { files: [] })]), () => "T").remoteModified(), null);
});

test("upload（雲端沒有檔案）：multipart POST，parents 為 appDataFolder", async () => {
  const f = fake([resp(200, { files: [] }), resp(200, { id: "NEW", modifiedTime: "2026-10-20T02:00:00.000Z" })]);
  const r = await createDrive(f, () => "T").upload({ a: 1 });
  assert.deepEqual(r, { id: "NEW", modifiedTime: "2026-10-20T02:00:00.000Z" });
  const c = f.calls[1];
  assert.equal(c.init.method, "POST");
  assert.match(c.url, /^https:\/\/www\.googleapis\.com\/upload\/drive\/v3\/files\?uploadType=multipart/);
  assert.match(c.init.headers["Content-Type"], /^multipart\/related; boundary=/);
  assert.ok(c.init.body.includes('"parents":["appDataFolder"]'));
  assert.ok(c.init.body.includes(`"name":"${FILE_NAME}"`));
  assert.ok(c.init.body.includes('{"a":1}'));
});

test("upload（已有檔案）：PATCH uploadType=media 到該檔案 id", async () => {
  const f = fake([resp(200, { files: [FILE] }), resp(200, { id: "F1", modifiedTime: "2026-10-20T03:00:00.000Z" })]);
  const r = await createDrive(f, () => "T").upload('{"b":2}');
  assert.equal(r.modifiedTime, "2026-10-20T03:00:00.000Z");
  const c = f.calls[1];
  assert.equal(c.init.method, "PATCH");
  assert.match(c.url, /\/upload\/drive\/v3\/files\/F1\?uploadType=media/);
  assert.equal(c.init.body, '{"b":2}');
});

test("download：alt=media，回傳文字與修改時間；沒有檔案回傳 null", async () => {
  const f = fake([resp(200, { files: [FILE] }), resp(200, null, '{"app":"BACalc"}')]);
  const r = await createDrive(f, () => "T").download();
  assert.deepEqual(r, { text: '{"app":"BACalc"}', modifiedTime: FILE.modifiedTime });
  assert.match(f.calls[1].url, /\/drive\/v3\/files\/F1\?alt=media$/);
  assert.equal(await createDrive(fake([resp(200, { files: [] })]), () => "T").download(), null);
});

test("401：丟出 auth 錯誤並通知清除權杖", async () => {
  let cleared = 0;
  const d = createDrive(fake([resp(401, { error: { code: 401 } })]), () => "T", () => { cleared += 1; });
  await assert.rejects(d.find(), (e) => e instanceof GDriveError && e.code === "auth" && e.status === 401 && /授權已失效/.test(e.message));
  assert.equal(cleared, 1);
});

test("403 未啟用 API、網路錯誤、沒有權杖", async () => {
  const body = { error: { errors: [{ reason: "accessNotConfigured" }] } };
  await assert.rejects(createDrive(fake([resp(403, body)]), () => "T").find(), (e) => e.code === "http" && /尚未啟用 Drive API/.test(e.message));
  await assert.rejects(createDrive(fake([new TypeError("Failed to fetch")]), () => "T").find(), (e) => e.code === "network");
  const f = fake([]);
  await assert.rejects(createDrive(f, () => null).find(), (e) => e.code === "auth");
  assert.equal(f.calls.length, 0, "沒有權杖時不送出任何請求");
});

test("上傳在 find 階段失敗時不會送出寫入請求", async () => {
  const f = fake([resp(500, {}, "oops")]);
  await assert.rejects(createDrive(f, () => "T").upload("{}"), (e) => e.status === 500);
  assert.equal(f.calls.length, 1);
});

test("權杖只放記憶體：載入模組後預設未連結，且沒有任何儲存呼叫", () => {
  assert.equal(currentToken(), null);
  assert.equal(isConnected(), false);
});
