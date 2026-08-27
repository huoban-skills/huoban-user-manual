#!/usr/bin/env python3
"""册头的全流程图（一册一张）：flow.json → SVG。

改自 huoban-automation-blueprint 的 render_flow.py。那边步骤卡片副行标的是
承载它的自动化；这里读者是业务操作者，副行标这一步落在哪张表（跟手册章节
对应，读图即知去哪章找操作细节），系统自动完成的环节置灰虚线，人工操作的
用彩色：读者一眼看清整个流程自己要动手几次、系统帮着干几步。

分组横向排（业务阶段/岗位环节），组内步骤纵向排。

用法：
    python3 scripts/flow.py flow.json images/0-全流程总览.svg

flow.json：
{
  "groups": [
    {"name": "销售环节", "steps": [
      {"text": "创建销售订单", "table": "销售订单"},
      {"text": "生成应收记录", "table": "应收单", "auto": true}
    ]},
    {"name": "财务环节", "steps": [
      {"text": "登记收款", "table": "收款单"}
    ]}
  ]
}

step 是字符串（只有步骤名）或对象：
    "text"  — 步骤名
    "table" — 这一步落在哪张表（副行显示；没有就不显示副行）
    "auto"  — true 表示系统自动完成，卡片置灰虚线，副行前缀「系统自动」
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

# 分组配色（容器底色，强调色），循环使用。
PALETTE = [
    ("#EEEFFB", "#5E6AD2"),
    ("#EAF6F0", "#4CB782"),
    ("#EBF4FE", "#4EA7FC"),
    ("#FDF0E9", "#FC7840"),
    ("#F3EFFB", "#9B7ED9"),
]

AUTO_INK = "#8f959e"   # 系统自动环节用灰，跟人工环节的彩色一眼区分

PAD = 18
GROUP_PAD_X = 16
HEADER_H = 28
STEP_W_MIN = 190
STEP_W_MAX = 300
STEP_H = 44
STEP_GAP = 20
GROUP_GAP = 26
GROUP_BOTTOM = 14
FS_STEP = 13
FS_HEADER = 12
FONT = '\'PingFang SC\', \'Helvetica Neue\', \'Microsoft YaHei\', Arial, sans-serif'


def _char_w(ch: str, fs: float) -> float:
    o = ord(ch)
    if o > 0x2E7F:
        return fs
    if ch == " ":
        return fs * 0.3
    return fs * 0.56


def text_width(s: str, fs: float) -> float:
    return sum(_char_w(c, fs) for c in s)


def wrap(s: str, max_w: float, fs: float, max_lines: int = 2) -> list:
    tokens = re.findall(r"[A-Za-z0-9]+|.", s)
    lines = [""]
    for t in tokens:
        if t == " " and lines[-1] == "":
            continue
        trial = lines[-1] + t
        if text_width(trial, fs) > max_w and lines[-1]:
            if len(lines) >= max_lines:
                lines[-1] = trial
            else:
                lines.append(t if t != " " else "")
        else:
            lines[-1] = trial
    return [ln for ln in lines if ln] or [""]


def _parts(step):
    """(步骤名, 副行文字, 是否系统自动)。副行为空串则不显示。"""
    if isinstance(step, str):
        return step, "", False
    auto = bool(step.get("auto"))
    table = step.get("table", "")
    if auto:
        sub = "系统自动 · " + table if table else "系统自动"
    else:
        sub = table
    return step.get("text", ""), sub, auto


def render_svg(data: dict) -> str:
    groups = data.get("groups", [])

    need = 0.0
    for g in groups:
        for step in g.get("steps", []):
            text, sub, _ = _parts(step)
            need = max(need, text_width(text, FS_STEP) + 28)
            if sub:
                need = max(need, text_width(sub, 12) + 24)
    step_w = min(max(STEP_W_MIN, need), STEP_W_MAX)

    two_line = any(
        text_width(_parts(s)[0], FS_STEP) > step_w - 24
        for g in groups for s in g.get("steps", [])
    )
    step_h = STEP_H + (16 if two_line else 0)
    group_w = step_w + 2 * GROUP_PAD_X

    max_steps = max((len(g.get("steps", [])) for g in groups), default=0)
    body_h = max_steps * step_h + max(max_steps - 1, 0) * STEP_GAP
    group_h = HEADER_H + 8 + body_h + GROUP_BOTTOM

    width = 2 * PAD + len(groups) * group_w + max(len(groups) - 1, 0) * GROUP_GAP
    height = 2 * PAD + group_h
    cy = PAD + group_h / 2

    boxes = []
    conts = []
    varrows = []
    harrows = []

    x = PAD
    for gi, g in enumerate(groups):
        tint, accent = PALETTE[gi % len(PALETTE)]
        steps = g.get("steps", [])
        sx = x + GROUP_PAD_X
        cx = sx + step_w / 2
        sy = PAD + HEADER_H + 8
        for si, step in enumerate(steps):
            text, sub, auto = _parts(step)
            boxes.append({"x": sx, "y": sy, "text": text, "sub": sub,
                          "accent": AUTO_INK if auto else accent, "auto": auto})
            if si < len(steps) - 1:
                varrows.append((cx, sy + step_h, sy + step_h + STEP_GAP))
            sy += step_h + STEP_GAP
        conts.append({"x": x, "name": g.get("name", ""), "tint": tint, "accent": accent})
        if gi < len(groups) - 1:
            harrows.append((cy, x + group_w, x + group_w + GROUP_GAP))
        x += group_w + GROUP_GAP

    p = []
    p.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height:.0f}" '
        f'viewBox="0 0 {width} {height:.0f}" font-family="{FONT}">'
    )
    p.append(
        '<defs>'
        '<marker id="arw" markerWidth="9" markerHeight="9" refX="6" refY="3" orient="auto" markerUnits="userSpaceOnUse">'
        '<path d="M0,0 L6,3 L0,6 Z" fill="#9aa3b2"/></marker>'
        '<filter id="sh" x="-20%" y="-20%" width="140%" height="140%">'
        '<feDropShadow dx="0" dy="1" stdDeviation="2" flood-color="#1f2329" flood-opacity="0.10"/></filter>'
        '</defs>'
    )
    p.append(f'<rect x="0" y="0" width="{width}" height="{height:.0f}" fill="#ffffff"/>')

    for c in conts:
        p.append(
            f'<rect x="{c["x"]:.0f}" y="{PAD}" width="{group_w}" height="{group_h:.0f}" rx="14" '
            f'fill="{c["tint"]}" stroke="{c["accent"]}" stroke-opacity="0.35" stroke-width="1"/>'
        )
        p.append(
            f'<text x="{c["x"] + GROUP_PAD_X:.0f}" y="{PAD + 19}" font-size="{FS_HEADER}" '
            f'font-weight="700" fill="{c["accent"]}">{html.escape(c["name"])}</text>'
        )

    for ax, y1, y2 in varrows:
        p.append(
            f'<line x1="{ax:.0f}" y1="{y1:.0f}" x2="{ax:.0f}" y2="{y2 - 2:.0f}" '
            f'stroke="#9aa3b2" stroke-width="1.5" marker-end="url(#arw)"/>'
        )
    for ay, x1, x2 in harrows:
        p.append(
            f'<line x1="{x1:.0f}" y1="{ay:.0f}" x2="{x2 - 2:.0f}" y2="{ay:.0f}" '
            f'stroke="#9aa3b2" stroke-width="1.5" marker-end="url(#arw)"/>'
        )

    name_lines_max = 2 if two_line else 1
    for b in boxes:
        dash = ' stroke-dasharray="4 3"' if b["auto"] else ""
        p.append(
            f'<rect x="{b["x"]}" y="{b["y"]:.0f}" width="{step_w}" height="{step_h}" rx="9" '
            f'fill="#ffffff" stroke="{b["accent"]}" stroke-width="1.5"{dash} filter="url(#sh)"/>'
        )
        bx = b["x"] + step_w / 2
        if b["sub"]:
            names = wrap(b["text"], step_w - 24, FS_STEP, max_lines=name_lines_max)
            lh = FS_STEP * 1.3
            for i, ln in enumerate(names):
                p.append(
                    f'<text x="{bx:.0f}" y="{b["y"] + 18 + i * lh:.1f}" font-size="{FS_STEP}" '
                    f'fill="#1f2329" text-anchor="middle">{html.escape(ln)}</text>'
                )
            sub = wrap(b["sub"], step_w - 20, 11, max_lines=1)[0]
            p.append(
                f'<text x="{bx:.0f}" y="{b["y"] + step_h - 10:.0f}" font-size="11" '
                f'fill="{b["accent"]}" text-anchor="middle">{html.escape(sub)}</text>'
            )
        else:
            lines = wrap(b["text"], step_w - 24, FS_STEP, max_lines=name_lines_max + 1)
            lh = FS_STEP * 1.3
            mid = b["y"] + step_h / 2
            start = mid - (len(lines) - 1) * lh / 2 + FS_STEP * 0.35
            for i, ln in enumerate(lines):
                p.append(
                    f'<text x="{bx:.0f}" y="{start + i * lh:.1f}" font-size="{FS_STEP}" '
                    f'fill="#1f2329" text-anchor="middle">{html.escape(ln)}</text>'
                )

    p.append("</svg>")
    return "".join(p)


def check_wording(data: dict) -> list:
    """节点文字按正文同一套措辞规则查。

    流程图长期在机检之外：正文里「回写」「拉取」改干净了，图上照旧挂着，
    读者先看图后读正文，图才是第一印象。词表从 render.py 引，不复制一份。
    """
    try:
        from render import JARGON, STOCK, WORDY
    except Exception:
        return ["措辞检查没跑：同目录下找不到 render.py，节点文字里的行话无人核对"]
    probs = []
    for g in data.get("groups", []):
        gname = g.get("name", "?")
        for st in g.get("steps", []):
            t = st.get("text", "")
            for w in JARGON:
                if w in t:
                    probs.append(f"「{gname}」节点「{t}」出现行话「{w}」："
                                 f"换成一线业务人员口头会说的词")
            for w in STOCK:
                if w in t:
                    probs.append(f"「{gname}」节点「{t}」出现陈词「{w}」")
            for w in WORDY:
                if w in t:
                    probs.append(f"「{gname}」节点「{t}」出现官腔动词「{w}」：动词直给")
    return probs


def main(argv):
    if len(argv) != 3:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    data = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    out = Path(argv[2])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_svg(data), encoding="utf-8")
    print(str(out))
    probs = check_wording(data)
    if probs:
        print(f"× 节点措辞 {len(probs)} 处问题：", file=sys.stderr)
        for x in probs:
            print(f"  {x}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
