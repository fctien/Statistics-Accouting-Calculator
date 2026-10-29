"""教學單一來源 teaching/prompts.py 的自測（self-test）。

檢查：11 個步驟順序、必要欄位非空、四段式 Prompt 標籤、驗收指令引用的檔案在對應 git tag 上存在、
EMBA 起點 tag 存在、所有字串沒有全形句點「。」（簡報規則）、兩層 CLAUDE.md 範本結構、
BA II Plus 按鍵標示「未實機驗證」

限制：驗收指令只檢查引用的 repo 路徑與 npm script 是否存在，不檢查旗標（flag，例如 --quick、
--allow-dirty）是否被該 tag 的工具支援，也不實際執行指令
"""
import fnmatch
import json
import os
import subprocess

import pytest

from teaching import prompts

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STEP_IDS = ["step%d" % i for i in range(11)]
FOUR_LABELS = ["【任務】", "【介面】", "【限制】", "【驗收】"]
# 驗收指令中被視為「repo 內路徑」的前綴與根目錄檔案
PATH_PREFIXES = ("tools/", "tests/", "engine/", "web/", "e2e/", "docs/",
                 "golden/", "teaching/", ".claude/", ".github/")
ROOT_FILES = {"package.json", "package-lock.json", "CLAUDE.md", "DEVLOG.md",
              "README.md", "pytest.ini"}
# 尚未有 tag 的步驟：step7 使用者決定不打（Drive 未實測）、step9 部署實測後才打
NO_TAG_YET = {"step7", "step9"}


def _git(*args):
    """在 repo 根目錄執行 git，回傳 (returncode, stdout)。"""
    p = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                       text=True, encoding="utf-8")
    return p.returncode, p.stdout


def _tags(pattern="step*"):
    code, out = _git("tag", "-l", pattern)
    return set(out.split()) if code == 0 else set()


def _need_tags():
    tags = _tags()
    if "step0" not in tags:
        # CI 的淺層 clone（shallow clone）不含 tag，只能在本機檢查
        pytest.skip("此 clone 沒有 step* tag（CI 淺層 clone），tag 相關檢查只在本機執行")
    return tags


def _files_at(tag):
    code, out = _git("ls-tree", "-r", "--name-only", tag)
    assert code == 0, tag
    return set(out.splitlines())


def _paths_in(command):
    """從一行驗收指令取出 repo 內路徑（略過網址）。"""
    out = []
    if command.startswith("claude "):
        # claude -p "…" 引號內是給 AI 的問題，不是路徑
        command = command.split('"')[0]
    for tok in command.split():
        tok = tok.strip("\"'`(),")
        if "://" in tok or not tok:
            continue
        if tok.startswith(PATH_PREFIXES) or tok in ROOT_FILES:
            out.append(tok.rstrip("/"))
    return out


def _npm_scripts_in(command):
    toks = command.split()
    return [toks[i + 2] for i in range(len(toks) - 2)
            if toks[i] == "npm" and toks[i + 1] == "run"]


def _exists(path, files):
    """path 可為檔案、目錄或含 * 的 glob。"""
    if "*" in path:
        return any(fnmatch.fnmatch(f, path) for f in files)
    return path in files or any(f.startswith(path + "/") for f in files)


def _all_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _all_strings(k)
            yield from _all_strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _all_strings(v)


def _nonempty(v):
    if isinstance(v, str):
        return bool(v.strip())
    if isinstance(v, list):
        return bool(v) and all(_nonempty(x) for x in v)
    return v is not None


# ---------- 結構 ----------

def test_eleven_steps_in_order():
    assert [s["id"] for s in prompts.STEPS] == STEP_IDS


def test_required_fields_nonempty():
    for s in prompts.STEPS:
        for k in ("id", "title", "goal"):
            assert _nonempty(s.get(k)), (s["id"], k)
        for k in ("prompt", "bad_prompt", "bad_result", "bad_evidence",
                  "expected", "verify", "pitfalls"):
            assert _nonempty(s["ai"].get(k)), (s["id"], "ai", k)
        for k in ("prompt", "expected", "verify", "pitfalls"):
            assert _nonempty(s["emba"].get(k)), (s["id"], "emba", k)
        assert isinstance(s["ai"]["verify"], list), s["id"]
        assert isinstance(s["emba"]["verify"], list), s["id"]
        assert "start_tag" in s["emba"], s["id"]


def test_ai_and_emba_prompts_have_four_labels_in_order():
    for s in prompts.STEPS:
        for ver in ("ai", "emba"):
            text = s[ver]["prompt"]
            pos = [text.find(lab) for lab in FOUR_LABELS]
            assert all(p >= 0 for p in pos), (s["id"], ver, pos)
            assert pos == sorted(pos), (s["id"], ver, "標籤順序")


MEASURED_STEPS = ("step0", "step1", "step2")  # 2026-10-21 演練過的步驟


