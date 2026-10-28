"""run_all.py：步驟順序、export_pdf 回 2 時停下、log 內容（不真的執行子程式）"""
import os

import pytest

import run_all

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _runner(codes):
    calls = []

    def run(cmd):
        name = os.path.basename(cmd[1])
        calls.append(name)
        return codes.get(name, 0), "輸出 %s" % name
    return run, calls


def test_order_and_all_pass(tmp_path):
    run, calls = _runner({})
    assert run_all.main(log_dir=str(tmp_path), runner=run, out_dir=str(tmp_path)) == 0
    assert calls == ["verify_all.py", "build_cards.py", "build_deck.py", "export_pdf.py", "make_package.py"]
    logs = list(tmp_path.glob("run_all-*.html"))
    text = logs[0].read_text(encoding="utf-8")
    assert "commit" in text and "總結：PASS" in text
    assert "人工目視檢查清單" in text and "未完成" in text  # 只列清單，不宣稱已完成


def test_stops_when_powerpoint_running(tmp_path):
    run, calls = _runner({"export_pdf.py": 2})
    assert run_all.main(log_dir=str(tmp_path), runner=run, out_dir=str(tmp_path)) == 2
    assert "make_package.py" not in calls
    text = next(tmp_path.glob("run_all-*.html")).read_text(encoding="utf-8")
    assert "停在 export_pdf" in text and "未執行" in text
    assert "git add logs/" in text  # log 也寫出復原方式


def test_stop_prints_recovery_hint(tmp_path, capsys):
    run, _ = _runner({"export_pdf.py": 2})
    run_all.main(log_dir=str(tmp_path), runner=run, out_dir=str(tmp_path))
    out = capsys.readouterr().out
    assert run_all.RECOVERY_HINT in out and "git add logs/" in out


def test_pass_has_no_recovery_hint(tmp_path, capsys):
    run, _ = _runner({})
    run_all.main(log_dir=str(tmp_path), runner=run, out_dir=str(tmp_path))
    assert "重跑前" not in capsys.readouterr().out


def test_failure_exit_1(tmp_path):
    run, calls = _runner({"verify_all.py": 1})
    assert run_all.main(log_dir=str(tmp_path), runner=run, out_dir=str(tmp_path)) == 1
    assert calls == ["verify_all.py"]


def test_visual_pages_found_in_real_deck():
    # CI（Linux）只裝 pytest：沒有 python-pptx 就無法讀簡報，跳過而非失敗
    pytest.importorskip("pptx", reason="需要 python-pptx 才能讀簡報（CI 未安裝）")
    out = os.path.join(ROOT, "teaching", "out")
    if not os.path.exists(os.path.join(out, "BACalc_AI.pptx")):
        pytest.skip("teaching/out 沒有簡報（請先跑 build_deck.py）")
    rows = run_all.find_visual_pages(out)
    missing = [r for r in rows if r[1] == "找不到"]
    assert not missing, missing
