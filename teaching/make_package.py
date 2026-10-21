"""學生版 zip（AI 版、EMBA 版）

用法
    python teaching/make_package.py          只檢查檔案是否齊全，不寫 zip
    python teaching/make_package.py --zip    產生 teaching/out/BACalc_AI_student.zip、BACalc_EMBA_student.zip

每份 zip 內容（使用者規定：簡報只放 PDF，不放 pptx、不放講稿）
- Prompt卡_AI.html 或 Prompt卡_EMBA.html
- BACalc_AI.pdf 或 BACalc_EMBA.pdf（先跑 python teaching/export_pdf.py）
- google-oauth-setup.html（docs/）
- 學生說明.txt：怎麼 clone、怎麼切換 tag、卡片在哪裡

缺 PDF 時不產生任何 zip，回報錯誤（exit 1）
"""
import argparse
import os
import sys
import zipfile

TEACHING = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TEACHING)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from teaching import prompts  # noqa: E402  Model：步驟與 tag 的單一來源

OUT_DIR = os.path.join(TEACHING, "out")
DOCS_DIR = os.path.join(ROOT, "docs")
REPO_URL = "https://github.com/fctien/Statistics-Accouting-Calculator.git"
SITE_URL = "https://fctien.github.io/Statistics-Accouting-Calculator/"
VERSIONS = {"ai": "AI", "emba": "EMBA"}
OAUTH = "google-oauth-setup.html"


class PackageError(Exception):
    """檔案不齊全，不能打包"""


def members(version, out_dir, docs_dir):
    """回傳 [(zip 內名稱, 來源路徑)]，不含說明檔"""
    v = VERSIONS[version]
    return [
        ("Prompt卡_%s.html" % v, os.path.join(out_dir, "Prompt卡_%s.html" % v)),
        ("BACalc_%s.pdf" % v, os.path.join(out_dir, "BACalc_%s.pdf" % v)),
        (OAUTH, os.path.join(docs_dir, OAUTH)),
    ]


def readme_text(version):
    """學生說明.txt（不用全形句點）"""
    v = VERSIONS[version]
    lines = [
        "BACalc 學生版（%s 版）" % v,
        "",
        "一、檔案",
        "- Prompt卡_%s.html：每個步驟一張卡，用瀏覽器開啟，Prompt 原文有複製鈕，可列印" % v,
        "- BACalc_%s.pdf：上課簡報" % v,
        "- google-oauth-setup.html：只有要用 Google Drive 同步（選用步驟 step7）才需要",
        "",
        "二、取得程式碼（需要先安裝 git）",
        "  git clone %s BACalc" % REPO_URL,
        "  cd BACalc",
        "  git fetch --tags",
        "  git tag            列出所有步驟的 tag",
        "",
        "三、切換到某一步",
    ]
    if version == "ai":
        lines += [
            "AI 版從空資料夾自己跟著 Prompt 卡做，每做完一步可以和參考答案的 tag 對照",
            "  git checkout step2       看 step2 完成時的參考答案（唯讀瀏覽）",
            "  git checkout main        回到最新版",
            "各步驟完成後對照的 tag：",
        ]
        for s in prompts.STEPS:
            done = s["tag"] or "沒有 tag（選用，作者未實測）"
            lines.append("  %s  %s  →  %s" % (s["id"], s["title"], done))
    else:
        lines += [
            "EMBA 版每一步從「起點 tag」接手，只做該步的 Prompt 與對答案",
            "  git checkout -b my-step2 step1     以 step1 為起點做 step2（開自己的分支）",
            "各步驟的起點 tag：",
        ]
        for s in prompts.STEPS:
            lines.append("  %s  %s  起點 %s" % (s["id"], s["title"], s["emba"]["start_tag"]))
    lines += [
        "",
        "四、線上版計算機",
        "  %s（第一次需連網，之後可離線）" % SITE_URL,
        "",
        "注意：tag 是作者完成時的狀態；step9 的 tag 在部署與手機實測後才會建立",
    ]
    text = "\n".join(lines) + "\n"
    return text.replace("。", "")


def check(out_dir=OUT_DIR, docs_dir=DOCS_DIR):
    """檢查所有要打包的檔案；缺檔就擲 PackageError（缺 PDF 時特別說明怎麼產生）"""
    missing = []
    for version in VERSIONS:
        for name, src in members(version, out_dir, docs_dir):
            if not os.path.exists(src):
                missing.append(src)
    if missing:
        pdf = any(m.endswith(".pdf") for m in missing)
        msg = "缺少檔案，不產生 zip：\n  " + "\n  ".join(missing)
        if pdf:
            msg += ("\n簡報 PDF 不存在：請關閉 PowerPoint 後執行 python teaching/export_pdf.py"
                    "（學生版只放 PDF，不放 pptx）")
        raise PackageError(msg)


def build_all(out_dir=OUT_DIR, docs_dir=DOCS_DIR):
    """產生兩份 zip，回傳路徑清單；先完整檢查，任何缺檔都不寫 zip"""
    check(out_dir, docs_dir)
    paths = []
    for version, v in VERSIONS.items():
        path = os.path.join(out_dir, "BACalc_%s_student.zip" % v)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            for name, src in members(version, out_dir, docs_dir):
                # 防呆：規則是簡報只放 PDF、不含講稿
                assert not name.endswith(".pptx") and "講稿" not in name, name
                z.write(src, name)
            z.writestr("學生說明.txt", readme_text(version).encode("utf-8"))
        paths.append(path)
    return paths


def main(argv=None, out_dir=OUT_DIR, docs_dir=DOCS_DIR):
    ap = argparse.ArgumentParser(description="BACalc 學生版 zip")
    ap.add_argument("--zip", action="store_true", help="產生 zip（不加只檢查）")
    args = ap.parse_args(argv)
    try:
        if not args.zip:
            check(out_dir, docs_dir)
            print("檔案齊全（未產生 zip；加 --zip 才會寫）")
            return 0
        for p in build_all(out_dir, docs_dir):
            print("寫入", p, os.path.getsize(p), "bytes")
        return 0
    except PackageError as e:
        print(str(e))
        return 1


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    sys.exit(main())
