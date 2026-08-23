#!/usr/bin/env python3
"""把手册 Markdown 渲染成 Linear 浅色皮肤的 HTML 预览（零依赖，图片走相对路径）。

用法：
  python3 render.py <文档.md> [输出.html]      # 省略输出则同名 .html

渲染后自动跑格式机检（章序号连续、小节编号对齐、图号图注格式、步骤序号、
图片相对路径且存在、操作小节图文对应），有问题逐条打印并以退出码 2 结束；
机检规则见 check()。

Markdown 约定（与 writing-guide 一致，只认这些）：
  # 标题            册头/篇名；紧随其后的第一段渲染为导语，自动插目录
  ## 一、章节名      二级章节，自动进目录
  ### 1.1 小节名     三级小节，编号渲染为主题色
  #### 问题？        「常见问题」下的一条，渲染成可折叠块
  1. 步骤            有序列表；紧跟其后缩进 4 空格的图片/文字挂进这一条
      ![图 1-1：说明](images/1-1-x.png)
  - 要点             无序列表；「注意事项」标题下的自动渲染成琥珀提示框
  | 表头 | ... |     表格
  ```                代码块
  > 引用
  行内：**粗**、`代码`、[文字](链接)、[待确认] [待补充] 自动高亮
"""

from __future__ import annotations

import html as ihtml
import re
import sys
from pathlib import Path

CSS = """
:root{
  --brand:#5E6AD2; --brand-weak:#EEEFFB; --brand-line:#C9CDF0;
  --bg:#FCFCFD; --card:#FFFFFF; --sunken:#F6F6F8;
  --ink:#0F1015; --ink-2:#484B54; --ink-3:#8A8F98;
  --line:#E9EAEC; --warn:#D4900C; --warn-bg:#FBF3E2;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:15px/1.8 "Inter",-apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  -webkit-font-smoothing:antialiased}
.page{max-width:860px;margin:0 auto;padding:56px 32px 96px}
h1{font-size:26px;font-weight:600;letter-spacing:-.3px;line-height:1.35;margin:0 0 10px}
p.intro{color:var(--ink-3);margin:0 0 40px}
h2{font-size:20px;font-weight:600;letter-spacing:-.2px;line-height:1.35;margin:56px 0 16px}
h3{font-size:15px;font-weight:650;margin:34px 0 12px}
h3 .sn{color:var(--brand);font-weight:650;margin-right:7px}
nav.toc{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:18px 24px;margin:0 0 8px}
nav.toc .toc-title{font-size:12px;font-weight:600;letter-spacing:.5px;text-transform:uppercase;color:var(--ink-3);margin-bottom:10px}
nav.toc ul{margin:0;padding-left:0;list-style:none}
nav.toc li{margin:3px 0}
nav.toc a{color:var(--ink-2);text-decoration:none}
nav.toc a:hover{color:var(--brand)}
ol.steps{padding-left:24px;margin:12px 0}
ol.steps>li{margin:8px 0}
ol.steps>li::marker{color:var(--brand);font-weight:650}
figure{margin:18px 0 26px}
ol.steps figure{margin:12px 0 20px}
figure img{max-width:100%;max-height:620px;width:auto;border:1px solid var(--line);border-radius:8px;
  box-shadow:0 1px 3px rgba(15,16,21,.05);display:block}
figure.tall img{max-height:420px}
figcaption{color:var(--ink-3);font-size:13px;margin-top:9px}
table{width:100%;border-collapse:collapse;font-size:13.5px;margin:14px 0 22px}
th{color:var(--ink-3);font-weight:650;font-size:12px;letter-spacing:.4px;text-align:left;
  border-bottom:1px solid var(--ink-3);padding:0 16px 9px 0}
td{border:0;border-bottom:1px solid var(--line);padding:11px 16px 11px 0;text-align:left;vertical-align:top}
td:first-child{font-weight:650;color:var(--ink-2);white-space:nowrap}
.notice{background:var(--warn-bg);border:1px solid var(--warn-bg);border-left:2px solid var(--warn);
  border-radius:8px;padding:14px 20px;margin:14px 0}
.notice ul{margin:0;padding-left:18px}
.notice li{margin:4px 0}
details.faq{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 20px;margin:10px 0}
details.faq summary{font-weight:650;cursor:pointer;color:var(--ink)}
details.faq summary::marker{color:var(--brand)}
details.faq[open] summary{margin-bottom:8px}
blockquote{margin:12px 0;padding:10px 16px;color:var(--ink-2);border-left:2px solid var(--brand-line);
  background:var(--brand-weak);border-radius:0 8px 8px 0}
code{font-family:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace;font-size:.92em;
  background:var(--sunken);border:1px solid var(--line);border-radius:4px;padding:1px 5px}
pre{background:var(--sunken);border:1px solid var(--line);border-radius:8px;padding:14px 16px;
  overflow-x:auto;font-size:12.5px;line-height:1.7}
pre code{background:none;border:0;padding:0}
.todo{color:var(--warn);font-weight:650}
a{color:var(--brand)}
@media print{body{background:#fff}.page{padding:0}details.faq{break-inside:avoid}figure{break-inside:avoid}}
"""

