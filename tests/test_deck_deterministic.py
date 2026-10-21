"""build_deck 可重現：內容不變時連續建置兩次，pptx 逐位元組相同（否則 run_all 重跑會被 git 乾淨檢查擋下）"""
import time
import zipfile

import pytest


def _deck():
    try:
        from teaching.deck import build_deck
    except Exception as e:  # deck_kit 或 python-pptx 不在（例如 CI）
        pytest.skip("無法載入 build_deck（%s）" % e)
    return build_deck


def test_build_twice_identical_bytes(tmp_path):
    bd = _deck()
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    p1 = bd.build("emba", False, out_dir=str(a))[0]
    time.sleep(2.1)  # zip 時間解析度 2 秒，確保第二次的「現在時間」不同
    p2 = bd.build("emba", False, out_dir=str(b))[0]
    assert open(p1, "rb").read() == open(p2, "rb").read()


def test_normalized_zip_fixed_dates_and_order(tmp_path):
    bd = _deck()
    p = bd.build("emba", False, out_dir=str(tmp_path))[0]
    infos = zipfile.ZipFile(p).infolist()
    assert infos[0].filename == "[Content_Types].xml"
    assert {i.date_time for i in infos} == {bd.ZIP_DATE}
    assert zipfile.ZipFile(p).testzip() is None
