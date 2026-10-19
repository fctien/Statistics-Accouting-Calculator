"""把 docs/ 下的 Markdown 文件轉成可閱讀的 HTML（HTML 版規格書、計畫）。

用法：python tools/md2html.py docs/spec-2026-10-19.md
"""
import sys
from pathlib import Path

import markdown

# 頁面樣板（template）：淺藍白配色，與教材風格一致
TEMPLATE = """<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
body {{ font-family: "Microsoft JhengHei", "Noto Sans TC", sans-serif;
       max-width: 960px; margin: 0 auto; padding: 16px; line-height: 1.7;
       color: #1f2d3d; background: #fff; }}
h1, h2 {{ color: #1565c0; border-bottom: 2px solid #bbdefb; padding-bottom: 4px; }}
h3 {{ color: #1976d2; }}
table {{ border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 15px; }}
th, td {{ border: 1px solid #bbdefb; padding: 6px 8px; vertical-align: top; }}
th {{ background: #e3f2fd; }}
code {{ background: #f1f8ff; padding: 1px 4px; border-radius: 3px; }}
pre {{ background: #f1f8ff; padding: 12px; overflow-x: auto; }}
blockquote {{ border-left: 4px solid #64b5f6; margin: 0; padding: 4px 12px;
             background: #f5faff; }}
</style></head><body>
{body}
</body></html>
"""


def convert(md_path: Path) -> Path:
    """轉換單一 Markdown 檔，輸出同名 .html，回傳輸出路徑。"""
    text = md_path.read_text(encoding="utf-8")
    body = markdown.markdown(text, extensions=["tables", "fenced_code"])
    title = text.splitlines()[0].lstrip("# ").strip()
    out = md_path.with_suffix(".html")
    out.write_text(TEMPLATE.format(title=title, body=body), encoding="utf-8")
    return out


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        print(convert(Path(arg)))
