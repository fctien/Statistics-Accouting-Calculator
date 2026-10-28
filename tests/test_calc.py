"""calc.py 算式剖析器測試。"""
import pytest

from engine.calc import evaluate


@pytest.mark.parametrize("expr,val", [
    ("1+2*3", 7), ("(1+2)*3", 9), ("2^3^2", 512), ("-2^2", -4),
    ("200+10%", 220), ("200-10%", 180), ("50%", 0.5), ("50*10%", 5),
    ("5!", 120), ("nCr(5,2)", 10), ("nPr(5,2)", 20), ("√16+1", 5),
    ("12", 12), ("1.5+.5", 2), ("1e3", 1000), ("2.5E-3", 0.0025),
    ("3²", 9), ("sqrt(16)", 4), ("inv(4)", 0.25), ("exp(0)", 1),
    ("ln(1)", 0), ("6÷3×2", 4), ("  1 + 2 ", 3), ("2^-1", 0.5),
    ("--3", 3), ("+3", 3), ("0!", 1), ("100+20+10%", 132),
])
def test_eval_aos(expr, val):
    assert abs(evaluate(expr)["values"]["value"] - val) < 1e-12


def test_chain_mode():
    assert evaluate("2+3*4", mode="CHAIN")["values"]["value"] == 20
    assert evaluate("2+3×4^2", mode="CHAIN")["values"]["value"] == 400
    assert evaluate("2+(3*4)", mode="CHAIN")["values"]["value"] == 14
    assert evaluate("200+10%", mode="CHAIN")["values"]["value"] == 220


def test_ans_and_memory():
    assert evaluate("ANS*2+M3", ans=5, mem={"M3": 1})["values"]["value"] == 11
    assert evaluate("M7+1")["values"]["value"] == 1  # 未設定的記憶為 0


@pytest.mark.parametrize("bad", [
    "1/0", "ln(0)", "ln(-1)", "(1+2", "1+2)", "2**", "3.5!", "abc", "",
    "   ", "sqrt(-1)", "(-1)!", "171!", "nCr(5,6)", "nPr(2.5,1)", "nCr(-1,0)",
    "exp(1000)", "10^400", "1+", "2 $ 3", "M10", "sqrt 4", "sqrt(1,2)",
    "nCr(5)", "inv(0)", "(-8)^0.5", "0^-1", "1e", "(" * 500 + "1",
])
def test_errors(bad):
    r = evaluate(bad)
    assert r["ok"] is False
    assert r["field"] == "expr"


def test_error_position():
    assert "4" in evaluate("1+ $")["error"]
    assert "5" in evaluate("12+3$")["error"]


def test_no_eval_used():
    src = open("engine/calc.py", encoding="utf-8").read()
    assert "eval(" not in src
    assert "exec(" not in src


@pytest.mark.parametrize("bad", [
    "1/1e999", "inv(1e999)", "exp(-1e999)", "2^-1e999", "1/(1e308*10)",
    "1e308*10", "1e308+1e308", "(1e200)²", "ANS*10",
])
def test_overflow_is_error(bad):
    r = evaluate(bad, ans=1e308)
    assert r["ok"] is False
    assert r["field"] == "expr"


@pytest.mark.parametrize("bad_mem", [[1], 5, "M1", (1, 2)])
def test_bad_mem_type(bad_mem):
    r = evaluate("1+1", mem=bad_mem)
    assert r["ok"] is False
    assert r["field"] == "expr"


def test_mem_extra_keys_ignored_bad_value_rejected():
    assert evaluate("M1", mem={"M1": 2, "ACC": {"sum": 1}})["ok"] is True
    assert evaluate("1", mem={"M1": "x"})["ok"] is False


def test_identifier_ascii_only():
    # 識別字只接受 ASCII 字母：MicroPython 的 str.isalpha() 只認 ASCII，兩端錯誤訊息須一致
    for expr, ch in (("$", "$"), ("é+1", "é")):
        r = evaluate(expr)
        assert r["ok"] is False and "無法辨識的字元「%s」" % ch in r["error"]
    assert "未知的符號「abc」" in evaluate("abc")["error"]


# ---- 科學函式（B1）----
def _v(expr, **kw):
    r = evaluate(expr, **kw)
    assert r["ok"], r
    return r["values"]["value"]


