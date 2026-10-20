// 純函式：CSV 輸出（RFC 4180）。toCSV 不碰 DOM；download 才用 Blob 與 <a download>。
// 為了讓 Excel 正確開啟中文標頭，toCSV 可加 UTF-8 BOM（byte order mark）。

/** UTF-8 BOM 字元（U+FEFF）。 */
export const BOM = "\uFEFF";

/** 單一欄位：含逗號、雙引號、換行時加雙引號，內部雙引號重複一次。null／undefined 為空字串。 */
export function csvField(value) {
  const s = value === null || value === undefined ? "" : String(value);
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

/**
 * rows：二維陣列；headers：標頭陣列（可省略或空）。
 * 每列以 CRLF 結尾；opts.bom 為 true 時開頭加 BOM。
 */
export function toCSV(rows, headers, opts = {}) {
  const lines = [];
  if (headers && headers.length) lines.push(headers.map(csvField).join(","));
  for (const row of rows || []) lines.push(row.map(csvField).join(","));
  const body = lines.map((l) => l + "\r\n").join("");
  return (opts.bom ? BOM : "") + body;
}

/**
 * 匯出用的引擎設定：小數點固定 "."、不含千分位（sep: "us"），小數位數維持使用者設定。
 * 四捨五入由引擎完成，JS 不再自己捨入。
 */
export function exportSettings(settings) {
  return { ...settings, sep: "us" };
}

/** 去掉 "us" 格式字串的千分位逗號（"1,234.50" → "1234.50"），讓 Excel 視為數字。 */
export function plainNumberRows(rows) {
  return rows.map((row) => row.map((c) => String(c).replace(/,/g, "")));
}

/** 觸發瀏覽器下載文字檔（Blob＋a[download]）；與 toCSV 分開，方便測試。 */
export function download(filename, text, mime = "text/csv;charset=utf-8") {
  const blob = new Blob([text], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
