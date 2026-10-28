"""使用說明影片腳本（teaching/video/script.py）：欄位齊全、動作合法、expect 數值由引擎實算核對、長度 8–12 分鐘。"""
import json

import pytest

from engine.bridge import call
from teaching.video import script
from teaching.video.build_video import split_cues, srt_time

ACTION_KEYS = {"goto", "click", "fill", "select", "press", "wait", "highlight", "card", "uncard", "check"}


def test_segments_fields_complete():
    ids = [s["id"] for s in script.SEGMENTS]
    assert len(ids) == len(set(ids)) and len(ids) >= 10
    for s in script.SEGMENTS:
        for key in ("id", "title", "narration", "start", "actions", "expect"):
            assert key in s, (s.get("id"), key)
        assert s["narration"].strip() and s["title"].strip()
        assert s["actions"], s["id"]
        assert s["expect"], s["id"]  # 每段至少一項可在畫面上核對


def test_actions_use_known_verbs():
    for s in script.SEGMENTS:
        for a in s["actions"]:
            verbs = ACTION_KEYS & set(a)
            assert len(verbs) == 1, (s["id"], a)
            if "fill" in a or "select" in a:
                assert isinstance(a.get("value"), str), (s["id"], a)


def test_required_topics_in_order():
    order = [s["id"] for s in script.SEGMENTS]
    must = ["intro", "install", "nav", "eng-calc", "eng-units-base", "stat-desc", "stat-reg",
            "stat-dist", "stat-infer", "acct-tvm", "acct-cf", "acct-tax", "scenario", "settings", "outro"]
    assert [x for x in order if x in must] == must


def _engine(req):
    res = json.loads(call(json.dumps({"sheet": req["sheet"], "action": req["action"],
                                      "inputs": req["inputs"], "settings": req.get("settings", {})})))
    assert res["ok"] is True, res
    return res["display"][req["key"]]


def test_expect_values_match_engine():
    n_engine = 0
    for s in script.SEGMENTS:
        for e in s["expect"]:
            assert e.get("selector") and e.get("text"), (s["id"], e)
            if e.get("screen"):  # 畫面文字（標題、網址、結論字樣），不是數值
                continue
            assert "engine" in e, (s["id"], e)
            disp = _engine(e["engine"])
            assert e["text"] in disp or e["text"] == disp.replace(" ", ""), (s["id"], e["text"], disp)
            n_engine += 1
    assert n_engine >= 12


def test_narration_length_8_to_12_minutes():
    chars = sum(script.speech_chars(s["narration"]) for s in script.SEGMENTS)
    minutes = chars / 220
    assert 8 <= minutes <= 12, (chars, minutes)


def test_narration_has_no_raw_ascii_abbrev():
    # 旁白給語音念，英文縮寫要寫成中文讀法（字幕另由 subtitle 欄位提供）
    for s in script.SEGMENTS:
        letters = [w for w in s["narration"].replace("\n", " ").split() if w.isascii() and w.isalpha() and len(w) >= 2]
        assert not letters, (s["id"], letters)


def test_split_cues_proportional():
    cues = split_cues("第一句很短。第二句比較長一點，還有逗號。", 10.0)
    assert cues[0][0] == 0 and abs(cues[-1][1] - 10.0) < 1e-9
    assert all(a < b for a, b, _ in cues)
    assert "".join(t for _, _, t in cues).replace("，", "").replace("。", "") == "第一句很短第二句比較長一點還有逗號"


def test_srt_time_format():
    assert srt_time(3723.456) == "01:02:03,456"
    assert srt_time(0) == "00:00:00,000"


@pytest.mark.parametrize("seg", script.SEGMENTS, ids=lambda s: s["id"])
def test_json_roundtrip(seg):
    assert json.loads(json.dumps(seg, ensure_ascii=False)) == seg
