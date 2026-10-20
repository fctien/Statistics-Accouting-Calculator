"""engine/fmt.py 測試：顯示格式（format_number）與輸入解析（parse_number）。"""
from engine.fmt import format_number, parse_number


def test_format_fixed():
    assert format_number(1234.5, 2) == "1,234.50"
    assert format_number(2.675, 2) == "2.68"
    assert format_number(-0.005, 2) == "-0.01"
    assert format_number(1234.5, 2, "eu") == "1.234,50"


def test_format_fixed_more():
    assert format_number(0, 2) == "0.00"
    assert format_number(1234567, 0) == "1,234,567"
    assert format_number(0.5, 0) == "1"
    assert format_number(-0.5, 0) == "-1"
    assert format_number(999.999, 2) == "1,000.00"
    assert format_number(0.1 + 0.2, 9) == "0.300000000"
    assert format_number(1.5, 9) == "1.500000000"
    assert format_number(123.456, 9, "eu") == "123,456000000"
    assert format_number(1000000, 0, "eu") == "1.000.000"
    assert format_number(-1234.5, 2) == "-1,234.50"


def test_format_exponent_forms():
    assert format_number(1.5e12, 2) == "1,500,000,000,000.00"
    assert format_number(1e-5, 6) == "0.000010"
    assert format_number(1e-5, 2) == "0.00"
    assert format_number(1.5e-5, 5) == "0.00002"
    assert format_number(1e20, 0) == "100,000,000,000,000,000,000"
    assert format_number(4e-6, 5) == "0.00000"
    assert format_number(5e-6, 5) == "0.00001"


def test_format_no_negative_zero():
    assert format_number(-0.0, 2) == "0.00"
    assert format_number(-0.001, 2) == "0.00"
    assert format_number(-0.0, None) == "0"
    assert format_number(-0.0, 0) == "0"


def test_format_errors_never_raise():
    err = "錯誤"
    assert format_number(float("nan"), 2) == err
    assert format_number(float("inf"), 2) == err
    assert format_number(float("-inf"), None) == err
    assert format_number(1.0, 10) == err
    assert format_number(1.0, -1) == err
    assert format_number(1.0, 2.5) == err
    assert format_number(1.0, "2") == err
    assert format_number(1.0, True) == err
    assert format_number("abc", 2) == err
    assert format_number(None, 2) == err
    assert format_number(1.0, 2, "xx") == err


def test_format_float_mode():
    assert format_number(1 / 3, None) == "0.3333333333"
    assert format_number(1.5e12, None) == "1.5E12"


def test_format_float_mode_more():
    assert format_number(0, None) == "0"
    assert format_number(5, None) == "5"
    assert format_number(1234.5, None) == "1,234.5"
    assert format_number(1234.5, None, "eu") == "1.234,5"
    assert format_number(-2.34e-10, None) == "-2.34E-10"
    assert format_number(1e10, None) == "1E10"
    assert format_number(9999999999.0, None) == "9,999,999,999"
    assert format_number(1e-9, None) == "0.000000001"
    assert format_number(1.5e-10, None, "eu") == "1,5E-10"
    assert format_number(2 / 3, None) == "0.6666666667"
    assert format_number(123456789.123456, None) == "123,456,789.1"
    assert format_number(0.1 + 0.2, None) == "0.3"
    assert format_number(1.23456789012e15, None) == "1.23456789E15"


def test_parse_number_locale():
    assert parse_number("1,000.50", "us") == 1000.5
    assert parse_number("1.000,50", "eu") == 1000.5
    assert parse_number("1.000,50", "us") is None
    assert parse_number("１２３", "us") == 123


def test_parse_number_misc():
    assert parse_number("  12.5  ") == 12.5
    assert parse_number("+3") == 3.0
    assert parse_number("-3") == -3.0
    assert parse_number("－３") == -3.0
    assert parse_number("1e3") == 1000.0
    assert parse_number("1.5E-2") == 0.015
    assert parse_number(".5") == 0.5
    assert parse_number("1,234,567") == 1234567.0
    assert parse_number("1,00.5") is None
    assert parse_number("1,0000") is None
    assert parse_number(",100") is None
    assert parse_number("1234,567") is None
    assert parse_number("12,34") is None
    assert parse_number("1.234.567,5", "eu") == 1234567.5
    assert parse_number("3,5", "eu") == 3.5
    assert parse_number("1,5", "eu") == 1.5


def test_parse_number_invalid():
    for s in ["", "   ", "abc", "1e", "e3", "--1", "1-", ".", "+", "1.2.3",
              "1e999", "-1e999", "nan", "inf", "1 000", "1e3.5", "0x10",
              "1__0", "١٢"]:
        assert parse_number(s) is None, s
    assert parse_number(None) is None
    assert parse_number(5) is None
    assert parse_number("1", "xx") is None
