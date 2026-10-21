"""teaching/make_package.py：學生版 zip 的內容規則

- 每版 zip 含：對應 Prompt 卡 HTML、簡報 PDF、docs/google-oauth-setup.html、學生說明.txt
- 絕不含 pptx、絕不含講稿版
- 缺 PDF 或 PDF 比 pptx 舊時不產生 zip，回傳錯誤並說明
"""
import os
import zipfile

import pytest

from teaching import make_package


def _setup(tmp_path, with_pdf=True):
    out = tmp_path / "out"
    out.mkdir()
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "google-oauth-setup.html").write_text("<html>oauth</html>", encoding="utf-8")
    for v in ("AI", "EMBA"):
        (out / ("Prompt卡_%s.html" % v)).write_text("card", encoding="utf-8")
        (out / ("BACalc_%s.pptx" % v)).write_bytes(b"pptx")
        (out / ("BACalc_%s_講稿.pptx" % v)).write_bytes(b"pptx")
        if with_pdf:
            (out / ("BACalc_%s.pdf" % v)).write_bytes(b"%PDF-1.7")
            (out / ("BACalc_%s_講稿.pdf" % v)).write_bytes(b"%PDF-1.7")  # 不該被打包
    return out, docs


def test_zip_contents(tmp_path):
    out, docs = _setup(tmp_path)
    paths = make_package.build_all(out_dir=str(out), docs_dir=str(docs))
    assert [p.split("\\")[-1].split("/")[-1] for p in paths] == [
        "BACalc_AI_student.zip", "BACalc_EMBA_student.zip"]
    for p, v in zip(paths, ("AI", "EMBA")):
        names = zipfile.ZipFile(p).namelist()
        assert sorted(names) == sorted([
            "Prompt卡_%s.html" % v, "BACalc_%s.pdf" % v,
            "google-oauth-setup.html", "學生說明.txt"])
        assert not any(n.endswith(".pptx") or "講稿" in n for n in names)


def test_readme_text_mentions_clone_tags_cards(tmp_path):
    out, docs = _setup(tmp_path)
    paths = make_package.build_all(out_dir=str(out), docs_dir=str(docs))
    for p, v in zip(paths, ("ai", "emba")):
        text = zipfile.ZipFile(p).read("學生說明.txt").decode("utf-8")
        assert "git clone" in text and "git checkout" in text
        assert "Prompt卡_%s.html" % v.upper() in text
        assert "step0" in text
        assert "。" not in text
    emba = zipfile.ZipFile(paths[1]).read("學生說明.txt").decode("utf-8")
    assert "step6" in emba  # step8 由 step6 接手（step7 沒有 tag）


def test_missing_pdf_no_zip(tmp_path):
    out, docs = _setup(tmp_path, with_pdf=False)
    with pytest.raises(make_package.PackageError) as e:
        make_package.build_all(out_dir=str(out), docs_dir=str(docs))
    assert "PDF" in str(e.value)
    assert not list(out.glob("*.zip"))


def test_main_returns_1_without_pdf(tmp_path, capsys):
    out, docs = _setup(tmp_path, with_pdf=False)
    code = make_package.main(["--zip"], out_dir=str(out), docs_dir=str(docs))
    assert code == 1
    assert "PDF" in capsys.readouterr().out


def test_main_without_zip_flag_only_checks(tmp_path, capsys):
    out, docs = _setup(tmp_path)
    code = make_package.main([], out_dir=str(out), docs_dir=str(docs))
    assert code == 0
    assert not list(out.glob("*.zip"))


def test_stale_pdf_no_zip(tmp_path):
    out, docs = _setup(tmp_path)
    pptx = out / "BACalc_EMBA.pptx"
    pdf = out / "BACalc_EMBA.pdf"
    os.utime(pdf, (1_000_000, 1_000_000))
    os.utime(pptx, (2_000_000, 2_000_000))  # pptx 在 PDF 之後才重建
    with pytest.raises(make_package.PackageError) as e:
        make_package.build_all(out_dir=str(out), docs_dir=str(docs))
    assert "比對應的 pptx 舊" in str(e.value)
    assert not list(out.glob("*.zip"))
