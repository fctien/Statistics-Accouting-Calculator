"""共用求根器測試。"""
from engine.solver import find_root


def test_sqrt2():
    assert abs(find_root(lambda x: x * x - 2, 0, 2, 1) - 2 ** 0.5) < 1e-10


def test_newton_fails_bisection_rescues():
    x = find_root(lambda x: x ** (1 / 3) if x >= 0 else -(-x) ** (1 / 3), -1, 2, 1)
    assert abs(x) < 1e-9


def test_no_root_returns_none():
    assert find_root(lambda x: x * x + 1, -5, 5, 0) is None


def test_max_iter_respected():
    f = lambda x: x ** (1 / 3) if x >= 0 else -(-x) ** (1 / 3)
    assert find_root(f, -1, 2.1, 1, max_iter=3) is None
    assert abs(find_root(f, -1, 2.1, 1)) < 1e-9


def test_snap_zero_pct():
    # 疊代求解的殘差雜訊（百分數 |x| < 1e-9）收成 0，其餘原樣
    from engine.solver import snap_zero_pct
    assert snap_zero_pct(-1.2660856707075806e-15) == 0.0
    assert snap_zero_pct(7.455e-10) == 0.0
    assert snap_zero_pct(2e-9) == 2e-9
    assert snap_zero_pct(-5.25) == -5.25
    r = snap_zero_pct(-1e-12)
    assert r == 0.0 and str(r) == "0.0"  # 不可是 -0.0