TOC_JS = """
const toc=document.getElementById('toc');
if(toc){document.querySelectorAll('h2[id]').forEach(h=>{
  const li=document.createElement('li');
  li.innerHTML='<a href="#'+h.id+'">'+h.textContent+'</a>';
  toc.appendChild(li);});
  if(!toc.children.length)toc.closest('nav').remove();}
"""

IMG_RE = re.compile(r"^\s*!\[([^\]]*)\]\(([^)]+)\)\s*$")

CN_NUM = "零一二三四五六七八九"


def cn2int(s: str):
    """中文数字转 int（一 ~ 九十九），非法返回 None。"""
    if not s or any(c not in CN_NUM + "十" for c in s):
        return None
    if s == "十":
        return 10
    if "十" in s:
        a, _, b = s.partition("十")
        return (CN_NUM.index(a) if a else 1) * 10 + (CN_NUM.index(b) if b else 0)
    return CN_NUM.index(s)


def check(md: str, base: Path) -> list:
    """格式机检：章序号、小节编号、图号图注、步骤序号。返回问题列表（空即通过）。

    规则（与 writing-guide 一致）：
      章标题  ## 一、名称        中文序号 + 顿号，顺序连续
      小节    ### 1.2 名称       数字编号，章号对齐、节号从 1 连续
      图注    ![图 2-3：说明]     图号章内从 1 连续，图注非空，文件存在且相对路径
      步骤    1. 2. 3.           每个列表块内从 1 连续
    """
    probs: list = []
    h1_count = 0
    ch = 0            # 当前章序号（int）
    minor = 0         # 当前章内小节号
    fig = 0           # 当前章内图号
    step_expect = 0   # 当前步骤块的下一个期望序号；0 = 不在步骤块里
    in_code = False

    # 操作小节的图文对应：有步骤没配图的小节要报出来（字段说明等纯参考小节除外）
    NO_IMG_OK = ("字段说明", "注意事项", "常见问题", "核对字段", "改动影响")
    sec = None        # (行号, 小节标题) 仅操作小节
    sec_steps = 0
    sec_imgs = 0

    def flush_section():
        nonlocal sec, sec_steps, sec_imgs
        if sec and sec_steps >= 2 and sec_imgs == 0:
            probs.append(f"行{sec[0]}: 操作小节「{sec[1]}」有 {sec_steps} 个步骤但没有一张配图，"
                         f"操作序列至少要有入口图、过程图、结果图（能合并的合并）")
        sec, sec_steps, sec_imgs = None, 0, 0

    for ln, raw in enumerate(md.splitlines(), 1):
        line = raw.rstrip()
        if line.lstrip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue

        m = re.match(r"^(#{1,4})\s+(.*)$", line)
        if m:
            step_expect = 0
            level, title = len(m.group(1)), m.group(2).strip()
            if level in (2, 3):
                flush_section()
            if level == 3 and not any(k in title for k in NO_IMG_OK):
                sec = (ln, title)
            if level == 1:
                h1_count += 1
                if h1_count > 1:
                    probs.append(f"行{ln}: 出现第二个一级标题「{title}」，一册只允许一个")
            elif level == 2:
                mm = re.match(r"^([一二三四五六七八九十]+)、(\S.*)$", title)
                if not mm:
                    probs.append(f"行{ln}: 章标题「{title}」应为「一、名称」格式（中文序号+顿号，顿号后不留空格）")
                    ch += 1
                else:
                    num = cn2int(mm.group(1))
                    if num != ch + 1:
                        probs.append(f"行{ln}: 章序号「{mm.group(1)}、」不连续，期望第 {ch + 1} 章")
                    ch = num if num else ch + 1
                minor = fig = 0
            elif level == 3:
                mm = re.match(r"^(\d+)\.(\d+)\s+(\S.*)$", title)
                if not mm:
                    probs.append(f"行{ln}: 小节标题「{title}」应为「{ch}.{minor + 1} 名称」格式（数字编号+空格）")
                else:
                    if int(mm.group(1)) != ch:
                        probs.append(f"行{ln}: 小节「{title}」章号 {mm.group(1)} 与所在章（第 {ch} 章）不符")
                    if int(mm.group(2)) != minor + 1:
                        probs.append(f"行{ln}: 小节号「{mm.group(1)}.{mm.group(2)}」不连续，期望 {ch}.{minor + 1}")
                    minor = int(mm.group(2))
            continue

        im = IMG_RE.match(line)
        if im:
            sec_imgs += 1
            alt, src = im.group(1), im.group(2)
            mm = re.match(r"^图 (\d+)-(\d+)：(\S.*)$", alt)
            if not mm:
                probs.append(f"行{ln}: 图注「{alt}」应为「图 {ch}-{fig + 1}：说明」格式（半角空格、全角冒号、说明非空）")
            else:
                if int(mm.group(1)) != ch:
                    probs.append(f"行{ln}: 图号「{mm.group(1)}-{mm.group(2)}」章号与所在章（第 {ch} 章）不符")
                if int(mm.group(2)) != fig + 1:
                    probs.append(f"行{ln}: 图号「{mm.group(1)}-{mm.group(2)}」不连续，期望 图 {ch}-{fig + 1}")
                fig = int(mm.group(2)) if mm else fig + 1
            if src.startswith(("/", "http://", "https://")):
                probs.append(f"行{ln}: 图片「{src}」必须用相对路径（images/…）")
            elif not (base / src).exists():
                probs.append(f"行{ln}: 图片文件不存在：{src}")
            continue

        sm = re.match(r"^(\d+)\.\s+", line)
        if sm:
            sec_steps += 1
            if step_expect == 0:
                step_expect = 1
            if int(sm.group(1)) != step_expect:
                probs.append(f"行{ln}: 步骤序号 {sm.group(1)}. 不连续，期望 {step_expect}.")
            step_expect = int(sm.group(1)) + 1
        elif line.strip() and not line.startswith("    "):
            step_expect = 0

    flush_section()
    return probs


