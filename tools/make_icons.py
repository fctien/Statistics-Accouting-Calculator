"""產生 PWA 圖示（icon）：web/icons/icon-192.png、icon-512.png。

淺藍底（#1565c0）圓角方塊＋白色「BA」字樣。使用已安裝的 Pillow（PIL）；
本工具只在需要重畫圖示時手動執行，產出的 PNG 已 commit。
用法：python tools/make_icons.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
BLUE = (21, 101, 192, 255)
WHITE = (255, 255, 255, 255)


def _font(size):
    """優先用系統粗體字型，找不到就用 Pillow 內建字型。"""
    for name in ("arialbd.ttf", "DejaVuSans-Bold.ttf", "Arial Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def draw_icon(size):
    """畫一個 size×size 的圖示，回傳 Image。"""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=size // 6,
                        fill=BLUE)
    font = _font(int(size * 0.42))
    text = "BA"
    l, t, r, b = d.textbbox((0, 0), text, font=font)
    d.text(((size - (r - l)) / 2 - l, (size - (b - t)) / 2 - t - size * 0.04),
           text, font=font, fill=WHITE)
    # 下方一條白線，像計算機顯示列
    y = int(size * 0.78)
    d.rounded_rectangle([size * 0.25, y, size * 0.75, y + size * 0.05],
                        radius=size // 50, fill=WHITE)
    return img


def main():
    out = ROOT / "web" / "icons"
    out.mkdir(parents=True, exist_ok=True)
    for size in (192, 512):
        draw_icon(size).save(out / ("icon-%d.png" % size), optimize=True)
        print("已產生 web/icons/icon-%d.png" % size)


if __name__ == "__main__":
    main()
