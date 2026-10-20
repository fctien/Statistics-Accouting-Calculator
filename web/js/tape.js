// Model：計算機紙帶（tape）。純函式模型，可用 node --test 測試。
// 每次成功計算新增 {expr, value, display, ts}；最多 max（預設 500）筆，超過時捨棄最舊的。
// 錯誤不進紙帶（由畫面顯示在輸入框下方）。value 是引擎的原始浮點數，display 是引擎格式化字串
// （設定改變時由畫面請引擎重新格式化，JS 不自己格式化）。

export const MAX_ENTRIES = 500;

export function createTape(max = MAX_ENTRIES, init = null) {
  let entries = [];

  const tape = {
    /** 新增一筆；回傳新增的項目。 */
    add({ expr, value, display, ts = Date.now() }) {
      const e = { expr: String(expr), value, display: String(display), ts };
      entries.push(e);
      if (entries.length > max) entries = entries.slice(entries.length - max);
      return e;
    },
    /** 全部項目（舊到新，陣列複本）。 */
    list: () => entries.slice(),
    get length() { return entries.length; },
    at: (i) => entries[i],
    last: () => entries[entries.length - 1] || null,
    clear() { entries = []; },
    setDisplay(i, display) { if (entries[i]) entries[i].display = String(display); },
    toJSON: () => entries.map((e) => ({ ...e })),
  };

  if (Array.isArray(init)) {
    for (const e of init) {
      if (e && typeof e.expr === "string" && Number.isFinite(e.value)) {
        tape.add({ expr: e.expr, value: e.value, display: e.display ?? "", ts: e.ts });
      }
    }
  }
  return tape;
}

/**
 * 輸入框的歷史瀏覽（上鍵往舊、下鍵往新）。
 * prev(current)：第一次往上時記住目前輸入的草稿；回傳要顯示的算式，或 null（已到最舊）。
 * next()：往新；走回最新之後回傳草稿；已在草稿位置回傳 null。reset()：新增紙帶項目後呼叫。
 */
export function createWalker(tape) {
  let pos = null; // null 代表草稿位置；否則為 tape 索引
  let draft = "";
  return {
    prev(current) {
      if (tape.length === 0) return null;
      if (pos === null) {
        draft = current;
        pos = tape.length - 1;
      } else if (pos > 0) {
        pos -= 1;
      } else {
        return null;
      }
      return tape.at(pos).expr;
    },
    next() {
      if (pos === null) return null;
      if (pos < tape.length - 1) {
        pos += 1;
        return tape.at(pos).expr;
      }
      pos = null;
      return draft;
    },
    reset() {
      pos = null;
      draft = "";
    },
  };
}
