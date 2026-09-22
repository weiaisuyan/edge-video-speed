# -*- coding: utf-8 -*-
"""生成 视频速度控制 扩展图标 + 商店素材（v2：▶▶ 双三角，替代旧设计）
设计：圆角方形 + 斜向渐变（石板蓝家族）+ 两个粗壮白色播放三角（▶▶ = 加速播放）
要点：1024 主图 → LANCZOS 降采样；16px 用简化版（三角更大、间距更宽）
"""
import os
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICONS = os.path.join(ROOT, "icons")
STORE = os.path.join(ROOT, "store")
os.makedirs(ICONS, exist_ok=True)
os.makedirs(STORE, exist_ok=True)

C1 = (125, 148, 173)   # 左上 雾霾蓝（扩展默认样式色）
C2 = (56, 72, 92)      # 右下 深石板
SS = 1024


def lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def base(size, c1=C1, c2=C2):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    px = img.load()
    for y in range(size):
        for x in range(size):
            t = (x * 0.65 + y * 0.35) / (size - 1)
            px[x, y] = lerp(c1, c2, t) + (255,)
    return img


def rounded_mask(size, ratio=0.225):
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, size - 1, size - 1], radius=int(size * ratio), fill=255)
    return m


def glyph(img, size, simple=False):
    d = ImageDraw.Draw(img)
    s = size / 1024.0

    def P(x, y):
        return (x * s, y * s)

    if simple:
        d.polygon([P(176, 196), P(176, 828), P(520, 512)], fill=(255, 255, 255, 255))
        d.polygon([P(556, 196), P(556, 828), P(900, 512)], fill=(255, 255, 255, 255))
        return img

    d.polygon([P(232, 250), P(232, 774), P(600, 512)], fill=(255, 255, 255, 255))
    d.polygon([P(600, 250), P(600, 774), P(968, 512)], fill=(255, 255, 255, 245))
    d.line([P(600, 250), P(600, 774)], fill=(0, 0, 0, 0), width=max(2, int(14 * s)))
    return img


def build_icon(size=SS):
    img = base(size)
    hl = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(hl).ellipse([-size * 0.35, -size * 0.6, size * 0.8, size * 0.3], fill=(255, 255, 255, 30))
    img = Image.alpha_composite(img, hl)
    img = glyph(img, size, simple=False)
    img.putalpha(rounded_mask(size))
    return img


def build_simple(size=512):
    img = base(size)
    img = glyph(img, size, simple=True)
    img.putalpha(rounded_mask(size))
    return img


def font(px, bold=True):
    for p in ((r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc"),
              r"C:\Windows\Fonts\msyh.ttc"):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, px)
            except Exception:
                pass
    return ImageFont.load_default()


def build_flat(size, bg, gap=110, radius=0.225):
    """小尺寸专用：纯色底（去渐变/高光）+ 加粗双三角 + 更宽的缝（16/32px 才看得清是两个三角）"""
    img = Image.new("RGBA", (size, size), bg + (255,))
    d = ImageDraw.Draw(img)
    k = size / 1024.0

    def P(x, y):
        return (x * k, y * k)

    mid = 512
    d.polygon([P(200, 232), P(200, 792), P(mid - gap, 512)], fill=(255, 255, 255, 255))
    d.polygon([P(mid + gap, 232), P(mid + gap, 792), P(824, 512)], fill=(255, 255, 255, 255))
    img.putalpha(rounded_mask(size, radius))
    return img


def tile(w, h, icon_px, title, sub):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = img.load()
    for y in range(h):
        for x in range(w):
            t = (x * 0.5 + y * 0.5) / (w - 1)
            px[x, y] = lerp((32, 37, 46), (17, 20, 25), t) + (255,)
    ic = build_icon(SS).resize((icon_px, icon_px), Image.LANCZOS)
    ix = int(w * 0.075)
    iy = (h - icon_px) // 2
    img.paste(ic, (ix, iy), ic)
    d = ImageDraw.Draw(img)
    tx = ix + icon_px + int(w * 0.04)
    d.text((tx, iy + icon_px * 0.14), title, font=font(int(icon_px * 0.34)), fill=(255, 255, 255, 255))
    d.text((tx, iy + icon_px * 0.62), sub, font=font(int(icon_px * 0.17), bold=False), fill=(158, 170, 185, 255))
    return img


if __name__ == "__main__":
    master = build_icon()
    for target in (128, 48):
        master.resize((target, target), Image.LANCZOS).save(os.path.join(ICONS, "icon%d.png" % target))
    # 小尺寸：纯色 + 加粗 + 更宽的缝
    build_flat(512, (74, 90, 108), gap=105).resize((32, 32), Image.LANCZOS).save(os.path.join(ICONS, "icon32.png"))
    build_flat(512, (74, 90, 108), gap=130).resize((16, 16), Image.LANCZOS).save(os.path.join(ICONS, "icon16.png"))

    master.resize((1024, 1024), Image.LANCZOS).save(os.path.join(STORE, "icon-1024.png"))
    master.resize((300, 300), Image.LANCZOS).save(os.path.join(STORE, "logo-300.png"))
    tile(440, 280, 168, "视频速度控制", "点一下就能调速").save(os.path.join(STORE, "tile-440x280.png"))
    tile(1400, 560, 300, "视频速度控制", "页面内悬浮按钮 · 点一下调速").save(
        os.path.join(STORE, "tile-1400x560.png"))

    print("icons:", sorted(os.listdir(ICONS)))
    print("store:", sorted(os.listdir(STORE)))
    for n in ("icon16.png", "icon32.png"):
        im = Image.open(os.path.join(ICONS, n)).convert("RGBA")
        w = im.width
        cols = [sum(1 for y in range(w) if im.getpixel((x, y))[0] > 190 and im.getpixel((x, y))[3] > 190)
                for x in range(w)]
        mid = w // 2
        gap_cols = sum(1 for x in range(w) if cols[x] == 0)
        print("%s 白像素=%d 空列=%d 中间两列=%s 每列=%s" % (
            n, sum(cols), gap_cols, cols[mid - 1:mid + 1], cols))