def inline(text: str) -> str:
    """行内标记：链接、粗体、行内代码、[待确认] 高亮。"""
    out, codes = text, []

    def stash(m):
        codes.append(m.group(1))
        return f"\x00{len(codes) - 1}\x00"

    out = re.sub(r"`([^`]+)`", stash, out)
    out = ihtml.escape(out, quote=False)
    out = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2" target="_blank">\1</a>', out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"(\[待确认\]|\[待补充\])", r'<span class="todo">\1</span>', out)
    for i, c in enumerate(codes):
        out = out.replace(f"\x00{i}\x00", f"<code>{ihtml.escape(c)}</code>")
    return out


def is_tall(src: str, base: Path) -> bool:
    """竖图（高>宽）限得更矮，避免撑版。读 PNG 头拿宽高，不依赖图像库。"""
    p = base / src
    try:
        data = p.read_bytes()
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            w = int.from_bytes(data[16:20], "big")
            h = int.from_bytes(data[20:24], "big")
            return h > w
    except Exception:
        pass
    return False


def table_html(rows) -> str:
    if len(rows) >= 2 and set("".join(rows[1])) <= set("-: "):
        head, body = rows[0], rows[2:]
    else:
        head, body = rows[0], rows[1:]
    cells = "".join(f"<th>{inline(c)}</th>" for c in head)
    out = [f"<table><thead><tr>{cells}</tr></thead><tbody>"]
    for r in body:
        out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>")
    out.append("</tbody></table>")
    return "".join(out)


def figure_html(alt: str, src: str, base: Path) -> str:
    cls = ' class="tall"' if is_tall(src, base) else ""
    return (f'<figure{cls}><img src="{src}" alt="{ihtml.escape(alt)}">'
            f"<figcaption>{inline(alt)}</figcaption></figure>")


