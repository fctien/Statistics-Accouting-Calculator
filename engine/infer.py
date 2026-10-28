"""信賴區間與假設檢定（confidence intervals & hypothesis tests），供「統計」頁使用。

功能（公開函式皆回 ok／err）：
    ci_mean_z   平均數 CI，已知 σ（z）：margin = z·σ/√n（Excel CONFIDENCE.NORM）
    ci_mean_t   平均數 CI，未知 σ（t）：原始資料 X 或摘要 (mean, sx, n)（Excel CONFIDENCE.T）
    ci_prop     比例 CI：Wald（主要）並同時回 Wilson（score）區間
    t1          單樣本 t 檢定（one-sample t test）
    t2          兩獨立樣本 t 檢定：合併變異數（pooled，Excel T.TEST type 2）或 Welch（type 3）
    tpaired     成對 t 檢定（paired t test，Excel T.TEST type 1）
    chi_gof     卡方適合度檢定（goodness of fit），df = k−1
                （期望值由使用者給定；不做「估計參數」的自由度調整 k−1−m）
    chi_ind     卡方獨立性檢定（test of independence），df = (r−1)(c−1)
p 值一律由 engine/dist.py 的尾端機率直接取得（左尾 value、右尾 right、雙尾 two），
不以 1−cdf 計算（極小 p 值才保有相對精度）；臨界值用 dist 的 inv（雙尾 two）。
檢定的決策：p ≤ α 時拒絕 H0；結論文字「在 α=0.05 下拒絕 H0」或「在 α=0.05 下不拒絕 H0」。
樣本不足、變異數為 0（t 統計量未定義）、表格列／行總和為 0 等一律回錯誤，絕不回 inf／nan。
「變異數為 0」的判定：樣本標準差 ≤ ZERO_SD_REL × max|x_i|（ZERO_SD_REL = 64·機器 epsilon）
時視為 0。例：前後測恰差 1 的一位小數資料，浮點數相減後差值只有 1e-16 級的雜訊，
若不視為 0 會得到 t≈1e16、p≈1e-48 的錯誤「拒絕 H0」。
僅用 math 與 engine 內部匯入；無 I/O。
"""
import math

from engine import dist
from engine.result import err, is_finite, ok

DEFAULT_ALPHA = 0.05
PROB_SUM_TOL = 1e-9      # 機率向量總和與 1 的容許差
SMALL_EXPECTED = 5.0     # 期望次數門檻
SMALL_SHARE = 0.2        # 期望次數 < 5 的格數比例上限
_MAX_X = 1e300
ZERO_SD_REL = 64 * 2.220446049250313e-16   # 標準差視為 0 的相對門檻（64·eps）
_SIDES = ("less", "greater")
_SMALL_SAMPLE = "樣本太小，常態近似可能不準"
_OVERFLOW = "計算結果超出範圍（溢位）"


class _InferError(Exception):
    """參數或計算錯誤（內部使用），帶中文訊息與欄位名。"""

    def __init__(self, message, field=None):
        super().__init__(message)  # MicroPython 相容
        self.message = message
        self.field = field


# ---------------------------------------------------------------- 參數檢查

def _is_num(v):
    return (not isinstance(v, bool) and isinstance(v, (int, float))
            and is_finite(v) and abs(v) <= _MAX_X)


def _need(v, field):
    """必填有限數字。"""
    if v is None:
        raise _InferError("請輸入 %s" % field, field)
    if not _is_num(v):
        raise _InferError("%s 必須是有限數字" % field, field)
    return float(v)


def _need_int(v, field, lo):
    """必填整數 ≥ lo（接受整數值的 float）。"""
    x = _need(v, field)
    if x != int(x):
        raise _InferError("%s 必須是整數" % field, field)
    if x < lo:
        raise _InferError("%s 必須 ≥ %d" % (field, lo), field)
    return int(x)


