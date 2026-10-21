"""teaching/export_pdf.py 的決策邏輯測試（不會真的啟動 PowerPoint）

- PowerPoint 正在執行：不匯出、不呼叫 COM，印出說明並回 2
- 沒有執行：開新 instance，每份簡報 ReadOnly＋WithWindow=False 開啟、SaveAs PDF（32）、Close，最後只 Quit 一次
- 匯出途中出錯也要 Quit 自己開的 instance
- tasklist 輸出判斷大小寫不敏感
"""
import pytest

from teaching import export_pdf


class FakePres:
    def __init__(self, log, path):
        self.log, self.path = log, path

    def SaveAs(self, out, fmt):  # noqa: N802（COM 方法名稱）
        self.log.append(("SaveAs", out, fmt))

    def Close(self):  # noqa: N802
        self.log.append(("Close", self.path))


class FakePresentations:
    def __init__(self, log, fail_on=None):
        self.log, self.fail_on = log, fail_on

    def Open(self, path, ReadOnly, Untitled, WithWindow):  # noqa: N802,N803
        self.log.append(("Open", path, ReadOnly, Untitled, WithWindow))
        if self.fail_on and self.fail_on in path:
            raise RuntimeError("模擬開檔失敗")
        return FakePres(self.log, path)


class FakeApp:
    def __init__(self, log, fail_on=None):
        self.log = log
        self.Presentations = FakePresentations(log, fail_on)

    def Quit(self):  # noqa: N802
        self.log.append(("Quit",))


TASKLIST_RUNNING = "POWERPNT.EXE                 25644 Console                   15    461,344 K\n"
TASKLIST_NONE = "資訊: 沒有執行中的工作符合指定的準則。\n"


def test_is_running_detects_powerpoint_case_insensitive():
    assert export_pdf.is_powerpoint_running(TASKLIST_RUNNING)
    assert export_pdf.is_powerpoint_running("powerpnt.exe 1 Console 1 10 K")
    assert not export_pdf.is_powerpoint_running(TASKLIST_NONE)
    assert not export_pdf.is_powerpoint_running("")


def test_running_powerpoint_blocks_export(tmp_path, capsys):
    called = []
    code = export_pdf.main(out_dir=str(tmp_path), tasklist=lambda: TASKLIST_RUNNING,
                           dispatch=lambda: called.append("dispatch"))
    assert code == 2
    assert called == []  # 絕不連上使用者開著的 PowerPoint
    assert export_pdf.RUNNING_MESSAGE in capsys.readouterr().out


def test_not_running_exports_each_deck_readonly(tmp_path):
    for name in export_pdf.DECKS:
        (tmp_path / name).write_bytes(b"pptx")
    log = []
    code = export_pdf.main(out_dir=str(tmp_path), tasklist=lambda: TASKLIST_NONE,
                           dispatch=lambda: FakeApp(log))
    assert code == 0
    opens = [x for x in log if x[0] == "Open"]
    assert len(opens) == len(export_pdf.DECKS)
    for _, path, ro, untitled, win in opens:
        assert ro is True and win is False and untitled is False
        assert "講稿" not in path
    saves = [x for x in log if x[0] == "SaveAs"]
    assert all(fmt == 32 for _, _, fmt in saves)
    assert [s[1].endswith(".pdf") for s in saves] == [True] * len(export_pdf.DECKS)
    assert log.count(("Quit",)) == 1 and log[-1] == ("Quit",)
    assert len([x for x in log if x[0] == "Close"]) == len(export_pdf.DECKS)


def test_error_still_quits_own_instance(tmp_path):
    for name in export_pdf.DECKS:
        (tmp_path / name).write_bytes(b"pptx")
    log = []
    code = export_pdf.main(out_dir=str(tmp_path), tasklist=lambda: TASKLIST_NONE,
                           dispatch=lambda: FakeApp(log, fail_on="EMBA"))
    assert code == 1
    assert log[-1] == ("Quit",)


def test_missing_deck_fails_before_dispatch(tmp_path, capsys):
    called = []
    code = export_pdf.main(out_dir=str(tmp_path), tasklist=lambda: TASKLIST_NONE,
                           dispatch=lambda: called.append("dispatch"))
    assert code == 1
    assert called == []
    assert "找不到簡報" in capsys.readouterr().out


def test_tasklist_failure_does_not_export(tmp_path, capsys):
    def boom():
        raise OSError("沒有 tasklist")
    called = []
    code = export_pdf.main(out_dir=str(tmp_path), tasklist=boom,
                           dispatch=lambda: called.append("dispatch"))
    assert code == 1 and called == []


@pytest.mark.parametrize("name", ["BACalc_AI.pptx", "BACalc_EMBA.pptx"])
def test_pdf_name(name):
    assert export_pdf.pdf_name(name) == name[:-5] + ".pdf"
