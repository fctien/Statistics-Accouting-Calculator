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
    { label: "xʸ", insert: "^", title: "次方 xʸ：2^10 = 1024", kind: "op" },
  ],
  [
    { label: "√", insert: "√(", title: "平方根", kind: "fn" },
    { label: "x²", insert: "²", title: "平方", kind: "fn" },
    { label: "1/x", insert: "inv(", title: "倒數", kind: "fn" },
    { label: "n!", insert: "!", title: "階乘", kind: "fn" },
  ],
];

/**
 * 科學鍵（工程頁）：{label, insert, title, kind}；second＝按下 2nd 後的替代鍵（反三角、eˣ、10ˣ）；
 * action＝不是插入文字的功能鍵：second（2nd 切換）、angle（DEG／RAD 切換）、negate（±）、
 * back（⌫）、clear（C）。參考桌面版 engineering-calculator 的科學鍵區。
 */
export const SCI_ROWS = [
  [
    { label: "2nd", action: "second", title: "第二功能：sin→sin⁻¹、cos→cos⁻¹、tan→tan⁻¹、ln→eˣ、log→10ˣ", kind: "fn" },
    { label: "DEG", action: "angle", title: "角度單位 DEG／RAD 切換", kind: "fn" },
    { label: "±", action: "negate", title: "正負號切換（游標所在的數字）", kind: "fn" },
    { label: "⌫", action: "back", title: "退格（Backspace）", kind: "fn" },
    { label: "C", action: "clear", title: "清除輸入（Esc）", kind: "fn" },
  ],
  [
    { label: "sin", insert: "sin(", title: "正弦 sin，例：DEG 時 sin(30) = 0.5", kind: "fn",
      second: { label: "sin⁻¹", insert: "asin(", title: "反正弦 asin，例：DEG 時 asin(0.5) = 30" } },
    { label: "cos", insert: "cos(", title: "餘弦 cos，例：DEG 時 cos(60) = 0.5", kind: "fn",
      second: { label: "cos⁻¹", insert: "acos(", title: "反餘弦 acos，例：DEG 時 acos(0.5) = 60" } },
    { label: "tan", insert: "tan(", title: "正切 tan，例：DEG 時 tan(45) = 1", kind: "fn",
      second: { label: "tan⁻¹", insert: "atan(", title: "反正切 atan，例：DEG 時 atan(1) = 45" } },
    { label: "π", insert: "π", title: "圓周率 π", kind: "fn" },
    { label: "e", insert: "e", title: "自然常數 e", kind: "fn" },
  ],
  [
    { label: "log", insert: "log(", title: "常用對數 log₁₀，例：log(100) = 2", kind: "fn",
      second: { label: "10ˣ", insert: "10^(", title: "10 的次方，例：10^(2) = 100" } },
    { label: "ln", insert: "ln(", title: "自然對數 ln，例：ln(e) = 1", kind: "fn",
      second: { label: "eˣ", insert: "exp(", title: "e 的次方 exp，例：exp(1) = 2.718…" } },
    { label: "∛", insert: "cbrt(", title: "立方根，例：cbrt(27) = 3", kind: "fn" },
    { label: "nPr", insert: "nPr(", title: "排列：nPr(5,2) = 20", kind: "fn" },
    { label: "nCr", insert: "nCr(", title: "組合：nCr(5,2) = 10；引數用 , 分隔", kind: "fn",
      second: { label: ",", insert: ",", title: "引數分隔（nPr、nCr 用）" } },
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

const NUM_CH = /[0-9.]/;
const MINUS = new Set(["−", "-"]);
const BEFORE_UNARY = new Set(["+", "−", "-", "×", "÷", "*", "/", "^", "(", ",", "%"]);

/**
 * ±：切換游標所在數字的負號（負號用 −）。數字前已有「一元」負號（在開頭或運算子、左括號之後）就移除，
 * 否則插入一個（二元減號後也插入：3−45 → 3−−45）。回傳 {text, caret}。
 */
export function toggleSign(text, caret) {
  const [c] = clampRange(text, caret, caret);
  let start = c;
  while (start > 0 && NUM_CH.test(text[start - 1])) start -= 1;
  const prev = text[start - 1];
  const unary = MINUS.has(prev) && (start - 1 === 0 || BEFORE_UNARY.has(text[start - 2]));
  if (unary) return { text: text.slice(0, start - 1) + text.slice(start), caret: c - 1 };
  return { text: text.slice(0, start) + "−" + text.slice(start), caret: c + 1 };
}