def _need_list(v, field, min_len, nonneg=False):
    """必填數值 list，長度 ≥ min_len。"""
    if v is None:
        raise _InferError("請輸入 %s" % field, field)
    if not isinstance(v, (list, tuple)):
        raise _InferError("%s 必須是數字清單" % field, field)
    for x in v:
        if not _is_num(x):
            raise _InferError("%s 含非數值或非有限數" % field, field)
        if nonneg and x < 0:
            raise _InferError("%s 不可為負數" % field, field)
    if len(v) < min_len:
        raise _InferError("%s 至少需要 %d 筆資料（目前 n=%d）"
                          % (field, min_len, len(v)), field)
    return [float(x) for x in v]


def _open_unit(v, field):
    """0 < v < 1。"""
    x = _need(v, field)
    if not 0.0 < x < 1.0:
        raise _InferError("%s 必須介於 0 與 1 之間（不含 0、1）" % field, field)
    return x


def _alpha(v):
    return DEFAULT_ALPHA if v is None else _open_unit(v, "ALPHA")


def _side(tails, alt):
    """回傳 "two"、"less" 或 "greater"。tails 省略為 2；單尾須指定 alternative。"""
    if alt is not None and alt not in _SIDES:
        raise _InferError("ALT 必須是 less 或 greater", "ALT")
    t = 2 if tails is None else _need(tails, "TAILS")
    if t != 1 and t != 2:
        raise _InferError("TAILS 必須是 1 或 2", "TAILS")
    if t == 2:
        if alt is not None:
            raise _InferError("雙尾檢定不可指定 ALT（單尾請設 TAILS=1）", "ALT")
        return "two"
    if alt is None:
        raise _InferError("單尾檢定請指定 ALT（less 或 greater）", "ALT")
    return alt


def _fin(v):
    """計算中間值必須有限，否則視為溢位錯誤。"""
    if not is_finite(v):
        raise _InferError(_OVERFLOW, None)
    return v


def _run(fn):
    """執行計算並把內部例外轉成 err。"""
    try:
        values, warnings = fn()
        return ok(values, warnings)
    except _InferError as e:
        return err(e.message, e.field)
    except (OverflowError, ValueError, ZeroDivisionError):
        return err(_OVERFLOW, None)


# ---------------------------------------------------------------- 共用計算

def _mean_var(xs):
    """(n, 平均, 樣本變異數)；兩遍法。

    全部相同，或標準差 ≤ ZERO_SD_REL × max|x_i|（只剩浮點捨入雜訊）時變異數視為 0，
    由呼叫端回「標準差為 0、t 統計量未定義」錯誤，不產生假的巨大 t 值。
    """
    n = len(xs)
    mean = _fin(sum(xs) / n)
    if min(xs) == max(xs):
        return n, xs[0], 0.0
    ss = 0.0
    for x in xs:
        d = x - mean
        ss += d * d
    var = _fin(ss / (n - 1))
    scale = max(abs(min(xs)), abs(max(xs)))
    if math.sqrt(var) <= ZERO_SD_REL * scale:
        return n, mean, 0.0
    return n, mean, var


def _unwrap(res):
    """取 dist 的結果；dist 回錯誤時轉成本模組錯誤。"""
    if not res["ok"]:
        raise _InferError(res["error"], None)
    return res["values"]


def _t_p(t, df, side):
    """t 分配的 p 值：直接取對應尾端（不經 1−cdf）。"""
    v = _unwrap(dist.t_dist("cdf", df, x=_fin(t)))
    return v["two"] if side == "two" else (
        v["value"] if side == "less" else v["right"])


def _decision(p, alpha):
    """回傳 (是否拒絕, 結論文字)；p ≤ α 拒絕 H0。"""
    reject = p <= alpha
    return reject, "在 α=%g 下%s H0" % (alpha, "拒絕" if reject else "不拒絕")


def _test_values(stat_key, stat, df, p, alpha, extra):
    reject, text = _decision(p, alpha)
    values = {stat_key: stat, "df": df, "p": p, "alpha": alpha,
              "reject": reject, "conclusion": text}
    values.update(extra)
    return values


def _t_result(t, df, side, alpha, extra):
    return _test_values("t", t, df, _t_p(t, df, side), alpha, extra)


