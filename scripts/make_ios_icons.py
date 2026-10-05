# -*- coding: utf-8 -*-
"""生成 iOS「添加到主屏幕」用的不透明图标（apple-touch-icon + manifest icons）。

为什么必须单独生成（而不是直接用 logo-180.png）：
- iOS 把图标的**透明区域渲染成黑色**，而现有 logo 全系列都是带 alpha 的透明 PNG，
  直接引用会在主屏上出现黑边/黑块。
- iOS 会自己给图标加圆角遮罩，所以我们要的是**满幅不透明方块**，不是预先做好圆角的图。

做法：裁到实体外框 → 用 logo 自身底色填平透明区 → LANCZOS 缩放 → 输出无 alpha 的 RGB PNG。

依赖 Pillow（本机用 C:/Users/Leo/.workbuddy/binaries/python/envs/img）。
这是**一次性资产生成脚本**，不参与每日 CI（CI 只用仓库里已提交的 PNG）。
"""
import os
from collections import Counter
from PIL import Image

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = os.path.join(BASE, "outputs", "assets")
SRC = os.path.join(A, "logo-1024.png")

TARGETS = [("apple-touch-icon.png", 180), ("icon-192.png", 192), ("icon-512.png", 512)]


def main():
    im = Image.open(SRC).convert("RGBA")
    W, H = im.size
    alpha = im.split()[-1]
    bbox = alpha.getbbox()

    # 取不透明像素里出现最多的颜色 = logo 自身底色
    px = im.load()
    cnt = Counter()
    for y in range(0, H, 3):
        for x in range(0, W, 3):
            r, g, b, a = px[x, y]
            if a > 250:
                cnt[(r // 4 * 4, g // 4 * 4, b // 4 * 4)] += 1
    bg = cnt.most_common(1)[0][0]
    print("源图 %s | 实体外框 %s | 填色 %s" % (im.size, bbox, bg))

    # 满幅不透明画布
    flat = Image.new("RGB", (bbox[2] - bbox[0], bbox[3] - bbox[1]), bg)
    flat.paste(im.crop(bbox), (0, 0), im.crop(bbox))

    for name, size in TARGETS:
        out = flat.resize((size, size), Image.LANCZOS)
        p = os.path.join(A, name)
        out.save(p, "PNG", optimize=True)
        chk = Image.open(p)
        print("  → %-24s %s %s  alpha=%s" % (name, chk.size, chk.mode,
              "无（正确）" if chk.mode == "RGB" else "有（错误！）"))


if __name__ == "__main__":
    main()
