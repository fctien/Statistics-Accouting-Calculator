"""pytest 共用：尋找並執行 Node.js（找不到時讓測試 skip 並說明原因）。"""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
NODE = shutil.which("node")
SKIP_REASON = "找不到 node（Node.js）：JS 測試需要 Node 18 以上，請安裝後重跑"


def require_node():
    """沒有 node 就 skip 目前測試。"""
    if NODE is None:
        pytest.skip(SKIP_REASON)


def run_node(args, stdin=None, timeout=120):
    """在專案根目錄執行 node，回傳 CompletedProcess（UTF-8 文字）。"""
    require_node()
    return subprocess.run([NODE, *args], cwd=ROOT, input=stdin,
                          capture_output=True, text=True, encoding="utf-8",
                          timeout=timeout)
