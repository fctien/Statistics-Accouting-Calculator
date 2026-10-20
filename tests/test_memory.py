"""memory.py 記憶與累加器測試。"""
import pytest

from engine.memory import Memory


def test_store_recall_default():
    m = Memory()
    assert m.recall(3)["values"]["value"] == 0.0
    m.store(3, 2.5)
    assert m.recall(3)["values"]["value"] == 2.5


def test_arithmetic():
    m = Memory()
    m.store(1, 10)
    assert m.add(1, 5)["values"]["value"] == 15
    assert m.sub(1, 3)["values"]["value"] == 12
    assert m.mul(1, 2)["values"]["value"] == 24
    assert m.div(1, 8)["values"]["value"] == 3
    assert m.recall(1)["values"]["value"] == 3


def test_div_zero_keeps_value():
    m = Memory()
    m.store(2, 7)
    r = m.div(2, 0)
    assert r["ok"] is False
    assert m.recall(2)["values"]["value"] == 7


@pytest.mark.parametrize("i", [-1, 10, 1.0, "1", None, True])
def test_bad_index(i):
    assert Memory().recall(i)["ok"] is False
    assert Memory().store(i, 1)["ok"] is False


def test_bad_value_and_overflow():
    m = Memory()
    assert m.store(0, float("nan"))["ok"] is False
    assert m.store(0, "x")["ok"] is False
    m.store(0, 1e308)
    assert m.mul(0, 10)["ok"] is False
    assert m.recall(0)["values"]["value"] == 1e308


def test_accumulate():
    m = Memory()
    m.accumulate(3)
    r = m.accumulate(4.5)
    assert r["values"] == {"sum": 7.5, "count": 2}
    assert m.accumulate(float("inf"))["ok"] is False
    assert m.accumulate(0)["values"]["count"] == 3


def test_round_trip_and_validation():
    m = Memory()
    m.store(4, 1.25)
    m.accumulate(2)
    m2 = Memory.from_dict(m.to_dict())
    assert m2.recall(4)["values"]["value"] == 1.25
    assert m2.accumulate(1)["values"] == {"sum": 3.0, "count": 2}
    m3 = Memory.from_dict({"M1": 5, "M2": "bad", "M99": 1, "zzz": 3,
                           "M3": float("nan"), "M4": True})
    assert m3.recall(1)["values"]["value"] == 5
    for i in (2, 3, 4):
        assert m3.recall(i)["values"]["value"] == 0.0
    assert Memory.from_dict(None).recall(0)["values"]["value"] == 0.0
    assert Memory.from_dict("x").recall(0)["ok"] is True
