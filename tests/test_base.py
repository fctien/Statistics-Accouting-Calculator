"""進位轉換與位元運算（engine/base.py）與 bridge base 路由測試。"""
import json

import pytest

from engine import base
from engine.bridge import call
from golden import runner


def _call(req):
    return json.loads(call(json.dumps(req)))


def _conv(text, frm, width, signed=False):
    return _call({"sheet": "base", "action": "convert", "settings": {},
                  "inputs": {"TEXT": text, "FROM": frm, "WIDTH": width,
                             "SIGNED": signed}})


def _bw(op, a, b, frm, width, signed=False):
    return _call({"sheet": "base", "action": "bitwise", "settings": {},
                  "inputs": {"OP": op, "A": a, "B": b, "FROM": frm,
                             "WIDTH": width, "SIGNED": signed}})


def _four(res):
    v = res["values"]
    return v["BIN"], v["OCT"], v["DEC"], v["HEX"]


def test_base_golden(golden_cases):
    cases = golden_cases("base")
    assert len(cases) >= 20
    assert all(isinstance(c["expected"], str) for c in cases)
    assert runner.run(cases, _call) == []


def test_convert_basic_unsigned():
    r = _conv("10", 10, 8)
    assert r["ok"]
    assert _four(r) == ("00001010", "012", "10", "0A")
    assert r["display"] == {"BIN": "00001010", "OCT": "012", "DEC": "10",
                            "HEX": "0A"}


def test_convert_signed_negative_pattern():
    assert _four(_conv("-1", 10, 8, True)) == ("11111111", "377", "-1", "FF")
    assert _four(_conv("-128", 10, 8, True))[3] == "80"
    assert _four(_conv("80", 16, 8, True))[2] == "-128"
    assert _four(_conv("ff", 16, 8, True))[2] == "-1"


def test_convert_no_thousands_separator_in_display():
    r = _conv("1234567", 10, 32)
    assert r["display"]["DEC"] == "1234567"


def test_convert_64_bit_edges():
    r = _conv(str(2 ** 63 - 1), 10, 64, True)
    assert r["values"]["HEX"] == "7FFFFFFFFFFFFFFF"
    r = _conv("FFFFFFFFFFFFFFFF", 16, 64)
    assert r["values"]["DEC"] == "18446744073709551615"
    r = _conv("8000000000000000", 16, 64, True)
    assert r["values"]["DEC"] == "-9223372036854775808"


@pytest.mark.parametrize("text, frm, width, signed", [
    ("256", 10, 8, False),
    ("128", 10, 8, True),
    ("-129", 10, 8, True),
    ("-1", 10, 8, False),
    ("100", 16, 8, False),          # 0x100 超出 8 位
    ("1FF", 16, 8, True),
    ("18446744073709551616", 10, 64, False),
    ("9223372036854775808", 10, 64, True),
])
def test_out_of_range_is_error_not_wrapped(text, frm, width, signed):
    r = _conv(text, frm, width, signed)
    assert r["ok"] is False
    assert "範圍" in r["error"]
    assert r["field"] == "TEXT"


def test_range_boundaries_accepted():
    assert _conv("255", 10, 8)["ok"]
    assert _conv("127", 10, 8, True)["ok"]
    assert _conv("-128", 10, 8, True)["ok"]


@pytest.mark.parametrize("text, frm", [
    ("1.5", 10), ("A.8", 16), ("1.0", 10), ("", 10), ("   ", 10),
    ("_", 2), ("-", 10),
])
def test_non_integer_or_empty_is_error(text, frm):
    r = _conv(text, frm, 16)
    assert r["ok"] is False and r["field"] == "TEXT"


def test_illegal_character_reports_position():
    r = _conv("12G4", 16, 16)
    assert not r["ok"]
    assert "第 3 個字元" in r["error"] and "G" in r["error"]
    r = _conv("1012", 2, 8)
    assert "第 4 個字元" in r["error"]
    r = _conv("789", 8, 16)
    assert "第 2 個字元" in r["error"]
    r = _conv("12a", 10, 16)
    assert "第 3 個字元" in r["error"]


def test_position_counts_original_text_with_separators():
    r = _conv("1111 2", 2, 8)
    assert "第 6 個字元" in r["error"]


def test_grouping_spaces_underscores_and_case():
    assert _conv("ff_ff", 16, 16)["values"]["DEC"] == "65535"
    assert _conv("1111 0000", 2, 8)["values"]["HEX"] == "F0"
    assert _conv("  Ab  ", 16, 8)["values"]["DEC"] == "171"
    assert _conv("1 000", 10, 16)["values"]["DEC"] == "1000"


def test_prefix_rules():
    assert _conv("0xFF", 16, 8)["values"]["DEC"] == "255"
    assert _conv("0XFF", 16, 8)["values"]["DEC"] == "255"
    assert _conv("0b1010", 2, 8)["values"]["DEC"] == "10"
    assert _conv("0o17", 8, 8)["values"]["DEC"] == "15"
    # 前綴與進位不符 -> 錯誤
    assert not _conv("0xFF", 10, 16)["ok"]
    assert not _conv("0b1010", 8, 8)["ok"]
    assert not _conv("0o17", 2, 8)["ok"]
    # 16 進位的 0b 是數字 0 與 B，不是前綴
    assert _conv("0B1", 16, 8)["values"]["DEC"] == "177"
    # 只有前綴沒有數字
    assert not _conv("0x", 16, 8)["ok"]


