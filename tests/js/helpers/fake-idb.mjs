// 測試用：最小的記憶體版 indexedDB（只支援 idb.js 用到的 open／createObjectStore／get／put／getAll／delete／clear）。
export function makeFakeIndexedDB({ failOpen = false, failPut = false } = {}) {
  const dbs = new Map(); // name -> {version, stores: Map(name -> {keyPath, data: Map})}
  const defer = (fn) => setTimeout(fn, 0);
  return {
    dbs,
    open(name, version) {
      const req = {};
      defer(() => {
        if (failOpen) return req.onerror?.({});
        let rec = dbs.get(name);
        const upgrade = !rec || rec.version < version;
        if (!rec) rec = { version: 0, stores: new Map() };
        dbs.set(name, rec);
        const db = {
          objectStoreNames: { contains: (n) => rec.stores.has(n) },
          createObjectStore(n, { keyPath }) { rec.stores.set(n, { keyPath, data: new Map() }); },
          close() {},
          transaction(storeName) {
            const store = rec.stores.get(storeName);
            if (!store) throw new Error("NotFoundError");
            const tx = { pending: 0 };
            const request = (fn, isWrite) => {
              const r = {};
              tx.pending += 1;
              defer(() => {
                if (isWrite && failPut) {
                  tx.onabort?.({});
                  return;
                }
                r.result = fn();
                r.onsuccess?.({});
                tx.pending -= 1;
                if (tx.pending === 0) defer(() => tx.oncomplete?.({}));
              });
              return r;
            };
            tx.objectStore = () => ({
              get: (k) => request(() => structuredClone(store.data.get(k))),
              getAll: () => request(() => [...store.data.values()].map((v) => structuredClone(v))),
              put: (v) => request(() => { store.data.set(v[store.keyPath], structuredClone(v)); return v[store.keyPath]; }, true),
              delete: (k) => request(() => { store.data.delete(k); }, true),
              clear: () => request(() => { store.data.clear(); }, true),
            });
            return tx;
          },
        };
        req.result = db;
        if (upgrade) {
          req.onupgradeneeded?.({});
          rec.version = version;
        }
        req.onsuccess?.({});
      });
      return req;
    },
  };
}
