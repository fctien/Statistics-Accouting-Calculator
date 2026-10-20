// 計算機按鍵面板的資料與插入邏輯（純函式，可用 node --test 測試）。
// 每個按鍵 insert 的字串都是引擎 engine/calc.py 認得的記號；按鍵只是在游標處插入文字。

/** 按鍵列：{label, insert, title, kind}；kind 供 CSS（digit／op／fn）。 */
export const KEY_ROWS = [
  [
    { label: "(", insert: "(", title: "左括號", kind: "fn" },
    { label: ")", insert: ")", title: "右括號", kind: "fn" },
    { label: "%", insert: "%", title: "百分比：200+10% = 220", kind: "fn" },
    { label: "÷", insert: "÷", title: "除", kind: "op" },
  ],
  [
    { label: "7", insert: "7", kind: "digit" },
    { label: "8", insert: "8", kind: "digit" },
    { label: "9", insert: "9", kind: "digit" },
    { label: "×", insert: "×", title: "乘", kind: "op" },
  ],
  [
    { label: "4", insert: "4", kind: "digit" },
    { label: "5", insert: "5", kind: "digit" },
    { label: "6", insert: "6", kind: "digit" },
    { label: "−", insert: "−", title: "減", kind: "op" },
  ],
  [
    { label: "1", insert: "1", kind: "digit" },
    { label: "2", insert: "2", kind: "digit" },
    { label: "3", insert: "3", kind: "digit" },
    { label: "+", insert: "+", title: "加", kind: "op" },
  ],
  [
    { label: "0", insert: "0", kind: "digit" },
    { label: ".", insert: ".", title: "小數點", kind: "digit" },
    { label: "ANS", insert: "ANS", title: "上一次的答案", kind: "fn" },
    { label: "yˣ", insert: "^", title: "次方：2^10", kind: "op" },
  ],
  [
    { label: "√", insert: "√(", title: "平方根", kind: "fn" },
    { label: "x²", insert: "²", title: "平方", kind: "fn" },
    { label: "1/x", insert: "inv(", title: "倒數", kind: "fn" },
    { label: "n!", insert: "!", title: "階乘", kind: "fn" },
  ],
];

function clampRange(text, start, end) {
  const n = text.length;
  let a = Math.min(Math.max(start ?? n, 0), n);
  let b = Math.min(Math.max(end ?? a, 0), n);
  if (a > b) [a, b] = [b, a];
  return [a, b];
}

/**
 * 在 [start, end) 選取範圍以 token 取代，回傳 {text, caret}（caret 在插入文字之後）。
 * 超出範圍時夾在字串長度內；start > end 視為對調。
 */
export function insertAt(text, start, end, token) {
  const [a, b] = clampRange(text, start, end);
  return { text: text.slice(0, a) + token + text.slice(b), caret: a + token.length };
}

/** 退格：有選取就刪選取，否則刪游標前一個字元。 */
export function backspaceAt(text, start, end) {
  const [a, b] = clampRange(text, start, end);
  if (a === b) {
    if (a === 0) return { text, caret: 0 };
    return { text: text.slice(0, a - 1) + text.slice(b), caret: a - 1 };
  }
  return { text: text.slice(0, a) + text.slice(b), caret: a };
}
