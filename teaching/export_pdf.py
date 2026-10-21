"""把教學簡報匯出成 PDF（PowerPoint COM，pywin32）

用法：python teaching/export_pdf.py

安全規則（使用者規定：要關閉或影響使用者開著的程式前必須先問）
- 先用 tasklist（CSV 格式、列出全部行程）檢查 POWERPNT.EXE 是否在執行
- 正在執行：不匯出、不連上（attach）它，印出說明並 exit 2
  （PowerPoint 是單一 instance 的 COM 伺服器，DispatchEx 也會拿到使用者那一個，所以一定要先檢查）
- 無法判斷（tasklist 無法執行、結束碼非 0、輸出無法解析）：一律當成「可能在執行」，不匯出、exit 2（fail-safe）
- 確定沒有執行：自己開一個 instance，每份簡報以 ReadOnly、WithWindow=False 開啟，
  SaveAs PDF（ppSaveAsPDF = 32）後關閉，最後只 Quit 自己開的那一個
- 匯出途中失敗：刪掉本次要寫的 PDF（含寫到一半的），避免留下不完整或新舊混雜的檔案

只匯出一般版（BACalc_AI.pptx、BACalc_EMBA.pptx），不匯出講稿版（學生版不含講稿）
結束碼：0 成功；1 錯誤（找不到簡報、COM 失敗）；2 PowerPoint 正在執行或無法確定，未匯出
"""
import csv
import os
import subprocess
import sys

TEACHING = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(TEACHING, "out")
DECKS = ["BACalc_AI.pptx", "BACalc_EMBA.pptx"]
PP_SAVE_AS_PDF = 32  # ppSaveAsPDF
RUNNING_MESSAGE = ("PowerPoint 正在執行，為避免影響使用者開啟的檔案，未匯出 PDF；"
                   "請關閉 PowerPoint 後重跑，或由使用者同意後再執行")
UNKNOWN_MESSAGE = ("無法確定 PowerPoint 是否正在執行（%s），為避免影響使用者開啟的檔案，未匯出 PDF；"
                   "請確認 PowerPoint 已關閉後重跑")


def pdf_name(deck):
    """BACalc_AI.pptx → BACalc_AI.pdf"""
    return os.path.splitext(deck)[0] + ".pdf"


def tasklist_output():
    """回傳 (結束碼, 輸出文字)：tasklist /FO CSV /NH 列出全部行程（CSV 格式與語系無關）"""
    p = subprocess.run(["tasklist", "/FO", "CSV", "/NH"],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    return p.returncode, p.stdout.decode("mbcs" if os.name == "nt" else "utf-8", errors="replace")


def is_powerpoint_running(text):
    """解析 tasklist CSV：True 正在執行、False 確定沒有、None 無法判斷

    每一列都必須是「"映像名稱","PID",…」至少 5 欄且 PID 為數字；任何一列不符，
    或一列都沒有（錯誤訊息、空輸出），就回 None，呼叫端不可匯出
    """
    rows = [r for r in csv.reader((text or "").splitlines()) if r]
    if not rows:
        return None
    for r in rows:
        if len(r) < 5 or not r[1].strip().isdigit():
            return None
    return any(r[0].strip().lower() == "powerpnt.exe" for r in rows)


def new_powerpoint():
    """開一個新的 PowerPoint instance（只在確認沒有執行中的 PowerPoint 之後呼叫）"""
    import win32com.client  # 延後 import：測試與非 Windows 環境不需要 pywin32
    return win32com.client.DispatchEx("PowerPoint.Application")


def remove_quietly(paths):
    """刪除本次的 PDF（不存在就略過）"""
    for p in paths:
        try:
            os.remove(p)
        except OSError:
            pass


def export(app, decks, out_dir):
    """逐份開啟、另存 PDF、關閉；任何一份失敗就刪掉本次全部的 PDF 再擲出例外；回傳 PDF 路徑清單"""
    pdfs = []
    try:
        for deck in decks:
            src = os.path.abspath(os.path.join(out_dir, deck))
            dst = os.path.abspath(os.path.join(out_dir, pdf_name(deck)))
            pdfs.append(dst)  # 先記下，失敗時寫到一半的也一起刪
            pres = app.Presentations.Open(src, ReadOnly=True, Untitled=False, WithWindow=False)
            try:
                pres.SaveAs(dst, PP_SAVE_AS_PDF)
            finally:
                pres.Close()
    except Exception:
        remove_quietly(pdfs)
        raise
    return pdfs


def main(out_dir=OUT_DIR, tasklist=tasklist_output, dispatch=new_powerpoint):
    """Controller：檢查 → 匯出；參數可注入假物件以便測試"""
    try:
        code, text = tasklist()
    except OSError as e:
        print(UNKNOWN_MESSAGE % ("tasklist 無法執行：%s" % e))
        return 2
    if code != 0:
        print(UNKNOWN_MESSAGE % ("tasklist 結束碼 %d" % code))
        return 2
    running = is_powerpoint_running(text)
    if running is None:
        print(UNKNOWN_MESSAGE % "tasklist 輸出無法解析")
        return 2
    if running:
        print(RUNNING_MESSAGE)
        return 2
    missing = [d for d in DECKS if not os.path.exists(os.path.join(out_dir, d))]
    if missing:
        print("找不到簡報：%s（請先跑 python teaching/deck/build_deck.py）" % "、".join(missing))
        return 1
    try:
        app = dispatch()
    except Exception as e:  # pywin32 未安裝或 COM 無法啟動
        print("無法啟動 PowerPoint（%s）" % e)
        return 1
    try:
        pdfs = export(app, DECKS, out_dir)
    except Exception as e:
        print("匯出 PDF 失敗（已刪除本次的 PDF）：%s" % e)
        return 1
    finally:
        app.Quit()  # 只關自己開的 instance
    for p in pdfs:
        print("寫入", p, os.path.getsize(p) if os.path.exists(p) else "?", "bytes")
    return 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    sys.exit(main())
