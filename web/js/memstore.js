// Model：記憶 M0～M9 與累加器 Σ（純函式模型，可用 node --test 測試）。
// 語意鏡射（mirror）engine/memory.py：STO、RCL、M+、M−、M×、M÷；除以零或溢位時回錯誤且記憶不變；
// 累加器記 sum 與 count。數值只存原始浮點數，顯示格式化一律交給引擎（JS 不自己格式化）。
// toJSON()／fromJSON() 的形狀同 Memory.to_dict()：{M0..M9, ACC:{sum,count}}（Task 25 持久化用）。

const isNum = (v) => typeof v === "number" && Number.isFinite(v);
const isIdx = (i) => Number.isInteger(i) && i >= 0 && i <= 9;
const fail = (error, field) => ({ ok: false, error, field });

export function createMemStore(init) {
  const v = new Array(10).fill(0);
  let sum = 0;
  let count = 0;

  /** 檢查記憶編號與數值；通過回 null，否則回錯誤物件。 */
  function check(i, x) {
    if (!isIdx(i)) return fail("記憶編號須為 0～9 的整數", "index");
    if (!isNum(x)) return fail("數值必須是有限數", "value");
    return null;
  }

  function apply(i, x, op) {
    const bad = check(i, x);
    if (bad) return bad;
    const cur = v[i];
    let next;
    if (op === "+") next = cur + x;
    else if (op === "-") next = cur - x;
    else if (op === "*") next = cur * x;
    else {
      if (x === 0) return fail("除以零", "value");
      next = cur / x;
    }
    if (!Number.isFinite(next)) return fail("計算結果超出範圍（溢位）", "value");
    v[i] = next;
    return { ok: true, value: next };
  }

  const store = {
    store(i, x) {
      const bad = check(i, x);
      if (bad) return bad;
      v[i] = x;
      return { ok: true, value: x };
    },
    recall(i) {
      const bad = check(i, 0);
      return bad || { ok: true, value: v[i] };
    },
    add: (i, x) => apply(i, x, "+"),
    sub: (i, x) => apply(i, x, "-"),
    mul: (i, x) => apply(i, x, "*"),
    div: (i, x) => apply(i, x, "/"),
    /** 累加一個值；回傳目前的 {sum, count}。 */
    accumulate(x) {
      if (!isNum(x)) return fail("數值必須是有限數", "value");
      const next = sum + x;
      if (!Number.isFinite(next)) return fail("計算結果超出範圍（溢位）", "value");
      sum = next;
      count += 1;
      return { ok: true, sum, count };
    },
    clearAccumulator() {
      sum = 0;
      count = 0;
    },
    clearAll() {
      v.fill(0);
      store.clearAccumulator();
    },
    get sum() { return sum; },
    get count() { return count; },
    /** 十格目前的值（陣列複本）。 */
    values: () => v.slice(),
    /** 給引擎 calc/eval 的 MEM：{M0..M9}。 */
    toEngineMem() {
      const m = {};
      for (let i = 0; i < 10; i++) m["M" + i] = v[i];
      return m;
    },
    toJSON() {
      return { ...store.toEngineMem(), ACC: { sum, count } };
    },
  };

  // 由 toJSON 結果還原；驗證各值，未知鍵與不合格的值一律忽略（保持 0）
  if (init && typeof init === "object") {
    for (let i = 0; i < 10; i++) if (isNum(init["M" + i])) v[i] = init["M" + i];
    const acc = init.ACC;
    if (acc && typeof acc === "object" && isNum(acc.sum)
        && Number.isInteger(acc.count) && acc.count >= 0) {
      sum = acc.sum;
      count = acc.count;
    }
  }
  return store;
}

/** 由 toJSON() 的結果還原（等同 createMemStore(d)）。 */
export function fromJSON(d) {
  return createMemStore(d);
}