def _zero_sd(field, what="樣本標準差 Sx "):
    return _InferError("%s為 0（所有值相同或只差浮點捨入誤差），t 統計量未定義" % what, field)


# ---------------------------------------------------------------- 信賴區間

def ci_mean_z(mean, sigma, n, conf):
    """平均數信賴區間（已知 σ）：mean ± z·σ/√n。"""
    def calc():
        m = _need(mean, "MEAN")
        s = _need(sigma, "SIGMA")
        if s <= 0:
            raise _InferError("SIGMA 必須 > 0", "SIGMA")
        nn = _need_int(n, "N", 1)
        c = _open_unit(conf, "CONF")
        z = _unwrap(dist.normal("inv", 0, 1, prob=1.0 - c))["two"]
        se = s / math.sqrt(nn)
        margin = _fin(z * se)
        return {"z_crit": z, "se": se, "margin": margin,
                "lower": _fin(m - margin), "upper": _fin(m + margin)}, []
    return _run(calc)


def ci_mean_t(xs=None, mean=None, sx=None, n=None, conf=None):
    """平均數信賴區間（未知 σ）：mean ± t(df=n−1)·Sx/√n；X 或 (MEAN, SX, N) 擇一。"""
    def calc():
        if xs is not None:
            if mean is not None or sx is not None or n is not None:
                raise _InferError("X 與 MEAN／SX／N 只能擇一輸入", None)
            nn, m, var = _mean_var(_need_list(xs, "X", 2))
            if var == 0:
                raise _InferError("樣本標準差 Sx 為 0（所有值相同或只差浮點"
                                  "捨入誤差），信賴區間無意義", "X")
            s = math.sqrt(var)
        else:
            m = _need(mean, "MEAN")
            s = _need(sx, "SX")
            if s <= 0:
                raise _InferError("SX 必須 > 0", "SX")
            nn = _need_int(n, "N", 2)
        c = _open_unit(conf, "CONF")
        df = nn - 1
        t = _unwrap(dist.t_dist("inv", df, prob=1.0 - c))["two"]
        se = _fin(s / math.sqrt(nn))
        margin = _fin(t * se)
        return {"n": nn, "mean": m, "sx": s, "df": df, "t_crit": t,
                "se": se, "margin": margin,
                "lower": _fin(m - margin), "upper": _fin(m + margin)}, []
    return _run(calc)


def ci_prop(x, n, conf):
    """比例信賴區間：Wald p̂ ± z·√(p̂(1−p̂)/n)，另附 Wilson（score）區間。"""
    def calc():
        nn = _need_int(n, "N", 1)
        k = _need_int(x, "X", 0)
        if k > nn:
            raise _InferError("X（成功數）不可大於 N", "X")
        c = _open_unit(conf, "CONF")
        z = _unwrap(dist.normal("inv", 0, 1, prob=1.0 - c))["two"]
        p = k / nn
        q = (nn - k) / nn
        se = math.sqrt(p * q / nn)
        margin = z * se
        z2 = z * z
        den = 1.0 + z2 / nn
        center = (p + z2 / (2.0 * nn)) / den
        half = z * math.sqrt(p * q / nn + z2 / (4.0 * nn * nn)) / den
        warnings = []
        if k < 5 or nn - k < 5:          # n·p̂ < 5 或 n(1−p̂) < 5
            warnings.append(_SMALL_SAMPLE)
        lower, upper = p - margin, p + margin
        if lower < 0 or upper > 1:
            warnings.append("Wald 區間超出 [0, 1]，建議參考 Wilson 區間")
        # Wilson 區間理論上必在 [0, 1] 內；夾住只修正最後一位的捨入
        return {"p_hat": p, "se": se, "z_crit": z, "method": "Wald",
                "margin": margin, "lower": lower, "upper": upper,
                "wilson_method": "Wilson", "wilson_center": center,
                "wilson_margin": half,
                "wilson_lower": max(0.0, center - half),
                "wilson_upper": min(1.0, center + half)}, warnings
    return _run(calc)


