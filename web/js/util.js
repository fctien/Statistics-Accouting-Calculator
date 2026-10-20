// 純函式小工具（不碰 DOM，可用 node --test 測試）。

/**
 * 防抖（debounce）：最後一次呼叫後等 ms 毫秒才執行 fn。
 * 回傳的函式有 .cancel()，可取消尚未執行的呼叫。
 */
export function debounce(fn, ms) {
  let timer = null;
  const wrapped = (...args) => {
    if (timer !== null) clearTimeout(timer);
    timer = setTimeout(() => {
      timer = null;
      fn(...args);
    }, ms);
  };
  wrapped.cancel = () => {
    if (timer !== null) clearTimeout(timer);
    timer = null;
  };
  return wrapped;
}
