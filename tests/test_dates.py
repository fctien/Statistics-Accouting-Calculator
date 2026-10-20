"""日期（序數日）測試。"""
from engine.dates import (to_ordinal, from_ordinal, weekday, days_act,
                          days_360, is_valid_date)


def test_ordinal_roundtrip_and_leap():
    for d in [(1, 1, 1), (2000, 2, 29), (2028, 2, 29), (2026, 12, 31)]:
        assert from_ordinal(to_ordinal(*d)) == d
    assert not is_valid_date(2026, 2, 29) and not is_valid_date(1900, 2, 29)


def test_weekday_known():
    assert weekday(to_ordinal(2026, 10, 20)) == 1


def test_days360_month_end():
    assert days_360((2026, 1, 31), (2026, 2, 28)) == 28
    assert days_360((2026, 1, 30), (2026, 3, 31)) == 60
    assert days_act((2028, 2, 28), (2028, 3, 1)) == 2


def test_days360_feb_end_matches_excel():
    # 以下數值皆由本機 Excel DAYS360(...,FALSE) 實測
    assert days_360((2026, 2, 28), (2026, 3, 31)) == 30
    assert days_360((2028, 2, 29), (2028, 3, 31)) == 30
    assert days_360((2028, 2, 28), (2028, 3, 31)) == 33
    assert days_360((2026, 2, 28), (2026, 2, 28)) == -2


def test_dates_golden(golden_cases):
    cases = golden_cases("date")
    assert cases
    for c in cases:
        i = c["call"]["inputs"]
        fn = days_act if i["basis"] == "ACT" else days_360
        got = fn(tuple(i["DT1"]), tuple(i["DT2"]))
        assert abs(got - c["expected"]) <= c["tol"], c["id"]
