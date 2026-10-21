"""把教學簡報匯出成 PDF（PowerPoint COM，pywin32）

用法：python teaching/export_pdf.py

安全規則（使用者規定：要關閉或影響使用者開著的程式前必須先問）
- 先用 tasklist 檢查 POWERPNT.EXE 是否在執行
- 正在執行：不匯出、不連上（attach）它，印出說明並 exit 2
  （PowerPoint 是單一 instance 的 COM 伺服器，DispatchEx 也會拿到使用者那一個，所以一定要先檢查）
- 沒有執行：自己開一個 instance，每份簡報以 ReadOnly、WithWindow=False 開啟，
  SaveAs PDF（ppSaveAsPDF = 32）後關閉，最後只 Quit 自己開的那一個

只匯出一般版（BACalc_AI.pptx、BACalc_EMBA.pptx），不匯出講稿版（學生版不含講稿）
結束碼：0 成功；1 錯誤（找不到簡報、COM 失敗、無法檢查 tasklist）；2 PowerPoint 正在執行，未匯出
"""
import os
import subprocess
import sys

TEACHING = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(TEACHING, "out")
DECKS = ["BACalc_AI.pptx", "BACalc_EMBA.pptx"]
PP_SAVE_AS_PDF = 32  # ppSaveAsPDF
RUNNING_MESSAGE = ("PowerPoint 正在執行，為避免影響使用者開啟的檔案，未匯出 PDF；"
                   "請關閉 PowerPoint 後重跑，或由使用者同意後再執行")


def pdf_name(deck):
    """BACalc_AI.pptx → BACalc_AI.pdf"""
    return os.path.splitext(deck)[0] + ".pdf"


def tasklist_output():
    """回傳 tasklist 對 POWERPNT.EXE 的查詢輸出（文字）"""
    p = subprocess.run(["tasklist", "/FI", "IMAGENAME eq POWERPNT.EXE", "/NH"],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    return p.stdout.decode("mbcs" if os.name == "nt" else "utf-8", errors="replace")


def is_powerpoint_running(text):
    """tasklist 輸出中有 POWERPNT.EXE 就視為正在執行（大小寫不敏感）"""
    return "powerpnt.exe" in (text or "").lower()


def new_powerpoint():
    """開一個新的 PowerPoint instance（只在確認沒有執行中的 PowerPoint 之後呼叫）"""
    import win32com.client  # 延後 import：測試與非 Windows 環境不需要 pywin32
    return win32com.client.DispatchEx("PowerPoint.Application")


def export(app, decks, out_dir):
    """Model 之外的實際動作：逐份開啟、另存 PDF、關閉；回傳 PDF 路徑清單"""
    pdfs = []
    for deck in decks:
        src = os.path.abspath(os.path.join(out_dir, deck))
        dst = os.path.abspath(os.path.join(out_dir, pdf_name(deck)))
        pres = app.Presentations.Open(src, ReadOnly=True, Untitled=False, WithWindow=False)
        try:
            pres.SaveAs(dst, PP_SAVE_AS_PDF)
        finally:
            pres.Close()
        pdfs.append(dst)
    return pdfs


def main(out_dir=OUT_DIR, tasklist=tasklist_output, dispatch=new_powerpoint):
    """Controller：檢查 → 匯出；參數可注入假物件以便測試"""
    try:
        running = is_powerpoint_running(tasklist())
    except OSError as e:
        print("無法檢查 PowerPoint 是否在執行（%s），為安全起見不匯出" % e)
        return 1
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
        print("匯出 PDF 失敗：%s" % e)
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
