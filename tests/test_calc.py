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
    for expr, ch in (("π", "π"), ("é+1", "é")):
        r = evaluate(expr)
        assert r["ok"] is False and "無法辨識的字元「%s」" % ch in r["error"]
    assert "未知的符號「abc」" in evaluate("abc")["error"]
