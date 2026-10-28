"""突變測試（mutation testing）：對 engine/ 逐一植入刻意的錯誤，確認測試會失敗。

用法：python tools/mutate.py
每個突變：套用 -> 執行 pytest -x -q -> 還原原始位元組。
測試仍通過 = 突變「存活」（SURVIVED），代表測試有漏洞，結束碼 1。
突變的 old 文字在檔案中必須恰好出現一次，否則視為工具錯誤（結束碼 1）。
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TIMEOUT = 300  # 每個突變的 pytest 逾時秒數；逾時視為被殺死（killed）

# (檔案, 原文, 突變後文字, 說明)
MUTATIONS = [
    ("engine/tvm.py", "(1 + i * k) * (a - 1) / i", "(a - 1) / i",
     "TVM 年金因子拿掉 BGN 因子 (1+i*k)"),
    ("engine/tvm.py", "** (cy / py) - 1", "** (py / cy) - 1",
     "period_rate 的 cy/py 對調"),
    ("engine/cashflow.py", "total += _disc(c, rate, t)",
     "total += _disc(c, rate, t + 1)", "NPV 從第 1 期起折現（CF0 也被折現）"),
    # old/new 可為 tuple：多處同時修改（IRR 另有格點後備掃描，須一併拿掉）
    ("engine/cashflow.py",
     ("find_root(f, -0.9999, 10.0, 0.1)",
      "grid = [-0.99, -0.95] + [-0.9 + k * 0.02 for k in range(550)]"),
     ("find_root(f, 0.0, 10.0, 0.1)", "grid = []"),
     "IRR 搜尋範圍下限改為 0（含後備格點掃描）"),
    ("engine/stats.py", '"sx": math.sqrt(sxx0 / (n - 1))',
     '"sx": math.sqrt(sxx0 / n)', "雙變數 Sx 分母 n-1 改 n"),
    ("engine/stats.py", 'values["sx"] = math.sqrt(sxx / (n - 1))',
     'values["sx"] = math.sqrt(sxx / n)', "單變數 Sx 分母 n-1 改 n"),
    ("engine/stats.py",
     'a = math.exp(icpt) if model in ("EXP", "PWR") else icpt',
     'a = math.exp(icpt) if model in ("PWR",) else icpt',
     "EXP 模型忘了對 a 取 exp"),
    ("engine/depr.py", "dep = min(dep, avail)", "dep = dep",
     "DB/DBX 折舊未扣到殘值為止（未以 avail 封頂）"),
    ("engine/depr.py", "frac = (13 - m01) / 12.0", "frac = (12 - m01) / 12.0",
     "SL 首年比例 (13-M01) 改 (12-M01)（現行 DB 部分年度已禁用，改打 SL）"),
    ("engine/dates.py", "if a == 31:", "if a == 99:",
     "days_360 拿掉起日 31->30 規則"),
    ("engine/money.py", "return (2 * num + den) // (2 * den)",
     "return num // den", "round_div 四捨五入改無條件捨去"),
    ("engine/money.py", "net = round_div(gross_cents * 10000, 10000 + bp)",
     "net = gross_cents - round_div(gross_cents * bp, 10000)",
     "tax_inclusive 稅額誤用 含稅×稅率"),
    ("engine/fmt.py", 'up = ds[keep] >= "5"', "up = False",
     "format_number 四捨五入改捨去"),
    ("engine/calc.py", "right = _fin(left * right, pos)", "right = right",
     "加法中 a+b% 改成只 ÷100（不乘 a）"),
    ("engine/calc.py", 'self.chain = (mode == "CHAIN")', "self.chain = False",
     "CHAIN 模式被當成 AOS"),
    ("engine/calc.py", "return x * math.pi / 180.0 if angle == \"DEG\" else x",
     "return x", "三角函數輸入拿掉 DEG->弧度換算"),
    ("engine/calc.py", "return -r if x < 0 else r", "return r",
     "cbrt 負數取絕對值（回正根）"),
    ("engine/bridge.py", "if len(blanks) != 1:", "if len(blanks) < 1:",
     "留一格空白檢查改成 >=1 格"),
    ("engine/depr.py", "dep = max(dep, avail / (lif - k))",
     "dep = min(dep, avail / (lif - k))", "DBX 轉直線法改取較小者"),
    ("engine/cashflow.py", "if t > 0 and prev < 0 <= cum:",
     "if t > 0 and prev < 0 < cum:", "回收期邊界（累計剛好為 0）判斷改嚴格"),
]


def _as_tuple(x):
    """字串或字串 tuple 一律轉 tuple。"""
    return x if isinstance(x, tuple) else (x,)


def _git_dirty():
    """engine/ 是否有未提交變更。"""
    out = subprocess.run(["git", "status", "--porcelain", "engine/"],
                         cwd=ROOT, capture_output=True, text=True)
    return out.stdout.strip()


def _snapshot():
    """讀取 engine/ 所有檔案的位元組（用於最後比對）。"""
    snap = {}
    d = os.path.join(ROOT, "engine")
    for name in sorted(os.listdir(d)):
        if name.endswith(".py"):
            with open(os.path.join(d, name), "rb") as f:
                snap[name] = f.read()
    return snap


def _run_pytest():
    """回傳 (通過?, 是否逾時)。"""
    try:
        p = subprocess.run([sys.executable, "-m", "pytest", "-x", "-q"],
                           cwd=ROOT, capture_output=True, timeout=TIMEOUT)
        return p.returncode == 0, False
    except subprocess.TimeoutExpired:
        return False, True


def main():
    """執行全部突變；回傳結束碼。"""
    dirty = _git_dirty()
    if dirty:
        print("拒絕執行：engine/ 有未提交變更：\n" + dirty)
        return 1
    # 先驗證所有 old 恰好出現一次（工具錯誤不可默默略過）
    for rel, old, new, note in MUTATIONS:
        path = os.path.join(ROOT, rel)
        with open(path, "rb") as f:
            text = f.read().decode("utf-8")
        for piece in _as_tuple(old):
            cnt = text.count(piece)
            if cnt != 1:
                print("工具錯誤：%s 中 %r 出現 %d 次（須恰好 1 次）：%s"
                      % (rel, piece, cnt, note))
                return 1
        if old == new:
            print("工具錯誤：突變與原文相同：" + note)
            return 1
    before = _snapshot()
    base_ok, _ = _run_pytest()
    if not base_ok:
        print("拒絕執行：未突變時 pytest 就失敗")
        return 1
    killed = 0
    survivors = []
    try:
        for rel, old, new, note in MUTATIONS:
            path = os.path.join(ROOT, rel)
            with open(path, "rb") as f:
                original = f.read()
            try:
                mutated = original.decode("utf-8")
                for o, n in zip(_as_tuple(old), _as_tuple(new)):
                    mutated = mutated.replace(o, n, 1)
                with open(path, "wb") as f:
                    f.write(mutated.encode("utf-8"))
                passed, timeout = _run_pytest()
            finally:
                with open(path, "wb") as f:
                    f.write(original)
            if passed:
                survivors.append(note)
                print("SURVIVED  %s  [%s]" % (note, rel))
            else:
                killed += 1
                tag = "killed(逾時)" if timeout else "killed"
                print("%s  %s  [%s]" % (tag, note, rel))
    finally:
        if _snapshot() != before:
            print("嚴重錯誤：engine/ 未能還原！請用 git checkout engine/")
            return 1
    total = len(MUTATIONS)
    print("%d/%d mutants killed" % (killed, total))
    return 0 if killed == total else 1


if __name__ == "__main__":
    sys.exit(main())
