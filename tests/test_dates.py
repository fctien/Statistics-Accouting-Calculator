"""日期（序數日）測試。"""
from engine.dates import (to_ordinal, from_ordinal, weekday, days_act,
                          days_360, is_valid_date, days_in_month,
                          date_sheet)


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


def test_days_in_month():
    assert days_in_month(2028, 2) == 29 and days_in_month(2026, 2) == 28


def test_date_sheet_golden(golden_cases):
    cases = golden_cases("date")
    for c in cases:
        i = c["call"]["inputs"]
        r = date_sheet(i["DT1"], i["DT2"], None, i["basis"], "DBD")
        assert r["ok"], c["id"]
        assert abs(r["values"]["DBD"] - c["expected"]) <= c["tol"], c["id"]


def test_solve_dt2_act():
    r = date_sheet([2026, 1, 1], None, 59, "ACT", "DT2")
    assert r["ok"] and r["values"]["DT2"] == [2026, 3, 1]
    r = date_sheet(None, [2026, 3, 1], 59, "ACT", "DT1")
    assert r["values"]["DT1"] == [2026, 1, 1]


def test_weekday_label():
    r = date_sheet([2026, 10, 19], [2026, 10, 25], None, "ACT", "DBD")
    assert r["values"]["weekday1"] == "星期一"
    assert r["values"]["weekday2"] == "星期日"
    assert r["values"]["DBD"] == 6


def test_solve_360_roundtrip_and_warning():
    # 1/1 起算 89 天（360）只有 3/30 一解，無警告
    r = date_sheet([2026, 1, 1], None, 89, "360", "DT2")
    assert r["values"]["DT2"] == [2026, 3, 30] and r["warnings"] == []
    # 90 天：3/31 與 4/1 皆為 90 → 取最早並警告
    r = date_sheet([2026, 1, 1], None, 90, "360", "DT2")
    assert r["values"]["DT2"] == [2026, 3, 31]
    assert r["warnings"] == ["30/360 有多個日期符合，取最早者"]
    # 起日 1/30：3/30 與 3/31 同為 60
    r = date_sheet([2026, 1, 30], None, 60, "360", "DT2")
    assert r["values"]["DT2"] == [2026, 3, 30] and r["warnings"]
    r = date_sheet(None, [2026, 3, 30], 89, "360", "DT1")
    assert r["values"]["DT1"] == [2026, 1, 1]


def test_solve_360_brute_force():
    base = to_ordinal(2027, 12, 20)
    for off in range(0, 800, 7):
        d2 = from_ordinal(base + off)
        dbd = days_360((2027, 12, 20), d2)
        r = date_sheet([2027, 12, 20], None, dbd, "360", "DT2")
        assert r["ok"]
        got = tuple(r["values"]["DT2"])
        assert days_360((2027, 12, 20), got) == dbd
        assert to_ordinal(*got) <= base + off


def test_date_sheet_errors():
    assert not date_sheet([2026, 2, 29], [2026, 3, 1], None, "ACT", "DBD")["ok"]
    assert not date_sheet([2026, 1, 1], None, 1.5, "ACT", "DT2")["ok"]
    assert not date_sheet([2026, 1, 1], None, 10, "XX", "DT2")["ok"]
    assert not date_sheet([2026, 1, 1], None, 10, "ACT", "ZZ")["ok"]
    assert not date_sheet([2026, 1, 1], None, 10 ** 8, "ACT", "DT2")["ok"]
    assert not date_sheet([2026, 1, 1], None, 10 ** 8, "360", "DT2")["ok"]
    assert not date_sheet([True, 1, 1], [2026, 1, 2], None, "ACT", "DBD")["ok"]
    assert not date_sheet([2026, 1], [2026, 1, 2], None, "ACT", "DBD")["ok"]
