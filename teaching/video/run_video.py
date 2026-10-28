"""一鍵重建使用說明影片：build_web → script.json → narrate → record → compose → 檢查 → 抽影格。

用法：python teaching/video/run_video.py [--skip-record]
    --skip-record  沿用 build/ 內既有的錄影（只重做旁白與合成）
本機伺服器（python -m http.server，port 8765，根目錄 web/）由本程式啟動，結束時一定關閉。
完成後印出影片長度、解析度、音軌（ffprobe 不在系統上，用 imageio_ffmpeg 的 ffmpeg -i 取得同樣資訊），
並在 5 個時間點抽影格存到 out/frames/。
"""
import os
import re
import socket
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)

from teaching.video import build_video  # noqa: E402

BUILD = os.path.join(HERE, "build")
OUT = os.path.join(HERE, "out")
PORT = 8765
MIN_SEC, MAX_SEC = 8 * 60, 12 * 60


def step(title, cmd):
    """執行一個步驟（子程式），失敗就結束。"""
    print("== %s" % title, flush=True)
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    code = subprocess.call(cmd, cwd=ROOT, env=env)
    if code != 0:
        raise SystemExit("步驟失敗：%s（exit %d）" % (title, code))


def port_free(port):
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def start_server():
    """啟動靜態伺服器並等它回應；回傳 Popen。"""
    if not port_free(PORT):
        raise SystemExit("port %d 已被占用，請先關閉該伺服器" % PORT)
    proc = subprocess.Popen([sys.executable, "-m", "http.server", str(PORT), "-b", "127.0.0.1", "-d", "web"],
                            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        try:
            urllib.request.urlopen("http://127.0.0.1:%d/index.html" % PORT, timeout=1).close()
            return proc
        except OSError:
            time.sleep(0.2)
    proc.terminate()
    raise SystemExit("伺服器沒有回應")


def probe(path):
    """用 ffmpeg -i 取得 Duration／Video／Audio 資訊行與秒數、解析度。"""
    proc = subprocess.run([build_video.ffmpeg_exe(), "-hide_banner", "-i", path],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    lines = [ln.strip() for ln in proc.stderr.splitlines() if re.search(r"Duration:|Stream #", ln)]
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", proc.stderr)
    sec = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0
    res = re.search(r"Video:.*?(\d{3,5})x(\d{3,5})", proc.stderr)
    size = (int(res.group(1)), int(res.group(2))) if res else None
    has_audio = any("Audio:" in ln for ln in lines)
    return lines, sec, size, has_audio


def extract_frames(path, seconds, n=5):
    """在 10%、30%、50%、70%、90% 抽影格 → out/frames/frame-N.jpg；回傳檔案清單。"""
    folder = os.path.join(OUT, "frames")
    os.makedirs(folder, exist_ok=True)
    files = []
    for i in range(n):
        t = seconds * (0.1 + 0.8 * i / (n - 1))
        f = os.path.join(folder, "frame-%d.jpg" % (i + 1))
        build_video.run([build_video.ffmpeg_exe(), "-y", "-hide_banner", "-ss", "%.2f" % t, "-i", path,
                         "-frames:v", "1", "-q:v", "3", f])
        files.append((t, f))
    return files


def main(argv):
    skip_record = "--skip-record" in argv
    os.makedirs(BUILD, exist_ok=True)
    step("建置網頁 build_web", [sys.executable, "tools/build_web.py"])
    step("輸出腳本 script.json", [sys.executable, "teaching/video/script.py", os.path.join(BUILD, "script.json")])
    step("旁白合成 narrate（Yating）", [sys.executable, "teaching/video/narrate.py"])
    if not skip_record:
        server = start_server()
        try:
            step("錄影 record（Playwright）", ["node", "teaching/video/record.mjs", "http://127.0.0.1:%d/" % PORT])
        finally:
            server.terminate()
            server.wait(timeout=10)
    step("合成 compose（ffmpeg）", [sys.executable, "teaching/video/build_video.py"])
    final = os.path.join(OUT, build_video.NAME + ".mp4")
    lines, sec, size, has_audio = probe(final)
    print("== 檢查")
    for ln in lines:
        print("  " + ln)
    print("  長度 %.1f 秒（%.2f 分）、解析度 %s、音軌 %s" % (sec, sec / 60, size, "有" if has_audio else "無"))
    for t, f in extract_frames(final, sec):
        print("  影格 %6.1f 秒 → %s" % (t, f))
    problems = []
    if not MIN_SEC <= sec <= MAX_SEC:
        problems.append("長度 %.1f 秒不在 8–12 分鐘" % sec)
    if size != (1280, 720):
        problems.append("解析度 %s 不是 1280x720" % (size,))
    if not has_audio:
        problems.append("沒有音軌")
    if problems:
        print("失敗：" + "；".join(problems))
        return 1
    print("完成：%s" % final)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
