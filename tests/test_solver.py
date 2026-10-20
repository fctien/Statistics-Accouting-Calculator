"""共用求根器測試。"""
from engine.solver import find_root


def test_sqrt2():
    assert abs(find_root(lambda x: x * x - 2, 0, 2, 1) - 2 ** 0.5) < 1e-10


def test_newton_fails_bisection_rescues():
    x = find_root(lambda x: x ** (1 / 3) if x >= 0 else -(-x) ** (1 / 3), -1, 2, 1)
    assert abs(x) < 1e-9


def test_no_root_returns_none():
    assert find_root(lambda x: x * x + 1, -5, 5, 0) is None
