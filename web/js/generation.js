// 純函式：世代計數（generation guard）。每張工作表一個計數器；輸入改變或結果失效時 bump，
// 進行中的請求回來時用 isCurrent 檢查，世代變了就丟棄回應，避免舊輸入的結果看起來像目前結果。

export function createGuard() {
  const gens = new Map();
  return {
    /** 目前世代（未見過的 id 為 0）。 */
    get: (id) => gens.get(id) || 0,
    /** 世代加一，回傳新值。 */
    bump(id) {
      const n = (gens.get(id) || 0) + 1;
      gens.set(id, n);
      return n;
    },
    /** token（先前 get 的值）是否仍為目前世代。 */
    isCurrent: (id, token) => (gens.get(id) || 0) === token,
  };
}
