"""tools.check_portable 可攜性檢查測試。"""
from tools.check_portable import scan


def test_portable_flags_decimal(tmp_path):
    (tmp_path / "bad.py").write_text("import decimal\n", encoding="utf-8")
    assert any("decimal" in m for m in scan(str(tmp_path)))


def test_portable_flags_from_import(tmp_path):
    (tmp_path / "bad.py").write_text(
        "from datetime import date\nimport os.path, typing\n", encoding="utf-8")
    msgs = scan(str(tmp_path))
    assert any("datetime" in m for m in msgs)
    assert any("typing" in m for m in msgs)


def test_portable_flags_eval_exec(tmp_path):
    (tmp_path / "bad.py").write_text(
        "x = eval('1')\nexec('y=1')\n", encoding="utf-8")
    msgs = scan(str(tmp_path))
    assert any("eval" in m for m in msgs) and any("exec" in m for m in msgs)


def test_portable_allows_math_json(tmp_path):
    (tmp_path / "ok.py").write_text(
        "import math\nimport json\nfrom math import sqrt\n", encoding="utf-8")
    assert scan(str(tmp_path)) == []


def test_portable_engine_clean():
    assert scan("engine") == []


def test_portable_flags_builtin_base_init(tmp_path):
    # MicroPython 的內建型別沒有 __init__ 屬性：Exception.__init__(self, ...) 會拋 AttributeError
    (tmp_path / "bad.py").write_text(
        "class E(Exception):\n    def __init__(self, m):\n"
        "        Exception.__init__(self, m)\n"
        "class F(ValueError):\n    def __init__(self, m):\n"
        "        ValueError.__init__(self, m)\n", encoding="utf-8")
    msgs = scan(str(tmp_path))
    assert sum("__init__" in m for m in msgs) == 2


def test_portable_allows_super_init(tmp_path):
    (tmp_path / "ok.py").write_text(
        "class E(Exception):\n    def __init__(self, m):\n"
        "        super().__init__(m)\n        self.m = m\n", encoding="utf-8")
    assert scan(str(tmp_path)) == []
