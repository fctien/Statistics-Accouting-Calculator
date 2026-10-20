// Model／Controller：Google Drive 同步（選用，預設關閉）。
// 只用 drive.appdata 權限範圍（scope）：App 專屬的隱藏資料夾 appDataFolder，看不到使用者其他檔案。
// 隱私：使用者設定 Client ID 並按下按鈕之前，不送出任何網路請求；
// GIS 程式庫（accounts.google.com/gsi/client）只在按「連結 Google Drive」時才動態載入，不進 precache。
// 存取權杖（access token）只放在記憶體，絕不寫入 IndexedDB／localStorage。
// 純函式（buildMultipartBody、parseFileList、decideConflict、describeHttpError…）與 createDrive(fetch, getToken)
// 都可用 node --test 搭配假的 fetch 測試；GIS 與 DOM 相關部分以 globalThis 守衛。

export const FILE_NAME = "bacalc-backup.json";
export const SCOPE = "https://www.googleapis.com/auth/drive.appdata";
export const GIS_URL = "https://accounts.google.com/gsi/client";
export const API = "https://www.googleapis.com/drive/v3/files";
export const UPLOAD_API = "https://www.googleapis.com/upload/drive/v3/files";
/** 只屬於本機、不上傳也不從雲端覆蓋的設定鍵。 */
export const LOCAL_ONLY_KEYS = ["gdriveClientId", "gdriveLastSync"];

/** 驗證 Client ID 的形狀（結尾必須是 .apps.googleusercontent.com）；不代表它真的有效。 */
export function isValidClientId(id) {
  return typeof id === "string" && id.length <= 200 && /^[A-Za-z0-9._-]+\.apps\.googleusercontent\.com$/.test(id);
}

/** 組 multipart/related 請求本體：第一段 JSON 中繼資料（metadata），第二段檔案內容。 */
export function buildMultipartBody(metadata, content, boundary = "bacalc_boundary_7d2f9a") {
  const body = `--${boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n${JSON.stringify(metadata)}\r\n`
    + `--${boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n${content}\r\n--${boundary}--`;
  return { body, contentType: `multipart/related; boundary=${boundary}` };
}

/** 從 files.list 的回應取出備份檔 {id, name, modifiedTime}；多個同名時取最近修改的；沒有回傳 null。 */
export function parseFileList(json) {
  const files = json && Array.isArray(json.files) ? json.files : [];
  const ok = files.filter((f) => f && typeof f.id === "string" && f.name === FILE_NAME);
  if (ok.length === 0) return null;
  const t = (f) => (Number.isFinite(Date.parse(f.modifiedTime)) ? Date.parse(f.modifiedTime) : -Infinity);
  const best = ok.reduce((a, b) => (t(b) > t(a) ? b : a));
  return { id: best.id, name: best.name, modifiedTime: typeof best.modifiedTime === "string" ? best.modifiedTime : null };
}

const ms = (s) => {
  const t = Date.parse(s);
  return Number.isFinite(t) ? t : null;
};

/**
 * 判斷該上傳、下載還是詢問使用者。
 * - 雲端沒有檔案 → "upload"
 * - 從未同步過（lastSync 空）：雲端有檔；本機有資料 → "ask"，本機是空的 → "download"
 * - 雲端比上次同步新 且 本機在上次同步之後也改過 → "ask"（絕不自動覆蓋）
 * - 只有雲端變新 → "download"；其餘（只有本機改過，或都沒變）→ "upload"
 */
export function decideConflict(localUpdatedAtIso, remoteModifiedTime, lastSync = null) {
  const remote = ms(remoteModifiedTime);
  if (remote === null) return "upload";
  const local = ms(localUpdatedAtIso);
  const last = ms(lastSync);
  if (last === null) return local === null ? "download" : "ask";
  const remoteChanged = remote > last;
  const localChanged = local !== null && local > last;
  if (remoteChanged && localChanged) return "ask";
  if (remoteChanged) return "download";
  return "upload";
}

/** 本機資料的最後更新時間（情境 updated_at 與紙帶 ts 的最大值）；沒有任何帶時間的資料回傳 null。 */
export function localUpdatedAt(data) {
  let best = null;
  for (const s of (data && data.scenarios) || []) {
    const t = ms(s.updated_at);
    if (t !== null && (best === null || t > best)) best = t;
  }
  for (const e of (data && data.tape) || []) {
    if (Number.isFinite(e.ts) && e.ts > 0 && (best === null || e.ts > best)) best = e.ts;
  }
  return best === null ? null : new Date(best).toISOString();
}

