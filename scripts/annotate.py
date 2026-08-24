"""给截图模糊脱敏、不可逆遮挡、画标注框和裁剪，位置按百分比给。

browser.py 的 --mask / --highlight 靠 CSS selector，控制台类 SPA（阿里云、
腾讯云等）的 class 是随机哈希，选择器匹配不上，这时改用本脚本按比例坐标画。

**必须先量再画**：凭肉眼估比例基本每次都偏。没跑过 --grid 就画框会直接报错。

    # 1. 量：带上最终要用的 --crop，出一张带百分比网格的图，从上面读坐标
    python3 scripts/annotate.py shot.png --crop 10,75 --grid

    # 2. 画：普通敏感文字用 --blur；密钥、令牌等秘密才用 --fill
    python3 scripts/annotate.py shot.png --crop 10,75 \
      --box 14,36,73,44 --blur 10,20,45,28 --fill 85,0,100,7

`--box` 传入多个时按传入顺序在框左上角自动画 ①②③ 序号角标（单框不画）。
何时画框、选区怎么取、脱敏怎么复检，标准都在 references/walkthrough-guide.md
第四、五节，本脚本只管执行。`--blur-radius` 只调模糊强度，不弥补选区错位。

所有百分比都相对**裁剪后的成图**，量到什么就填什么，不用换算。
原图自动备份成 <图名>.orig.png，标错了重跑即可。交付前清掉 .orig.png 和 .grid.png。
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ACCENT = "#D97757"   # 标注框珊瑚色：白边圆角描边，在蓝色系界面上醒目不刺眼
SHADOW = (31, 35, 41, 110)
MASK = "#DDDDDD"


def _font(size):
    for cand in (
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ):
        try:
            return ImageFont.truetype(cand, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _stem(path):
    return path.rsplit(".", 1)[0]


def _load(path, crop):
    """取原图（首次调用时备份），按 crop 裁到最终尺寸。"""
    orig = path + ".orig.png"
    if not os.path.exists(orig):
        Image.open(path).save(orig)
    im = Image.open(orig).convert("RGB")
    if crop:
        w, h = im.size
        im = im.crop((0, int(crop[0] / 100 * h), w, int(crop[1] / 100 * h)))
    return im


def _rect(box, w, h):
    x0, y0, x1, y1 = box
    return [x0 / 100 * w, y0 / 100 * h, x1 / 100 * w, y1 / 100 * h]


def grid(path, crop):
    """出一张带百分比网格的图用来量，并记下这次量的是哪种裁剪。"""
    im = _load(path, crop)
    im = im.resize((900, int(im.height * 900 / im.width)))
    d = ImageDraw.Draw(im)
    w, h = im.size
    for i in range(1, 20):
        x, y = w * i / 20, h * i / 20
        d.line([(x, 0), (x, h)], fill="#00A0FF")
        d.text((x + 2, 4), str(i * 5), fill="#0080D0")
        d.line([(0, y), (w, y)], fill="#FF9000")
        d.text((3, y + 2), str(i * 5), fill="#D06000")
    out = _stem(path) + ".grid.png"
    im.save(out)
    with open(_stem(path) + ".grid.json", "w") as f:
        json.dump({"crop": crop}, f)
    return out


def annotate(path, boxes, fills, blurs, crop, blur_radius=None):
    im = _load(path, crop)
    w, h = im.size
    radius = blur_radius if blur_radius is not None else max(10, round(w / 90))
    for b in blurs:
        rect = tuple(int(v) for v in _rect(b, w, h))
        region = im.crop(rect).filter(ImageFilter.GaussianBlur(radius=radius))
        im.paste(region, rect)
    d = ImageDraw.Draw(im)
    for f in fills:
        d.rectangle(_rect(f, w, h), fill=MASK)

    if boxes:
        # 柔和描边样式：投影 → 白色外圈 → 珊瑚色圆角框 → 序号角标
        lw = max(3, w // 400)
        corner = max(8, w // 120)
        base = im.convert("RGBA")
        shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        for b in boxes:
            r = _rect(b, w, h)
            sd.rounded_rectangle([r[0] + 2, r[1] + 3, r[2] + 2, r[3] + 3],
                                 radius=corner, outline=SHADOW, width=lw + 2)
        base = Image.alpha_composite(base, shadow.filter(ImageFilter.GaussianBlur(3)))
        d = ImageDraw.Draw(base)
        br = max(12, w // 110)
        for i, b in enumerate(boxes):
            r = _rect(b, w, h)
            # 内缩到画布内：框和角标画出图外会被截断，读者看到半个框、半个序号
            m = lw + 2 + (br + 2 if len(boxes) > 1 else 0)
            r = [min(max(r[0], m), w - lw - 2), min(max(r[1], m), h - lw - 2),
                 min(max(r[2], m), w - lw - 2), min(max(r[3], m), h - lw - 2)]
            d.rounded_rectangle([r[0] - lw, r[1] - lw, r[2] + lw, r[3] + lw],
                                radius=corner + lw, outline="#ffffff", width=lw + 2)
            d.rounded_rectangle(r, radius=corner, outline=ACCENT, width=lw)
            if len(boxes) > 1:
                # 多框按传入顺序标序号角标，贴框左上角；含义写在步骤文字里
                cx, cy = r[0], r[1]
                d.ellipse([cx - br - 2, cy - br - 2, cx + br + 2, cy + br + 2], fill="#ffffff")
                d.ellipse([cx - br, cy - br, cx + br, cy + br], fill=ACCENT)
                num = str(i + 1)
                font = _font(int(br * 1.3))
                tb = d.textbbox((0, 0), num, font=font)
                d.text((cx - (tb[2] - tb[0]) / 2 - tb[0], cy - (tb[3] - tb[1]) / 2 - tb[1]),
                       num, fill="#ffffff", font=font)
        im = base.convert("RGB")
    im.save(path)
    return im.size


def check_measured(path, crop):
    """没量过就不许画：坐标靠估必偏，这条是硬约束。"""
    meta = _stem(path) + ".grid.json"
    if not os.path.exists(meta):
        sys.exit(
            f"× 还没量过 {os.path.basename(path)}，不能直接画框。\n"
            f"  先跑：annotate.py {path}"
            + (f" --crop {crop[0]:g},{crop[1]:g}" if crop else "")
            + " --grid\n  从网格图上读出坐标，再回来画。"
        )
    with open(meta) as f:
        measured = json.load(f).get("crop")
    if (measured or None) != (list(crop) if crop else None):
        sys.exit(
            f"× --crop 和量的时候不一致（量的是 {measured}，现在是 "
            f"{list(crop) if crop else None}）。\n"
            f"  裁剪一变，百分比就全错位了。用同样的 --crop 重新 --grid。"
        )


def _nums(v):
    return tuple(float(x) for x in v.split(","))


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    path, boxes, fills, blurs, crop, blur_radius, want_grid = (
        args[0], [], [], [], None, None, False
    )
    i = 1
    while i < len(args):
        if args[i] == "--grid":
            want_grid = True; i += 1
        elif args[i] == "--box":
            boxes.append(_nums(args[i + 1])); i += 2
        elif args[i] == "--fill":
            fills.append(_nums(args[i + 1])); i += 2
        elif args[i] == "--blur":
            blurs.append(_nums(args[i + 1])); i += 2
        elif args[i] == "--blur-radius":
            blur_radius = float(args[i + 1]); i += 2
        elif args[i] == "--crop":
            crop = _nums(args[i + 1]); i += 2
        else:
            i += 1

    if want_grid:
        print(grid(path, crop))
    else:
        if boxes or fills or blurs:
            check_measured(path, crop)
        print(path, annotate(path, boxes, fills, blurs, crop, blur_radius))
