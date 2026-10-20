"""DEPR 折舊測試。"""
from engine.depr import schedule, year
from tests.conftest import rel_close


def test_depr_golden(golden_cases):
    cases = golden_cases("depr")
    assert cases
    for c in cases:
        i = c["call"]["inputs"]
        r = year(i["method"], i["CST"], i["SAL"], i["LIF"], i["M01"],
                 i["DB"], i["YR"])
        assert r["ok"] and rel_close(
            r["values"][c["expect_key"]], c["expected"], c["tol"]), c["id"]


def test_sl_partial_first_year():
    r = schedule("SL", 12000, 0, 5, 7)
    rows = r["values"]["rows"]
    assert len(rows) == 6
    assert abs(rows[0][1] - 1200) < 1e-9 and abs(rows[5][1] - 1200) < 1e-9
    assert abs(rows[5][2]) < 1e-9
    assert year("SL", 12000, 0, 5, 7, yr=6)["ok"]
    assert not year("SL", 12000, 0, 5, 7, yr=7)["ok"]
    assert not year("SL", 12000, 0, 5, 1, yr=6)["ok"]


def test_db_never_below_salvage():
    for m in ("DB", "DBX"):
        for pct in (150, 200, 400, 1000):
            rows = schedule(m, 10000, 1000, 5, 1, pct)["values"]["rows"]
            assert all(r[2] >= 1000 and r[1] >= 0 for r in rows)


def test_db_partial_first_year():
    r = schedule("DB", 10000, 1000, 5, 7, 200)["values"]["rows"]
    assert len(r) == 6 and abs(r[0][1] - 4000 * 0.5) < 1e-9


def test_dbx_matches_vdb_values():
    rows = schedule("DBX", 10000, 1000, 5)["values"]["rows"]
    assert [round(x[1], 6) for x in rows] == [4000, 2400, 1440, 864, 296]


def test_syd_partial_year_rejected():
    for m in ("SYD", "DBX"):
        r = schedule(m, 10000, 1000, 5, 7)
        assert not r["ok"] and r["field"] == "M01"
        assert r["error"] == "SYD 部分年度需 TI 手冊範例驗證，目前僅支援 M01=1"


def test_rows_sum_to_depreciable():
    for m, mm in (("SL", 1), ("SL", 4.5), ("SYD", 1), ("DBX", 1)):
        rows = schedule(m, 10000, 1000, 5, mm)["values"]["rows"]
        assert abs(sum(r[1] for r in rows) - 9000) < 1e-9, m
        assert abs(rows[-1][3]) < 1e-9


def test_year_fields():
    v = year("SYD", 10000, 1000, 5, yr=3)["values"]
    assert abs(v["DEP"] - 1800) < 1e-9
    assert abs(v["RDV"] - (v["RBV"] - 1000)) < 1e-9


def test_validation():
    bad = [
        dict(method="XX", cst=1, sal=0, lif=1),
        dict(method="SL", cst=-1, sal=0, lif=1),
        dict(method="SL", cst=100, sal=200, lif=1),
        dict(method="SL", cst=100, sal=-1, lif=1),
        dict(method="SL", cst=100, sal=0, lif=0),
        dict(method="SL", cst=100, sal=0, lif=2.5),
        dict(method="SL", cst=100, sal=0, lif=10001),
        dict(method="SL", cst=100, sal=0, lif=True),
        dict(method="SL", cst=float("nan"), sal=0, lif=3),
        dict(method="SL", cst=float("inf"), sal=0, lif=3),
        dict(method="SL", cst=100, sal=0, lif=3, m01=13),
        dict(method="SL", cst=100, sal=0, lif=3, m01=0.5),
        dict(method="DB", cst=100, sal=0, lif=3, db_pct=0),
    ]
    for kw in bad:
        assert not schedule(**kw)["ok"], kw
    for yr in (0, 6, 1.5, None, True, float("nan")):
        assert not year("SL", 100, 0, 5, yr=yr)["ok"], yr
    assert year("SL", 100, 0, 5, yr=1.5)["field"] == "YR"
    assert schedule("SL", 100, 0, 5.0)["ok"]


def test_huge_rate_stays_finite_and_capped():
    r = schedule("DB", 1e308, 0, 5, 1, 1e308)
    assert r["ok"] and r["values"]["rows"][0][1] == 1e308