# ---------------------------------------------------------------- t 檢定

def t1(xs, mu0, tails=None, alt=None, alpha=None):
    """單樣本 t 檢定：t = (x̄ − μ0)/(Sx/√n)，df = n−1。"""
    def calc():
        data = _need_list(xs, "X", 2)
        m0 = _need(mu0, "MU0")
        side = _side(tails, alt)
        a = _alpha(alpha)
        n, m, var = _mean_var(data)
        if var == 0:
            raise _zero_sd("X")
        sd = math.sqrt(var)
        se = sd / math.sqrt(n)
        t = _fin((m - m0) / se)
        return _t_result(t, n - 1, side, a, {
            "n": n, "mean": m, "sx": sd, "se": se, "mu0": m0}), []
    return _run(calc)


def t2(xs, ys, equal_var=False, tails=None, alt=None, alpha=None):
    """兩獨立樣本 t 檢定：equal_var=True 合併變異數，False 為 Welch。"""
    def calc():
        a_data = _need_list(xs, "X", 2)
        b_data = _need_list(ys, "Y", 2)
        if not isinstance(equal_var, bool):
            raise _InferError("EQUAL_VAR 必須是 true 或 false", "EQUAL_VAR")
        side = _side(tails, alt)
        al = _alpha(alpha)
        n1, m1, v1 = _mean_var(a_data)
        n2, m2, v2 = _mean_var(b_data)
        diff = _fin(m1 - m2)
        extra = {"n_x": n1, "n_y": n2, "mean_x": m1, "mean_y": m2,
                 "diff": diff, "sx": math.sqrt(v1), "sy": math.sqrt(v2)}
        if equal_var:
            df = n1 + n2 - 2
            sp2 = _fin(((n1 - 1) * v1 + (n2 - 1) * v2) / df)
            if sp2 == 0:
                raise _zero_sd(None, "合併標準差 Sp ")
            se = math.sqrt(sp2 * (1.0 / n1 + 1.0 / n2))
            extra["sp"] = math.sqrt(sp2)
            extra["method"] = "pooled"
        else:
            a = v1 / n1
            b = v2 / n2
            if a + b == 0:
                raise _zero_sd(None, "兩組樣本標準差")
            se = math.sqrt(a + b)
            # Welch–Satterthwaite 自由度（非整數）
            den = a * a / (n1 - 1) + b * b / (n2 - 1)
            df = _fin((a + b) * (a + b) / den)
            extra["method"] = "Welch"
        extra["se"] = se
        return _t_result(_fin(diff / se), df, side, al, extra), []
    return _run(calc)


def tpaired(xs, ys, tails=None, alt=None, alpha=None):
    """成對 t 檢定：對差值 d = X − Y 做單樣本 t 檢定（μ0 = 0）。"""
    def calc():
        a_data = _need_list(xs, "X", 2)
        b_data = _need_list(ys, "Y", 1)
        if len(a_data) != len(b_data):
            raise _InferError("成對資料 X、Y 長度必須相同", "Y")
        side = _side(tails, alt)
        al = _alpha(alpha)
        d = [_fin(x - y) for x, y in zip(a_data, b_data)]
        n, m, var = _mean_var(d)
        if var == 0:
            raise _zero_sd(None, "差值的標準差")
        sd = math.sqrt(var)
        se = sd / math.sqrt(n)
        return _t_result(_fin(m / se), n - 1, side, al, {
            "n": n, "mean_diff": m, "sd": sd, "se": se}), []
    return _run(calc)


# ---------------------------------------------------------------- 卡方

def _small_warning(expected, warnings):
    """期望次數 < 5 的格數超過 20% 時加警告。"""
    small = sum(1 for e in expected if e < SMALL_EXPECTED)
    if small > SMALL_SHARE * len(expected):
        warnings.append("期望次數 < 5 的格數占 %d/%d（超過 20%%），"
                        "卡方近似可能不準" % (small, len(expected)))