def render(md: str, base: Path) -> str:
    lines = md.splitlines()
    out: list[str] = []
    i, n = 0, len(lines)
    section = ""          # 当前二/三级标题，用来判断注意事项、常见问题
    faq_open = False
    h2_count = 0

    def close_faq():
        nonlocal faq_open
        if faq_open:
            out.append("</details>")
            faq_open = False

    while i < n:
        line = lines[i]

        if not line.strip():
            i += 1
            continue

        # 代码块
        if line.startswith("```"):
            i += 1
            buf = []
            while i < n and not lines[i].startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            out.append("<pre><code>" + ihtml.escape("\n".join(buf)) + "</code></pre>")
            continue

        # 标题
        m = re.match(r"^(#{1,4})\s+(.*)$", line)
        if m:
            level, title = len(m.group(1)), m.group(2).strip()
            if level == 1:
                close_faq()
                out.append(f"<h1>{inline(title)}</h1>")
                i += 1
                while i < n and not lines[i].strip():
                    i += 1
                if i < n and not lines[i].startswith("#"):
                    out.append(f'<p class="intro">{inline(lines[i].strip())}</p>')
                    i += 1
                # 目录不自带编号：章标题已含「一、二、」，再套 ol 会双重序号
                out.append('<nav class="toc"><div class="toc-title">目录</div><ul id="toc"></ul></nav>')
                continue
            if level == 2:
                close_faq()
                section = title
                h2_count += 1
                out.append(f'<h2 id="ch{h2_count}">{inline(title)}</h2>')
            elif level == 3:
                close_faq()
                section = title
                sn = re.match(r"^([\d.]+)\s+(.*)$", title)
                if sn:
                    out.append(f'<h3><span class="sn">{sn.group(1)}</span>{inline(sn.group(2))}</h3>')
                else:
                    out.append(f"<h3>{inline(title)}</h3>")
            else:  # #### 常见问题条目
                close_faq()
                out.append(f'<details class="faq"><summary>{inline(title)}</summary>')
                faq_open = True
            i += 1
            continue

        # 表格
        if line.lstrip().startswith("|"):
            rows = []
            while i < n and lines[i].lstrip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            out.append(table_html(rows))
            continue

        # 有序列表（缩进 4 空格的图片/表格/代码块/段落挂进对应条目）
        if re.match(r"^\d+\.\s+", line):
            out.append('<ol class="steps">')
            while i < n:
                m2 = re.match(r"^\d+\.\s+(.*)$", lines[i])
                if not m2:
                    break
                item = [f"<li>{inline(m2.group(1))}"]
                i += 1
                while i < n:
                    # 空行不代表条目结束：往后看还有缩进内容就继续挂
                    if not lines[i].strip():
                        j = i + 1
                        while j < n and not lines[j].strip():
                            j += 1
                        if j < n and lines[j].startswith("    "):
                            i = j
                            continue
                        i = j
                        break
                    if not lines[i].startswith("    "):
                        break
                    body = lines[i][4:]
                    if body.startswith("```"):
                        i += 1
                        buf = []
                        while i < n and not lines[i].strip().startswith("```"):
                            buf.append(lines[i][4:] if lines[i].startswith("    ") else lines[i])
                            i += 1
                        i += 1
                        item.append("<pre><code>" + ihtml.escape("\n".join(buf)) + "</code></pre>")
                        continue
                    if body.lstrip().startswith("|"):
                        rows = []
                        while i < n and lines[i].strip().startswith("|"):
                            rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                            i += 1
                        item.append(table_html(rows))
                        continue
                    im = IMG_RE.match(lines[i])
                    if im:
                        item.append(figure_html(im.group(1), im.group(2), base))
                    else:
                        item.append(f"<p>{inline(lines[i].strip())}</p>")
                    i += 1
                item.append("</li>")
                out.append("".join(item))
            out.append("</ol>")
            continue

        # 无序列表（注意事项标题下的渲染成提示框）
        if re.match(r"^[-*]\s+", line):
            items = []
            while i < n and re.match(r"^[-*]\s+", lines[i]):
                items.append("<li>" + inline(re.sub(r"^[-*]\s+", "", lines[i])) + "</li>")
                i += 1
            ul = "<ul>" + "".join(items) + "</ul>"
            out.append(f'<div class="notice">{ul}</div>' if "注意事项" in section else ul)
            continue

        # 独立成行的图片
        im = IMG_RE.match(line)
        if im:
            out.append(figure_html(im.group(1), im.group(2), base))
            i += 1
            continue

        # 引用
        if line.startswith(">"):
            buf = []
            while i < n and lines[i].startswith(">"):
                buf.append(lines[i].lstrip("> ").rstrip())
                i += 1
            out.append("<blockquote>" + inline(" ".join(buf)) + "</blockquote>")
            continue

        # 普通段落
        out.append(f"<p>{inline(line.strip())}</p>")
        i += 1

    close_faq()
    title = re.search(r"^#\s+(.*)$", md, re.M)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{ihtml.escape(title.group(1).strip()) if title else "使用手册"}</title>
<style>{CSS}</style>
</head>
<body>
<div class="page">
{chr(10).join(out)}
</div>
<script>{TOC_JS}</script>
</body>
</html>
"""


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_suffix(".html")
    md = src.read_text(encoding="utf-8")
    dst.write_text(render(md, src.parent), encoding="utf-8")
    print(f"已渲染：{dst}")
    probs = check(md, src.parent)
    if probs:
        print(f"× 格式机检 {len(probs)} 处问题：")
        for p in probs:
            print(f"  {p}")
        sys.exit(2)
    print("✓ 格式机检通过（章序号、小节编号、图号图注、步骤序号）")


if __name__ == "__main__":
    main()