def test_sign_only_allowed_in_decimal():
    assert _conv("+5", 10, 8)["values"]["DEC"] == "5"
    r = _conv("-F", 16, 8, True)
    assert not r["ok"] and "第 1 個字元" in r["error"]


def test_bad_parameters():
    assert not _conv("1", 3, 8)["ok"]
    assert not _conv("1", 10, 12)["ok"]
    assert not _conv("1", 10, 8, "yes")["ok"]
    assert not _call({"sheet": "base", "action": "convert", "settings": {},
                      "inputs": {"TEXT": 10, "FROM": 10, "WIDTH": 8}})["ok"]
    assert not _call({"sheet": "base", "action": "convert", "settings": {},
                      "inputs": {"FROM": 10, "WIDTH": 8}})["ok"]


def test_bitwise_and_or_xor():
    assert _bw("AND", "12", "10", 10, 8)["values"]["DEC"] == "8"
    assert _bw("OR", "12", "10", 10, 8)["values"]["DEC"] == "14"
    assert _bw("XOR", "12", "10", 10, 8)["values"]["DEC"] == "6"
    r = _bw("AND", "F0", "3C", 16, 8)
    assert _four(r) == ("00110000", "060", "48", "30")


def test_bitwise_signed_and():
    r = _bw("AND", "-1", "5", 10, 8, True)
    assert r["values"]["DEC"] == "5"
    r = _bw("OR", "-128", "1", 10, 8, True)
    assert r["values"]["DEC"] == "-127"


def test_not_unsigned_and_signed():
    assert _four(_bw("NOT", "12", None, 10, 8)) == (
        "11110011", "363", "243", "F3")
    assert _four(_bw("NOT", "12", None, 10, 8, True)) == (
        "11110011", "363", "-13", "F3")
    assert _bw("NOT", "0", "", 10, 8)["values"]["DEC"] == "255"
    assert _bw("NOT", "-1", None, 10, 8, True)["values"]["DEC"] == "0"


def test_shifts():
    assert _bw("SHL", "1", "4", 10, 8)["values"]["DEC"] == "16"
    assert _bw("SHL", "129", "1", 10, 8)["values"]["DEC"] == "2"   # 遮罩
    assert _bw("SHR", "256", "4", 10, 16)["values"]["DEC"] == "16"
    assert _bw("SHR", "-16", "2", 10, 8, True)["values"]["DEC"] == "60"
    assert _bw("SHL", "5", "0", 10, 8)["values"]["DEC"] == "5"
    assert _bw("SHL", "5", "8", 10, 8)["values"]["DEC"] == "0"
    assert _bw("SHR", "200", "8", 10, 8)["values"]["DEC"] == "0"


def test_sar():
    assert _bw("SAR", "-16", "2", 10, 8, True)["values"]["DEC"] == "-4"
    assert _bw("SAR", "-1", "7", 10, 8, True)["values"]["DEC"] == "-1"
    assert _bw("SAR", "-128", "8", 10, 8, True)["values"]["DEC"] == "-1"
    assert _bw("SAR", "100", "2", 10, 8, True)["values"]["DEC"] == "25"
    assert _bw("SAR", "100", "8", 10, 8, True)["values"]["DEC"] == "0"
    r = _bw("SAR", "F0", "4", 16, 8, True)
    assert r["values"]["HEX"] == "FF"


def test_sar_requires_signed():
    r = _bw("SAR", "240", "2", 10, 8, False)
    assert not r["ok"] and "有號" in r["error"]


@pytest.mark.parametrize("op", ["SHL", "SHR", "SAR"])
def test_shift_amount_out_of_range(op):
    r = _bw(op, "1", "9", 10, 8, True)
    assert not r["ok"] and r["field"] == "B"
    r = _bw(op, "1", "-1", 10, 8, True)
    assert not r["ok"] and r["field"] == "B"


def test_bitwise_input_errors():
    assert _bw("AND", "256", "1", 10, 8)["field"] == "A"
    assert _bw("AND", "1", "256", 10, 8)["field"] == "B"
    assert _bw("AND", "1", None, 10, 8)["field"] == "B"
    assert _bw("AND", "1", "", 10, 8)["field"] == "B"
    assert not _bw("NAND", "1", "1", 10, 8)["ok"]
    assert _bw("AND", "1.5", "1", 10, 8)["field"] == "A"
    assert not _bw(None, "1", "1", 10, 8)["ok"]


def test_bitwise_64_bit():
    r = _bw("AND", "FFFFFFFFFFFFFFFF", "0F0F0F0F0F0F0F0F", 16, 64)
    assert r["values"]["HEX"] == "0F0F0F0F0F0F0F0F"
    r = _bw("SHL", "1", "63", 10, 64)
    assert r["values"]["DEC"] == "9223372036854775808"
    r = _bw("NOT", "0", None, 10, 64, True)
    assert r["values"]["DEC"] == "-1"


def test_engine_functions_direct():
    r = base.convert_base("255", 10, 16, False)
    assert r["ok"] and r["values"]["HEX"] == "00FF"
    r = base.bitwise("XOR", 5, 3, 8, False)
    assert r["ok"] and r["values"]["DEC"] == "6"
    assert not base.bitwise("AND", 256, 1, 8, False)["ok"]
    assert not base.bitwise("AND", True, 1, 8, False)["ok"]
    assert not base.bitwise("AND", 1.0, 1, 8, False)["ok"]