def test_measured_pitfalls_recorded():
    # 演練踩到的新坑要寫進 pitfalls，並標出處「演練 2026-10-21」
    for s in prompts.STEPS:
        if s["id"] in MEASURED_STEPS:
            assert any("演練 2026-10-21" in x for x in s["ai"]["pitfalls"]), s["id"]


def test_bad_prompt_is_one_line_and_labels_evidence():
    for s in prompts.STEPS:
        ai = s["ai"]
        assert "\n" not in ai["bad_prompt"].strip(), s["id"]
        for lab in FOUR_LABELS:
            assert lab not in ai["bad_prompt"], s["id"]
        # step0～step2 已演練（teaching/rehearse.md）：結果標「實測：」；其餘尚未實測，必須標「推測：」
        # 佐證必須是本專案實際發生過的事
        prefix = "實測：" if s["id"] in MEASURED_STEPS else "推測："
        assert ai["bad_result"].startswith(prefix), s["id"]
        if prefix == "實測：":
            assert "演練" in ai["bad_result"], s["id"]
        assert ai["bad_evidence"].startswith("實際踩過："), s["id"]


def test_step7_optional_and_tags():
    by_id = {s["id"]: s for s in prompts.STEPS}
    assert by_id["step7"]["optional"] is True
    assert "未實測" in by_id["step7"]["title"] + by_id["step7"]["goal"]
    for sid, s in by_id.items():
        if sid != "step7":
            assert not s.get("optional", False), sid
        expect = None if sid == "step7" else sid
        assert s["tag"] == expect, sid


def test_no_fullwidth_period_anywhere():
    texts = list(_all_strings(prompts.STEPS))
    texts += [prompts.USER_CLAUDE_MD, prompts.PROJECT_CLAUDE_MD]
    bad = [t[:40] for t in texts if "。" in t]
    assert not bad, bad


def test_ba_keystrokes_marked_unverified():
    """BA II Plus 按鍵依記憶撰寫，未在實機核對，必須標示"""
    keys = ("[2ND]", "[CPT]", "[CF]", "[ENTER]")
    found = 0
    for t in _all_strings(prompts.STEPS):
        if "BA II Plus" in t and any(k in t for k in keys):
            found += 1
            assert "未實機驗證" in t, t[:60]
    assert found >= 5, found


def test_user_claude_md_five_principles():
    lines = [ln for ln in prompts.USER_CLAUDE_MD.splitlines()
             if ln.startswith("- ")]
    assert len(lines) == 5, lines
    for word in ("繁體中文", "不確定", "連結", "測", "計畫", "安裝"):
        assert word in prompts.USER_CLAUDE_MD, word


def test_project_claude_md_five_sections():
    heads = [ln[3:].strip() for ln in prompts.PROJECT_CLAUDE_MD.splitlines()
             if ln.startswith("## ")]
    assert heads == ["常用指令", "專案結構", "程式風格", "工作方式", "重要規則"]
    for word in ("python -m pytest -q", "MVC", "eval", "MicroPython"):
        assert word in prompts.PROJECT_CLAUDE_MD, word


def test_import_has_no_side_effects():
    import importlib
    before = set(os.listdir(ROOT))
    importlib.reload(prompts)
    assert set(os.listdir(ROOT)) == before


# ---------- 與 git tag 對照 ----------

def test_ai_verify_paths_exist_at_tag():
    tags = _need_tags()
    checked = 0
    for s in prompts.STEPS:
        tag = s["tag"]
        if s["id"] in NO_TAG_YET and tag not in tags:
            continue  # 改由 test_untagged_steps_paths_exist_in_worktree 檢查
        assert tag in tags, tag
        files = _files_at(tag)
        pkg = None
        for cmd in s["ai"]["verify"]:
            for p in _paths_in(cmd):
                assert _exists(p, files), (tag, cmd, p)
                checked += 1
            for name in _npm_scripts_in(cmd):
                if pkg is None:
                    code, out = _git("show", "%s:package.json" % tag)
                    assert code == 0, (tag, "package.json")
                    pkg = json.loads(out)
                assert name in pkg.get("scripts", {}), (tag, cmd, name)
                checked += 1
    assert checked >= 15, checked


@pytest.mark.parametrize("sid", sorted(NO_TAG_YET))
def test_untagged_steps_paths_exist_in_worktree(sid):
    """step7／step9 尚無 tag（step7 使用者決定不打、step9 部署實測後才打），改查目前工作樹"""
    s = next(x for x in prompts.STEPS if x["id"] == sid)
    if sid in _tags():
        pytest.skip("%s 已打 tag，由 test_ai_verify_paths_exist_at_tag 檢查" % sid)
    for cmd in s["ai"]["verify"]:
        for p in _paths_in(cmd):
            assert os.path.exists(os.path.join(ROOT, p.split("*")[0])), (sid, p)


def test_emba_start_tag_exists():
    _need_tags()
    tags = _tags("*")  # step10 以版本 tag v0.1.0 為起點
    for s in prompts.STEPS:
        st = s["emba"]["start_tag"]
        if st is None:
            assert s["id"] in NO_TAG_YET, s["id"]
        else:
            assert st in tags, (s["id"], st)