@pytest.mark.parametrize("expr,val", [
    ("sin(30)", 0.5), ("cos(60)", 0.5), ("tan(45)", 1.0),
    ("asin(0.5)", 30.0), ("acos(0.5)", 60.0), ("atan(1)", 45.0),
    ("log(1000)", 3.0), ("log(1)", 0.0), ("cbrt(27)", 3.0),
    ("cbrt(-27)", -3.0), ("cbrt(0)", 0.0), ("cbrt(64)", 4.0),
    ("pi*2", 6.283185307179586), ("π*2", 6.283185307179586),
    ("e^2", 7.38905609893065), ("e", 2.718281828459045),
    ("1e3", 1000.0), ("2e3", 2000.0), ("1e-2+e", 0.01 + 2.718281828459045),
    ("sin(30)+log(100)*2", 4.5), ("-sin(30)", -0.5),
])
def test_scientific_deg(expr, val):
    assert abs(_v(expr) - val) < 1e-12


def test_cbrt_negative_not_abs():
    assert _v("cbrt(-8)") == -2.0
    assert _v("cbrt(-1000)") == -10.0


def test_rad_mode():
    assert abs(_v("sin(1)", angle="RAD") - 0.8414709848078965) < 1e-15
    assert abs(_v("atan(1)", angle="RAD") - 0.7853981633974483) < 1e-15
    assert abs(_v("sin(pi/6)", angle="RAD") - 0.5) < 1e-12
    # 同一算式 DEG 與 RAD 結果不同（換算確實生效）
    assert abs(_v("sin(30)") - _v("sin(30)", angle="RAD")) > 0.5


def test_snap_to_zero():
    assert _v("sin(180)") == 0.0
    assert _v("cos(90)") == 0.0
    assert _v("tan(180)") == 0.0
    assert _v("sin(pi)", angle="RAD") == 0.0
    assert _v("cos(pi/2)", angle="RAD") == 0.0
    # 真的很小的輸入不可被歸零
    assert _v("sin(1e-10)", angle="RAD") == pytest.approx(1e-10, rel=1e-9)
    assert _v("sin(1e-12)") != 0.0


@pytest.mark.parametrize("expr,angle", [
    ("tan(90)", "DEG"), ("tan(270)", "DEG"), ("tan(pi/2)", "RAD"),
])
def test_tan_singularity(expr, angle):
    r = evaluate(expr, angle=angle)
    assert r["ok"] is False and "tan 在此角度未定義" in r["error"]


@pytest.mark.parametrize("bad", [
    "asin(2)", "acos(-1.5)", "asin(-1.0001)", "log(0)", "log(-1)",
    "2e", "2pi", "2 e", "e3", "pi(1)", "sin", "sin(1,2)", "cbrt()",
])
def test_scientific_errors(bad):
    r = evaluate(bad)
    assert r["ok"] is False and r["field"] == "expr"


def test_implicit_multiply_error_has_position():
    r = evaluate("2e")
    assert r["ok"] is False and "第 2 個字元" in r["error"]


def test_bad_angle():
    for a in ("deg", "GRAD", None, 1, True):
        r = evaluate("sin(1)", angle=a)
        assert r["ok"] is False and r["field"] == "angle"


def test_chain_mode_scientific():
    assert abs(_v("sin(30)+1", mode="CHAIN") - 1.5) < 1e-12


def test_large_angle_reduction():
    assert _v("sin(360*1000000)") == 0.0
    assert _v("sin(180*1000000)") == 0.0
    assert _v("cos(90+360*1000000)") == 0.0
    assert _v("cos(360*1000000)") == 1.0
    assert abs(_v("tan(45+360*1000000)") - 1.0) < 1e-9
    assert abs(_v("sin(30+360*1000000)") - 0.5) < 1e-9
    assert abs(_v("sin(-30)") + 0.5) < 1e-12
    assert _v("sin(-180)") == 0.0
    r = evaluate("tan(90+360*1000000)")
    assert r["ok"] is False and "tan 在此角度未定義" in r["error"]
    assert evaluate("tan(-90)")["ok"] is False
    assert _v("tan(180*1000000)") == 0.0


def test_small_angle_kept_and_rad_reduction():
    assert _v("sin(1e-12)", angle="RAD") == pytest.approx(1e-12, rel=1e-9)
    assert _v("sin(-1e-12)") != 0.0
    assert abs(_v("sin(1+2*pi)", angle="RAD") - 0.8414709848078965) < 1e-12
    assert abs(_v("sin(1+2*pi*1000)", angle="RAD") - 0.8414709848078965) < 1e-9


def test_large_angle_non_multiple_needs_reduction():
    # 非 90 倍數的超大角度：沒有 fmod 縮減時誤差會超過容許值
    assert abs(_v("sin(30+360*1000000000000)") - 0.5) < 1e-9
    assert abs(_v("cos(60-360*1000000000000)") - 0.5) < 1e-9
    assert abs(_v("tan(45+360*1000000000000)") - 1.0) < 1e-9
