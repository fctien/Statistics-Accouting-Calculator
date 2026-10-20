// 日期顯示格式（純函式）：只影響「顯示」，輸入欄位仍是 <input type="date">。
// us：mm/dd/yyyy；eu：dd.mm.yyyy。不使用 Date 物件（避免時區造成差一天）。

const pad = (n, w) => String(n).padStart(w, "0");

/** 格式化 (y, m, d)；fmt 為 "us" 或 "eu"。 */
export function formatDate(y, m, d, fmt) {
  if (fmt === "eu") return `${pad(d, 2)}.${pad(m, 2)}.${pad(y, 4)}`;
  return `${pad(m, 2)}/${pad(d, 2)}/${pad(y, 4)}`;
}

/** 把 ISO 字串 yyyy-mm-dd 轉成指定格式；格式不符回傳 null。 */
export function formatIso(iso, fmt) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso || ""));
  return m ? formatDate(Number(m[1]), Number(m[2]), Number(m[3]), fmt) : null;
}