def _chi_result(obs, expected, df, alpha):
    chi = 0.0
    for o, e in zip(obs, expected):
        d = o - e
        chi += _fin(d * d / e)
    chi = _fin(chi)
    p = _unwrap(dist.chi2("cdf", df, x=chi))["right"]
    return _test_values("chi2", chi, df, p, alpha, {})


def chi_gof(observed, expected=None, probs=None, alpha=None):
    """卡方適合度：期望次數由 expected、機率向量 probs 或均等分配（皆省略）取得。

    expected 總和須等於觀察總和（相對差 ≤ 1e-9）；df = k−1，不扣除估計參數個數。
    """
    def calc():
        obs = _need_list(observed, "OBS", 2, nonneg=True)
        k = len(obs)
        total = _fin(sum(obs))
        if total <= 0:
            raise _InferError("OBS 總和為 0，無法檢定", "OBS")
        if expected is not None and probs is not None:
            raise _InferError("EXP 與 PROBS 只能擇一輸入", None)
        warnings = []
        if expected is not None:
            exp = _need_list(expected, "EXP", 1)
            if len(exp) != k:
                raise _InferError("EXP 個數須與 OBS 相同", "EXP")
            if min(exp) <= 0:
                raise _InferError("EXP（期望次數）必須 > 0", "EXP")
            if abs(_fin(sum(exp)) - total) > PROB_SUM_TOL * total:
                raise _InferError("期望次數總和必須等於觀察次數總和，"
                                  "或改用機率 PROBS", "EXP")
        elif probs is not None:
            ps = _need_list(probs, "PROBS", 1)
            if len(ps) != k:
                raise _InferError("PROBS 個數須與 OBS 相同", "PROBS")
            if min(ps) <= 0:
                raise _InferError("PROBS 每個機率必須 > 0", "PROBS")
            if abs(sum(ps) - 1.0) > PROB_SUM_TOL:
                raise _InferError("PROBS 總和必須為 1", "PROBS")
            exp = [total * p for p in ps]
        else:
            exp = [total / k] * k
        _small_warning(exp, warnings)
        values = _chi_result(obs, exp, k - 1, _alpha(alpha))
        values["expected"] = exp
        return values, warnings
    return _run(calc)


def _need_table(table):
    """r×c 表（list of rows），r、c ≥ 2，元素為非負有限數。"""
    if table is None:
        raise _InferError("請輸入 TABLE", "TABLE")
    if not isinstance(table, (list, tuple)) or len(table) < 2:
        raise _InferError("TABLE 至少需要 2 列", "TABLE")
    rows = []
    for row in table:
        if not isinstance(row, (list, tuple)):
            raise _InferError("TABLE 每一列必須是數字清單", "TABLE")
        rows.append(_need_list(row, "TABLE", 2, nonneg=True))
    c = len(rows[0])
    for row in rows:
        if len(row) != c:
            raise _InferError("TABLE 每一列的欄數必須相同", "TABLE")
    return rows


def chi_ind(table, alpha=None):
    """卡方獨立性：E_ij = 列總和 × 行總和 / 總數，df = (r−1)(c−1)。"""
    def calc():
        rows = _need_table(table)
        a = _alpha(alpha)
        r, c = len(rows), len(rows[0])
        row_sums = [_fin(sum(row)) for row in rows]
        col_sums = [_fin(sum(row[j] for row in rows)) for j in range(c)]
        for i, s in enumerate(row_sums):
            if s == 0:
                raise _InferError("第 %d 列總和為 0，無法檢定" % (i + 1), "TABLE")
        for j, s in enumerate(col_sums):
            if s == 0:
                raise _InferError("第 %d 行總和為 0，無法檢定" % (j + 1), "TABLE")
        total = _fin(sum(row_sums))
        exp = [[row_sums[i] * col_sums[j] / total for j in range(c)]
               for i in range(r)]
        flat_o = [x for row in rows for x in row]
        flat_e = [x for row in exp for x in row]
        warnings = []
        _small_warning(flat_e, warnings)
        df = (r - 1) * (c - 1)
        values = _chi_result(flat_o, flat_e, df, a)
        values["expected"] = exp
        return values, warnings
    return _run(calc)
