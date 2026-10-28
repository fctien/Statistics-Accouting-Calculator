"""合成（compose）：每段 webm ＋ 旁白 wav → mp4，串接後燒入字幕；另產外掛字幕 srt。

每段長度 D = max(錄影長度, 旁白長度 + 0.5)；錄影較短時以最後一格靜止延長（tpad clone），
旁白後面補靜音到 D。字幕依標點斷句，時間按字數比例分配在該段旁白長度內。
輸入：build/record.json（record.mjs）、build/durations.json 與 build/seg-XX.wav（narrate.py）
輸出：out/BACalc_使用說明.mp4（燒入字幕）、out/BACalc_使用說明.srt

用法：python teaching/video/build_video.py
"""
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))

from teaching.video.script import SEGMENTS  # noqa: E402

BUILD = os.path.join(HERE, "build")
OUT = os.path.join(HERE, "out")
NAME = "BACalc_使用說明"
FPS = 30
PAD = 0.5  # 旁白後的緩衝（秒）
# 白字黑框（BorderStyle=1）；不用不透明底框（BorderStyle=3 在 libass 下框底會出現鋸齒狀殘線）
SUB_STYLE = ("FontName=Microsoft JhengHei,FontSize=20,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
             "BackColour=&H80000000,BorderStyle=1,Outline=2,Shadow=1,MarginV=18")
_BREAK = "。！？；，、："
_MAX_CUE = 26  # 每則字幕最多字數（超過再於逗號處切）


def ffmpeg_exe():
    """imageio_ffmpeg 附的 ffmpeg 執行檔。"""
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def srt_time(sec):
    """秒 → SRT 時間字串 HH:MM:SS,mmm。"""
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return "%02d:%02d:%02d,%03d" % (h, m, s, ms)


def _sentences(text):
    """依句末標點（。！？；）斷句，太長的句子再依逗號類標點合併成不超過 _MAX_CUE 字的片段。"""
    text = text.replace("\n", "")
    out = []
    for sent in re.findall(r"[^。！？；]+[。！？；]?", text):
        parts = re.findall(r"[^，、：]+[，、：]?", sent)
        buf = ""
        for p in parts:
            if buf and len(buf) + len(p) > _MAX_CUE:
                out.append(buf)
                buf = ""
            buf += p
        if buf:
            out.append(buf)
    return [s for s in out if s.strip()]


def split_cues(text, duration):
    """把旁白切成字幕 [(開始秒, 結束秒, 文字)]，時間按字數比例分配於 0～duration。

    字幕顯示時去掉句尾的逗號與句號（保留問號等以外的內部標點）。
    """
    parts = _sentences(text)
    weights = [max(1, len(p.strip(_BREAK))) for p in parts]
    total = float(sum(weights))
    cues, t = [], 0.0
    for p, w in zip(parts, weights):
        end = t + duration * w / total
        cues.append((t, end, p.rstrip("，、：。；")))
        t = end
    if cues:
        a, _, txt = cues[-1]
        cues[-1] = (a, duration, txt)
    return cues


def media_seconds(path):
    """解碼整個檔案量實際長度（Playwright 的 webm 沒有 duration 標頭）。"""
    proc = subprocess.run([ffmpeg_exe(), "-hide_banner", "-i", path, "-f", "null", "-"],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    times = re.findall(r"time=(\d+):(\d+):(\d+\.\d+)", proc.stderr)
    if not times:
        raise RuntimeError("量不到長度：%s\n%s" % (path, proc.stderr[-800:]))
    h, m, s = times[-1]
    return int(h) * 3600 + int(m) * 60 + float(s)


def run(cmd, cwd=None):
    """執行 ffmpeg；失敗時丟出含 stderr 結尾的錯誤。"""
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError("ffmpeg 失敗（%d）：%s\n%s" % (proc.returncode, " ".join(cmd[:6]), proc.stderr[-1500:]))
    return proc


def compose_segment(rec, wav, narr, out_mp4):
    """一段：剪掉載入時間、補靜止畫面到 D、混入旁白；回傳實際長度 D。"""
    ff = ffmpeg_exe()
    raw = media_seconds(rec["file"]) - rec["trim"]
    target = max(raw, narr + PAD)
    pad = max(0.0, target - raw) + 0.2
    vf = ("[0:v]fps=%d,setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop_duration=%.3f,"
          "trim=duration=%.3f,setpts=PTS-STARTPTS,format=yuv420p[v]" % (FPS, pad, target))
    af = "[1:a]aresample=48000,apad,atrim=duration=%.3f,asetpts=PTS-STARTPTS[a]" % target
    run([ff, "-y", "-hide_banner", "-ss", "%.3f" % rec["trim"], "-i", rec["file"], "-i", wav,
         "-filter_complex", vf + ";" + af, "-map", "[v]", "-map", "[a]",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-r", str(FPS),
         "-c:a", "aac", "-b:a", "128k", "-ac", "1", "-ar", "48000", out_mp4])
    return media_seconds(out_mp4)


def write_srt(entries, path):
    """entries：[(段落起點秒, 旁白秒數, 旁白文字)] → SRT 檔；回傳字幕則數。"""
    lines, n = [], 0
    for offset, narr, text in entries:
        for a, b, txt in split_cues(text, narr):
            n += 1
            lines += [str(n), "%s --> %s" % (srt_time(offset + a), srt_time(offset + b)), txt, ""]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return n


def main():
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(BUILD, "record.json"), encoding="utf-8") as f:
        recs = {r["id"]: r for r in json.load(f)}
    with open(os.path.join(BUILD, "durations.json"), encoding="utf-8") as f:
        durs = json.load(f)
    seg_files, entries, offset = [], [], 0.0
    for i, seg in enumerate(SEGMENTS):
        name = "seg-%02d" % (i + 1)
        if seg["id"] not in recs:
            raise RuntimeError("缺少錄影：%s（先跑 record.mjs）" % seg["id"])
        out_mp4 = os.path.join(BUILD, name + ".mp4")
        length = compose_segment(recs[seg["id"]], os.path.join(BUILD, name + ".wav"), durs[seg["id"]], out_mp4)
        print("%s %-16s %6.1f 秒（旁白 %.1f）" % (name, seg["id"], length, durs[seg["id"]]))
        seg_files.append(out_mp4)
        entries.append((offset, durs[seg["id"]], seg["narration"]))
        offset += length
    # 串接（各段參數相同，直接複製串流）
    lst = os.path.join(BUILD, "concat.txt")
    with open(lst, "w", encoding="utf-8") as f:
        for p in seg_files:
            f.write("file '%s'\n" % p.replace("\\", "/"))
    joined = os.path.join(BUILD, "joined.mp4")
    run([ffmpeg_exe(), "-y", "-hide_banner", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined])
    srt = os.path.join(OUT, NAME + ".srt")
    n = write_srt(entries, srt)
    # 燒入字幕：subtitles 濾鏡的路徑在 Windows 要跳脫冒號，改在 build/ 下用 ASCII 相對檔名
    shutil.copyfile(srt, os.path.join(BUILD, "subs.srt"))
    final = os.path.join(OUT, NAME + ".mp4")
    run([ffmpeg_exe(), "-y", "-hide_banner", "-i", "joined.mp4",
         "-vf", "subtitles=subs.srt:force_style='%s'" % SUB_STYLE,
         "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-c:a", "copy",
         "-movflags", "+faststart", final], cwd=BUILD)
    print("字幕 %d 則 → %s" % (n, srt))
    print("輸出 %s（約 %.1f 秒）" % (final, offset))
    return 0


if __name__ == "__main__":
    sys.exit(main())