/** 上傳／下載時拿掉只屬於本機的設定（Client ID、上次同步時間）。 */
export function stripLocalOnly(data) {
  const settings = { ...(data.settings || {}) };
  for (const k of LOCAL_ONLY_KEYS) delete settings[k];
  return { ...data, settings };
}

/** Google 錯誤 → 中文訊息。 */
export function describeHttpError(status, bodyText = "") {
  let reason = "";
  try {
    const j = JSON.parse(bodyText);
    reason = (j.error && ((j.error.errors && j.error.errors[0] && j.error.errors[0].reason) || j.error.status)) || "";
  } catch (e) {
    reason = "";
  }
  if (status === 401) return "Google 授權已失效或過期，請重新按「連結 Google Drive」";
  if (status === 403) {
    if (/accessNotConfigured|SERVICE_DISABLED/i.test(reason + bodyText)) {
      return "這個 Google Cloud 專案尚未啟用 Drive API，請依設定說明啟用後再試";
    }
    if (/rateLimit|userRateLimit|quota/i.test(reason)) return "Google 回報請求過於頻繁或超過配額，請稍後再試";
    return "Google 拒絕存取（403）：請確認授權時有勾選 Drive 應用程式資料權限，且你的帳號已加入測試使用者";
  }
  if (status === 404) return "在雲端找不到備份檔（可能已被刪除）";
  if (status === 429) return "Google 請求過於頻繁，請稍後再試";
  if (status >= 500) return `Google 伺服器暫時發生問題（${status}），請稍後再試`;
  return `Google 回應錯誤（HTTP ${status}）`;
}

/** 同步相關錯誤；code：auth／network／http。 */
export class GDriveError extends Error {
  constructor(message, code, status = null) {
    super(message);
    this.name = "GDriveError";
    this.code = code;
    this.status = status;
  }
}

/**
 * 建立 Drive 存取物件。fetchFn：fetch 相容函式；getToken：回傳目前存取權杖字串（沒有則 null）；
 * onUnauthorized：收到 401 時呼叫（清掉記憶體中的權杖）。
 */
export function createDrive(fetchFn, getToken, onUnauthorized = () => {}) {
  async function request(url, init = {}) {
    const tk = getToken();
    if (!tk) throw new GDriveError("尚未連結 Google Drive，請先按「連結 Google Drive」", "auth");
    let res;
    try {
      res = await fetchFn(url, { ...init, headers: { ...(init.headers || {}), Authorization: `Bearer ${tk}` } });
    } catch (e) {
      throw new GDriveError("連不上 Google（網路中斷或被瀏覽器擋下），請檢查網路後再試", "network");
    }
    if (!res.ok) {
      let text = "";
      try {
        text = await res.text();
      } catch (e) {
        text = "";
      }
      if (res.status === 401) onUnauthorized();
      throw new GDriveError(describeHttpError(res.status, text), res.status === 401 ? "auth" : "http", res.status);
    }
    return res;
  }

  /** 找備份檔；回傳 {id, name, modifiedTime} 或 null。 */
  async function find() {
    const q = encodeURIComponent(`name='${FILE_NAME}'`);
    const url = `${API}?spaces=appDataFolder&q=${q}&fields=${encodeURIComponent("files(id,name,modifiedTime)")}`
      + "&orderBy=modifiedTime%20desc&pageSize=10";
    const res = await request(url);
    return parseFileList(await res.json());
  }

  /** 雲端備份檔的修改時間（ISO 字串）；沒有檔案回傳 null。 */
  async function remoteModified() {
    const f = await find();
    return f ? f.modifiedTime : null;
  }

  /** 上傳 JSON 字串（物件會先轉成字串）；有檔案就更新、沒有就建立。回傳 {id, modifiedTime}。 */
  async function upload(json) {
    const content = typeof json === "string" ? json : JSON.stringify(json);
    const existing = await find();
    let res;
    if (existing) {
      res = await request(`${UPLOAD_API}/${encodeURIComponent(existing.id)}?uploadType=media&fields=id,modifiedTime`, {
        method: "PATCH", headers: { "Content-Type": "application/json; charset=UTF-8" }, body: content,
      });
    } else {
      const { body, contentType } = buildMultipartBody({ name: FILE_NAME, parents: ["appDataFolder"] }, content);
      res = await request(`${UPLOAD_API}?uploadType=multipart&fields=id,modifiedTime`, {
        method: "POST", headers: { "Content-Type": contentType }, body,
      });
    }
    const j = await res.json();
    return { id: j.id, modifiedTime: j.modifiedTime || null };
  }

  /** 下載備份檔；回傳 {text, modifiedTime}，雲端沒有檔案回傳 null。內容由呼叫端驗證後才寫入。 */
  async function download() {
    const f = await find();
    if (!f) return null;
    const res = await request(`${API}/${encodeURIComponent(f.id)}?alt=media`);
    return { text: await res.text(), modifiedTime: f.modifiedTime };
  }

  return { find, remoteModified, upload, download };
}

