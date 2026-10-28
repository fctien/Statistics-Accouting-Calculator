"""旁白合成（narration TTS）：每段旁白用 Windows OneCore 語音 Microsoft Yating（zh-TW）存成 wav，並量長度。

pywin32 SAPI：SpObjectTokenCategory 指向 OneCore 語音登錄機碼取 Yating token → SpVoice ＋ SpFileStream。
（edge-tts 自 2026-10-13 回 403，不使用。）
輸出：teaching/video/build/seg-XX.wav 與 build/durations.json（{段落 id: 秒數}）。
旁白文字的雜湊（hash）存在 build/narration.json，文字沒變就不重新合成。

用法：python teaching/video/narrate.py
"""
import hashlib
import json
import os
import sys
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))

from teaching.video.script import SEGMENTS  # noqa: E402

BUILD = os.path.join(HERE, "build")
ONECORE = r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech_OneCore\Voices"
VOICE_NAME = "Yating"
SAFT24K16BIT_MONO = 26  # SpeechAudioFormatType：24 kHz、16 位元、單聲道
SSFM_CREATE_FOR_WRITE = 3


def seg_name(i):
    """第 i 段（0 起算）的檔名主體。"""
    return "seg-%02d" % (i + 1)


def wav_seconds(path):
    """wav 長度（秒）。"""
    with wave.open(path, "rb") as w:
        return w.getnframes() / float(w.getframerate())


def yating_voice():
    """回傳設定好 Yating 語音的 SpVoice；找不到 Yating 時丟 RuntimeError。"""
    import win32com.client as wc
    cat = wc.Dispatch("SAPI.SpObjectTokenCategory")
    cat.SetId(ONECORE, False)
    tokens = cat.EnumerateTokens()
    for i in range(tokens.Count):
        tok = tokens.Item(i)
        if VOICE_NAME in tok.GetDescription():
            voice = wc.Dispatch("SAPI.SpVoice")
            voice.Voice = tok
            return voice
    raise RuntimeError("找不到 OneCore 語音 Microsoft %s（zh-TW）" % VOICE_NAME)


def synth(voice, text, path):
    """把 text 合成為 path（wav）。"""
    import win32com.client as wc
    stream = wc.Dispatch("SAPI.SpFileStream")
    fmt = wc.Dispatch("SAPI.SpAudioFormat")
    fmt.Type = SAFT24K16BIT_MONO
    stream.Format = fmt
    stream.Open(path, SSFM_CREATE_FOR_WRITE, False)
    try:
        voice.AudioOutputStream = stream
        voice.Speak(text)
    finally:
        stream.Close()
        voice.AudioOutputStream = None


def main():
    os.makedirs(BUILD, exist_ok=True)
    cache_path = os.path.join(BUILD, "narration.json")
    cache = {}
    if os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as f:
            cache = json.load(f)
    voice = None
    durations = {}
    for i, seg in enumerate(SEGMENTS):
        wav = os.path.join(BUILD, seg_name(i) + ".wav")
        digest = hashlib.sha256(seg["narration"].encode("utf-8")).hexdigest()
        if not (os.path.exists(wav) and cache.get(seg["id"]) == digest):
            voice = voice or yating_voice()
            synth(voice, seg["narration"], wav)
            cache[seg["id"]] = digest
        durations[seg["id"]] = round(wav_seconds(wav), 3)
        print("%s %-16s %6.1f 秒" % (seg_name(i), seg["id"], durations[seg["id"]]))
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=1)
    with open(os.path.join(BUILD, "durations.json"), "w", encoding="utf-8") as f:
        json.dump(durations, f, ensure_ascii=False, indent=1)
    total = sum(durations.values())
    print("旁白合計 %.1f 秒（%.2f 分）" % (total, total / 60))
    return 0


if __name__ == "__main__":
    sys.exit(main())
