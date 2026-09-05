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
画框时自动向外让开，避免框线压住按钮文字和组件边界；边线仍落在深色内容上会继续外扩。
何时画框、选区怎么取、脱敏怎么复检，标准都在 references/walkthrough-guide.md
第四、五节，本脚本只管执行。`--blur-radius` 只调模糊强度，不弥补选区错位。

所有百分比都相对**裁剪后的成图**，量到什么就填什么，不用换算。
原图自动备份成 <图名>.orig.png，标错了重跑即可。交付前清掉 .orig.png 和 .grid.png。
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ACCENT = "#D97757"   # 标注框珊瑚色：细圆角描边，在蓝色系界面上醒目不刺眼
MASK = "#DDDDDD"


def _font(size):
    if sys.platform == "win32":
        fonts = os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts")
        candidates = [os.path.join(fonts, name) for name in ("arialbd.ttf", "segoeuib.ttf")]
    elif sys.platform == "darwin":
        candidates = ["/System/Library/Fonts/Helvetica.ttc",
                      "/System/Library/Fonts/Supplemental/Arial.ttf"]
    else:
        candidates = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                      "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"]
    for cand in candidates:
        try:
            return ImageFont.truetype(cand, size)
        except Exception:
            continue
    return ImageFont.load_default(size=size)


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
    with open(_stem(path) + ".grid.json", "w", encoding="utf-8") as f:
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
        # 细描边样式：珊瑚色圆角框（无投影、无白边）+ 序号角标；框线画在目标外侧，不压内容
        lw = max(2, w // 700)
        pad = lw + 2          # 框线与目标之间留空，避免压住按钮文字和组件边界
        corner = max(6, w // 150)
        base = im.convert("RGBA")
        d = ImageDraw.Draw(base)
        br = max(12, w // 110)
        px = base.load()

        def edge_busy(rect):
            """框线要走的这一圈上有多少深色像素（压住按钮或文字的迹象）。"""
            x0, y0, x1, y1 = (int(v) for v in rect)
            pts = [(x, y0) for x in range(x0, x1, 3)] + [(x, y1) for x in range(x0, x1, 3)] \
                + [(x0, y) for y in range(y0, y1, 3)] + [(x1, y) for y in range(y0, y1, 3)]
            pts = [(x, y) for x, y in pts if 0 <= x < w and 0 <= y < h]
            if not pts:
                return 0.0
            dark = sum(1 for x, y in pts
                       if (px[x, y][0] * 299 + px[x, y][1] * 587 + px[x, y][2] * 114) / 1000 < 150)
            return dark / len(pts)

        for i, b in enumerate(boxes):
            r = _rect(b, w, h)
            # 向外扩：框住目标而不是压在目标上；边线压着内容就在小范围内挑最干净的位置
            best, best_busy = pad, 1.0
            for grow in (pad, pad + 2, pad + 4, pad + 6):
                busy = edge_busy([r[0] - grow, r[1] - grow, r[2] + grow, r[3] + grow])
                if busy < 0.12:
                    best = grow
                    break
                if busy < best_busy:
                    best, best_busy = grow, busy
            r = [r[0] - best, r[1] - best, r[2] + best, r[3] + best]
            # 内缩到画布内：框和角标画出图外会被截断，读者看到半个框、半个序号
            m = lw + (br + 2 if len(boxes) > 1 else 0)
            r = [min(max(r[0], m), w - lw - 1), min(max(r[1], m), h - lw - 1),
                 min(max(r[2], m), w - lw - 1), min(max(r[3], m), h - lw - 1)]
            d.rounded_rectangle(r, radius=corner, outline=ACCENT, width=lw)
            if len(boxes) > 1:
                # 多框按传入顺序标序号角标，贴框左上角；含义写在步骤文字里
                cx, cy = r[0], r[1]
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
    with open(meta, encoding="utf-8") as f:
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
    # Windows redirected output may otherwise use a legacy code page.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
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