// ---- 瀏覽器端：GIS 動態載入、權杖（只在記憶體）
let token = null; // { value, expiresAt }
let gisPromise = null;

/** 目前有效的存取權杖字串；沒有或已過期回傳 null。 */
export function currentToken() {
  if (token && token.expiresAt > Date.now() + 10000) return token.value;
  return null;
}
export const isConnected = () => currentToken() !== null;
export function clearToken() {
  token = null;
}

/** 動態載入 GIS；只在使用者按「連結」時呼叫。離線時拒絕並說明。 */
export function loadGis() {
  if (globalThis.google && globalThis.google.accounts && globalThis.google.accounts.oauth2) return Promise.resolve();
  if (globalThis.navigator && globalThis.navigator.onLine === false) {
    return Promise.reject(new GDriveError("目前離線，無法載入 Google 登入程式庫，請連上網路後再試", "network"));
  }
  if (!gisPromise) {
    gisPromise = new Promise((resolve, reject) => {
      const s = globalThis.document.createElement("script");
      s.src = GIS_URL;
      s.async = true;
      s.onload = () => resolve();
      s.onerror = () => {
        gisPromise = null;
        s.remove();
        reject(new GDriveError("無法載入 Google 登入程式庫（網路中斷或被擋下）", "network"));
      };
      globalThis.document.head.append(s);
    });
  }
  return gisPromise;
}

/** 連結：載入 GIS、跳出授權視窗，取得存取權杖（只存記憶體）。須由使用者點擊觸發。 */
export async function connect(clientId) {
  if (!isValidClientId(clientId)) throw new GDriveError("Client ID 格式不正確（應以 .apps.googleusercontent.com 結尾）", "auth");
  await loadGis();
  return new Promise((resolve, reject) => {
    const client = globalThis.google.accounts.oauth2.initTokenClient({
      client_id: clientId,
      scope: SCOPE,
      callback: (resp) => {
        if (!resp || resp.error || !resp.access_token) {
          reject(new GDriveError(`Google 授權失敗：${(resp && (resp.error_description || resp.error)) || "未取得權杖"}`, "auth"));
          return;
        }
        const sec = Number(resp.expires_in);
        token = { value: resp.access_token, expiresAt: Date.now() + (Number.isFinite(sec) ? sec : 3600) * 1000 };
        resolve(resp.access_token);
      },
      error_callback: (err) => {
        const t = err && err.type;
        reject(new GDriveError(t === "popup_closed" ? "授權視窗被關閉，沒有連結"
          : t === "popup_failed_to_open" ? "瀏覽器擋住了授權視窗，請允許彈出視窗後再試"
            : `Google 授權發生錯誤：${t || "未知"}`, "auth"));
      },
    });
    client.requestAccessToken({ prompt: "" });
  });
}

/** 中斷連結：撤銷（revoke）權杖並清掉記憶體；沒有權杖時只清記憶體。 */
export function disconnect() {
  const t = currentToken();
  clearToken();
  if (!t || !globalThis.google || !globalThis.google.accounts) return Promise.resolve(false);
  return new Promise((resolve) => {
    globalThis.google.accounts.oauth2.revoke(t, () => resolve(true));
  });
}

let drive = null;
function getDrive() {
  if (!drive) drive = createDrive((...a) => globalThis.fetch(...a), currentToken, clearToken);
  return drive;
}
export const upload = (json) => getDrive().upload(json);
export const download = () => getDrive().download();
export const remoteModified = () => getDrive().remoteModified();
export const find = () => getDrive().find();
