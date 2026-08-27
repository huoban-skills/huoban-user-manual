#!/usr/bin/env python3
"""把手册 Markdown 渲染成 Linear 浅色皮肤的 HTML 预览（零依赖，图片走相对路径）。

用法：
  python3 render.py <文档.md> [输出.html]      # 省略输出则同名 .html

渲染后自动跑格式机检（章序号连续、小节编号对齐、图号图注格式、步骤序号、
图片相对路径且存在、操作小节图文对应、内部行话不入正文、
入口图必须有标注框、标注不出界、图注行与 alt 一致、核对类步骤有图、跨步骤不引图号、
册名合规、总览图在册头、常见问题格式、outline.md 存在、元信息变体、字段表列头、
正文不用 HTML 标签），
有问题逐条打印并以退出码 2 结束；
机检规则见 check()。

Markdown 约定（与 writing-guide 一致，只认这些）：
  # 标题            册头/篇名；紧随其后的第一段渲染为导语，自动插目录
  ## 一、章节名      二级章节，自动进目录
  ### 1.1 小节名     三级小节，编号渲染为主题色
  **1. 问题？**      「常见问题」下的一条（加粗编号行），渲染成可折叠块；旧式 #### 问句兼容
  1. 步骤            有序列表；紧跟其后缩进 4 空格的图片/文字挂进这一条
      ![图 1-1：说明](images/1-1-x.png)
      <small style="color:#8A8F98">图 1-1：说明</small>
                        图注行，与 alt 一致；md 里是灰色小字，HTML 里渲染成 figcaption
  - 要点             无序列表；「注意事项」标题下的自动渲染成琥珀提示框
  | 表头 | ... |     表格
  ```                代码块
  > 引用
  行内：**粗**、`代码`、[文字](链接)、[待确认] [待补充] 自动高亮
"""

from __future__ import annotations

import html as ihtml
import json
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
details.faq summary{font-weight:650;font-size:13.5px;cursor:pointer;color:var(--ink)}
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
# 图片下方的图注行：<small> 灰色小字，md 编辑器里的观感贴近 HTML 的 figcaption
CAP_RE = re.compile(r"^\s*<small[^>]*>\s*图\s?\d+-\d+：.*?</small>\s*$")


def cap_text(line: str) -> str:
    """从图注行里取出纯文字。"""
    return re.sub(r"<[^>]+>", "", line).strip()

# 平台自带的界面词：不在表结构里，但确实是界面上的原名
PLATFORM_UI = {
    "创建", "保存", "取消", "添加数据", "编辑", "删除", "确定", "确认",
    "保存并继续创建", "创建新数据", "+ 创建新数据", "创建视图", "字段设置",
    "分组", "筛选", "排序", "冻结", "全部数据", "我创建的", "导入模版", "导入模板",
    "导入 Excel", "智能识别", "仅更新数据", "数据唯一编号", "展开附加信息",
}


def load_vocab(path):
    """读 vocab.py 产出的系统原词表，合并平台自带界面词。"""
    try:
        d = json.loads(Path(path).read_text())
    except Exception:
        return None
    v = set(PLATFORM_UI)
    for k in ("tables", "fields", "options"):
        v |= {x.strip() for x in d.get(k, []) if isinstance(x, str)}
    return v


CN_NUM = "零一二三四五六七八九"

# 标注框的颜色（当前珊瑚色 + 旧版红），用于机检"图注说要点这里，图上却没画框"
ACCENTS = ((217, 119, 87), (225, 37, 27), (245, 34, 45))

# 标注框那两项要读像素，缺 Pillow 就跑不了。跑不了必须说出来：
# 静默跳过会让"机检通过"变成假话，而机检是这套规范唯一的硬约束。
try:
    from PIL import Image as _probe_pil  # noqa: F401
    PIL_OK = True
except Exception:
    PIL_OK = False


def box_clipped(path: Path):
    """标注框或序号角标是否画出了图外（图片最外圈出现标注色即判定截断）。"""
    try:
        from PIL import Image
    except Exception:
        return None
    try:
        im = Image.open(path).convert("RGB")
        w, h = im.size
        px = im.load()
        edge = 3
        for y in range(h):
            for x in range(w):
                if x >= edge and x < w - edge and y >= edge and y < h - edge:
                    continue
                r, g, b = px[x, y]
                for ar, ag, ab in ACCENTS:
                    if abs(r - ar) <= 28 and abs(g - ag) <= 30 and abs(b - ab) <= 30:
                        return True
        return False
    except Exception:
        return None


def has_box(path: Path):
    """图里有没有标注框颜色。返回 True/False；PIL 缺失或非 PNG 返回 None（跳过检查）。"""
    try:
        from PIL import Image
    except Exception:
        return None
    try:
        # 全尺寸找色：细描边只有 2~3px，缩略图的抗锯齿会把标注色糊没。
        # 用查表掩膜（C 层逐像素）代替 getcolors，大图也是毫秒级。
        from PIL import ImageChops
        im = Image.open(path).convert("RGB")
        bands = im.split()
        for accent in ACCENTS:
            m = None
            for band, target, tol in zip(bands, accent, (28, 30, 30)):
                lut = [255 if abs(v - target) <= tol else 0 for v in range(256)]
                bm = band.point(lut)
                m = bm if m is None else ImageChops.darker(m, bm)
            bb = m.getbbox()
            if not bb:
                continue
            # 标注框是围住控件的矩形描边，尺寸和像素量都远大于界面自身的红色元素
            # （导航栏消息红点、必填红星、橙色状态标签），按尺寸和像素量过滤掉它们
            w2, h2 = bb[2] - bb[0], bb[3] - bb[1]
            if w2 >= 60 and h2 >= 40 and m.histogram()[255] >= 200:
                return True
        return False
    except Exception:
        return None


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
    pil_skipped = 0   # 因缺 Pillow 没查成标注框的图片数
    lines_all = md.splitlines()
    h1_count = 0
    ch = 0            # 当前章序号（int）
    minor = 0         # 当前章内小节号
    fig = 0           # 当前章内图号
    step_expect = 0   # 当前步骤块的下一个期望序号；0 = 不在步骤块里
    in_code = False

    # 操作小节的图文对应：有步骤没配图的小节要报出来（字段说明等纯参考小节豁免）。
    NO_IMG_OK = ("字段说明", "注意事项", "常见问题", "核对字段", "改动影响")
    # 内部行话和元信息不许进正文：走查是 skill 术语，核验日期/本册适用于是说明书腔
    LEAKS = ("走查", "核验日期", "本册适用于", "本手册旨在", "本手册", "适用范围：", "适用对象：")
    # 陈词与例句照抄（user-manual-humanize.md）：AI 腔陈词，以及写作规范例句的特征片段
    STOCK = ("旨在", "致力于", "助力", "赋能", "极大提升", "高效便捷", "一目了然",
             "轻松实现", "值得注意的是", "总而言之", "综上所述", "众所周知")
    # 书面行话与程序员说法：读者口头不会这么说（user-manual-humanize.md「用读者嘴里的词」）
    JARGON = ("底册", "的串", "字符串", "拼接", "序列化", "映射关系",
              "需求行", "清单行", "明细行", "工序行", "数据行")
    ECHO = ("按下面步骤", "取数的档案")
    dup_clauses: dict = {}   # 归一化子句 -> [行号]，抓跨章模板复读
    section_title = ""       # 当前 h3 小节标题，用于常见问题格式检查
    sec = None        # (行号, 小节标题) 仅操作小节
    sec_steps = 0
    sec_imgs = 0
    sec_step_imgs = 0  # 出现在第一条步骤之后的图：节首概览图不算过程图
    sec_entry = None   # 首步是创建/添加类入口动作的行号：入口图和表单图要成对
    last_step = None   # (行号, 正文) 当前步骤块的最后一步，块结束时校验末步带不带结果
    sec_first_img = None  # 本节第一张图的图号
    last_fig = None   # 正文里最近出现的一张图的图号：紧跟其后的续讲可以点它的名
    fig_map = {}       # 图号 -> (行号, 相对路径)
    entry_needs = []   # [(行号, 小节名, 图号)] 入口图待验标注框
    pend = None       # 核对类步骤的行号：点名了多个字段，等本小节后续出现配图
    sec_ui = None     # (行号, 命中词) 小节正文提到页签/按钮等界面元素

    def flush_section():
        nonlocal sec, sec_steps, sec_imgs, sec_step_imgs, pend, sec_ui, sec_entry
        nonlocal sec_first_img, last_fig
        if sec and sec_steps >= 2 and sec_imgs == 0:
            probs.append(f"行{sec[0]}: 操作小节「{sec[1]}」有 {sec_steps} 个步骤但没有一张配图，"
                         f"操作序列要有入口图、过程图、结果图")
        elif sec and sec_steps >= 2 and sec_step_imgs == 0:
            probs.append(f"行{sec[0]}: 操作小节「{sec[1]}」的 {sec_steps} 个步骤之间没有一张过程图，"
                         f"节首的概览图不算；给关键交互补图")
        if sec and sec_entry:
            _num = sec_first_img
            if _num:
                entry_needs.append((sec_entry, sec[1], _num))
        if sec and sec_entry and sec_imgs < 2:
            probs.append(f"行{sec_entry}: 小节「{sec[1]}」首步是新增入口动作，但节内只有 {sec_imgs} 张图："
                         f"入口图（列表页或详情页框出按钮）和表单图要成对，各截各的")
        if pend:
            probs.append(f"行{pend}: 核对类步骤点名了多个字段，但小节内此后没有配图，"
                         f"补图给读者看")
        if sec and sec_ui:
            probs.append(f"行{sec_ui[0]}: 小节「{sec[1]}」的描述提到「{sec_ui[1]}」，但此后到节末"
                         f"没有配图；界面元素写进正文就要能在图里找到，"
                         f"给这一节补图（描述性小节同样适用，节首已有图不豁免）")
        sec, sec_steps, sec_imgs, sec_step_imgs, pend, sec_ui, sec_entry = None, 0, 0, 0, None, None, None
        sec_first_img = None
        last_fig = None   # 换节即失效：续讲只在同一节里紧跟着图才成立

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

            if level == 3:
                section_title = title
            if level == 2:
                section_title = ""
            if level == 3 and not any(k in title for k in NO_IMG_OK):
                sec = (ln, title)
            if level == 1:
                h1_count += 1
                if h1_count > 1:
                    probs.append(f"行{ln}: 出现第二个一级标题「{title}」，一册只允许一个")
                if re.search(r"使用手册|配置手册|[｜|]|v?\d+\.\d+", title):
                    probs.append(f"行{ln}: 册名「{title}」不合规：标题只写模块名，"
                                 f"不追加\"使用手册\"、版本号或分隔符")
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
            if sec_steps > 0:
                sec_step_imgs += 1
            pend = None
            sec_ui = None
            _fn = re.search(r"图 (\d+-\d+)", im.group(1))
            if _fn:
                fig_map[_fn.group(1)] = (ln, im.group(2))
                last_fig = _fn.group(1)
                if sec_first_img is None:
                    sec_first_img = _fn.group(1)
            alt, src = im.group(1), im.group(2)
            nxt = ""
            for k in range(ln, min(ln + 3, len(lines_all))):
                if lines_all[k].strip():
                    nxt = lines_all[k].strip()
                    break
            if ch > 0:
                cap = cap_text(nxt)
                if not CAP_RE.match(nxt):
                    probs.append(f"行{ln}: 图片下面缺图注行；alt 只在 HTML 里显示，"
                                 f"md 里看不到，图片下方要单独写一行"
                                 f"「<small style=\"color:#8A8F98\">{alt}</small>」")
                elif cap != alt:
                    probs.append(f"行{ln}: 图注行「{cap}」和 alt「{alt}」对不上，两处要一致")
            if ch == 0:
                # 第一章之前只有册头总览流程图，图注不编图号，只查路径和文件
                if src.startswith(("/", "http://", "https://")):
                    probs.append(f"行{ln}: 图片「{src}」必须用相对路径（images/…）")
                elif not (base / src).exists():
                    probs.append(f"行{ln}: 图片文件不存在：{src}")
                continue
            if re.search(r"总览|全流程", src) and src.lower().endswith(".svg"):
                probs.append(f"行{ln}: 总览流程图「{src}」出现在第 {ch} 章里；"
                             f"它该放在册头模块介绍后面（第一章之前），图注不编图号")
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
            elif src.lower().endswith(".png"):
                if not PIL_OK:
                    pil_skipped += 1
                else:
                    if re.search(r"入口|按钮|点[「击开]", alt) and has_box(base / src) is False:
                        probs.append(f"行{ln}: 图注「{alt}」说的是入口/点击，但图上没有画标注框")
                    if box_clipped(base / src):
                        probs.append(f"行{ln}: 图「{src}」的标注框或序号角标画到了图外被截断，"
                                     f"重新框选让它整个落在画面内")
            continue

        # 界面元素落图检查：描述行（非步骤行）提到界面元素记一笔账，
        # 之后出现配图即销账；图注行（<small）不算正文提及。
        # 步骤行不记：步骤序列的图文对应由过程图检查负责。
        if sec and not line.lstrip().startswith("<small"):
            is_step = bool(re.match(r"^\s*\d+\.\s", line))
            if sec_ui is None and sec_imgs == 0 and not is_step and not line.lstrip().startswith(("|", ">", "#")):
                ui = re.search(r"页签|按钮|下拉|弹窗|点开?「[^」]+」", line)
                if ui:
                    sec_ui = (ln, ui.group(0))
            # 跨步骤引用图号：一张图只带一套标注框，框是照着它所在那一步画的，
            # 引到别处框就对不上；增删图还会让图号顺移，引用变断链。各步骤各截各的图。
            # 紧邻上一张图的续讲不算（同一张图分两段讲，框就是照着它画的）。
            for _r in re.finditer(r"图\s?(\d+-\d+)", line):
                if _r.group(1) != last_fig:
                    probs.append(f"行{ln}: 正文引用了别处的「图 {_r.group(1)}」"
                                 f"（本节最近一张图是 {last_fig or '无'}）；"
                                 f"一张图只带一套标注框，引到别处框就对不上这一步。"
                                 f"给这一步单独截图、单独画框，同一个页面被两步用到就截两张")

        if line.lstrip().startswith("|"):
            cells = [c.strip().strip("*") for c in line.strip().strip("|").split("|")]
            if cells and cells[0] == "字段" and cells != ["字段", "字段说明", "填写说明"]:
                probs.append(f"行{ln}: 字段表列头是「{' | '.join(cells)}」，"
                             f"规范是「字段 | 字段说明 | 填写说明」（字段说明讲业务含义，填写说明写必填/选填/自动计算）")

        if "常见问题" in section_title and re.match(r"^\*?\*?[QA][：:]", line.strip()):
            probs.append(f"行{ln}: 常见问题不用 Q/A 前缀，问题写成加粗编号行「**1. 问题？**」，答案直接跟在下面")

        htag = re.match(r"^\s*</?(h[1-6]|ol|ul|li|p|div|br)\b", line)
        if htag:
            probs.append(f"行{ln}: 正文出现 HTML 标签 <{htag.group(1)}>；"
                         f"标题用 ## / ###、步骤用 1. 2. 3.、要点用 -，只有图注行用 <small>")

        for w in LEAKS:
            if w in line:
                probs.append(f"行{ln}: 正文出现「{w}」：内部行话和元信息不进手册（环境缺陷、走查情况记 notes.md）")

        for w in STOCK:
            if w in line:
                probs.append(f"行{ln}: 正文出现陈词「{w}」：价值用具体业务结果说，见 user-manual-humanize.md")
        for w in JARGON:
            if w in line:
                probs.append(f"行{ln}: 正文出现行话「{w}」：换成一线业务人员口头会说的词，"
                             f"见 user-manual-humanize.md「用读者嘴里的词」")
        for w in ECHO:
            if w in line:
                probs.append(f"行{ln}: 正文出现「{w}」：这是写作规范例句的措辞，例句只示意结构，换自己的说法")

        lb = re.match(r"^\s*\*{0,2}(进入路径|进入方式|入口|访问路径)\*{0,2}[:：]", line)
        if lb:
            probs.append(f"行{ln}: 「{lb.group(1)}：」标签行是说明书腔，且和第一个步骤重复；"
                         f"菜单路径只写在它对应的步骤里")

        # 模板复读：同一子句（去掉界面名和行内代码后）在全册出现 3 次以上
        s = line.strip()
        if s and not s.startswith(("|", ">", "<small")):
            text = re.sub(r"`[^`]*`", "", s).replace("**", "")
            text = re.sub(r"^(\d+\.|-)\s+", "", text)
            for cl in re.split(r"[。；！？，：]", text):
                cl = cl.strip()
                if len(cl) >= 6 and "「" not in cl:
                    dup_clauses.setdefault(cl, []).append(ln)

        if pend and re.search(r"[如同见]图\s?\d+-\d+", line):
            pend = None

        # 步骤块断开时校验末步：只写收尾动作、不交代系统反馈的要报
        if last_step and not re.match(r"^\s*\d+\.\s", line) and line.strip() and not line.startswith(" "):
            ln2, txt = last_step
            # 剥掉收尾动作和标点后几乎不剩内容 = 只写了动作没交代结果
            rest = re.sub(r"点?「?(保存|提交|确定|完成|确认)」?", "", txt)
            rest = re.sub(r"[。，、；：\s]", "", rest)
            if re.search(r"保存|提交|确定|完成|确认", txt) and len(rest) < 4:
                probs.append(f"行{ln2}: 末步「{txt}」只有收尾动作没有结果，"
                             f"读者不知道点完发生什么；把它并进上一步并补一句系统反馈"
                             f"（见 writing-guide「步骤写法」）")
            last_step = None

        sm = re.match(r"^(\d+)\.\s+(.*)$", line)
        if sm:
            sec_steps += 1
            stext = sm.group(2)
            last_step = (ln, stext.strip())
            if sec_steps == 1 and re.search(r"点[^。]*「[^」]*(创建|添加数据|新建)[^」]*」", stext):
                sec_entry = ln
            if (stext.count("、") >= 1
                    and re.search(r"查看|核对|确认|检查", stext)
                    and "无误" not in stext):
                pend = ln
            if step_expect == 0:
                step_expect = 1
            if int(sm.group(1)) != step_expect:
                probs.append(f"行{ln}: 步骤序号 {sm.group(1)}. 不连续，期望 {step_expect}.")
            step_expect = int(sm.group(1)) + 1
        elif line.strip() and not line.startswith("    "):
            step_expect = 0

    flush_section()

    for _ln, _title, _num in entry_needs:
        _hit = fig_map.get(_num)
        if not _hit:
            continue
        _src = _hit[1]
        if PIL_OK and _src.lower().endswith(".png") and has_box(base / _src) is False:
            probs.append(f"行{_ln}: 小节「{_title}」的入口图（图 {_num}）上没有标注框，"
                         f"入口图要把读者该点的按钮框出来")
    for cl, lns in dup_clauses.items():
        if len(lns) >= 3:
            probs.append(f"行{'、'.join(map(str, lns))}: 「{cl}」出现 {len(lns)} 次，"
                         f"同一措辞跨章盖章是模板复读，同类信息换说法（见 user-manual-humanize.md）")
    if pil_skipped:
        probs.append(f"环境缺 Pillow：{pil_skipped} 张图的标注框检查没跑（画没画框、框有没有出界这两项）。"
                     f"这一轮的结果不含这两项，装上再跑一次：pip install pillow")
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
                        # 图注行紧跟在图片下面（md 里也能看到），吸收成 figcaption 不重复
                        j = i + 1
                        while j < n and not lines[j].strip():
                            j += 1
                        if j < n and CAP_RE.match(lines[j].strip()):
                            i = j
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

        # 常见问题里的加粗编号问句：**1. 问题？** 渲染成折叠块
        fm = re.match(r"^\*\*(\d+)[.、]\s*(.+?)\*\*$", line.strip())
        if fm and "常见问题" in section:
            close_faq()
            out.append(f'<details class="faq"><summary>{inline(fm.group(1) + ". " + fm.group(2))}</summary>')
            faq_open = True
            i += 1
            continue

        # 独立成行的图片
        im = IMG_RE.match(line)
        if im:
            out.append(figure_html(im.group(1), im.group(2), base))
            i += 1
            while i < n and not lines[i].strip():
                i += 1
            if i < n and CAP_RE.match(lines[i].strip()):
                i += 1          # 图注行已渲染进 figcaption
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



def check_vocab(md: str, vocab_path) -> list:
    """核对正文里当界面元素用的「X」是不是系统原词（vocab.py 产出的词表）。

    只查语境明确的：填「X」/选「X」/点「X」/「X」必填/「X」会变空。
    举例值、业务说法不在此列，不查。
    """
    if not vocab_path:
        return ["界面名词校验没跑：未传 --vocab <vocab.json>，「」里的字段名是否生造无人核对"]
    vocab = load_vocab(vocab_path)
    if vocab is None:
        return [f"界面名词校验没跑：读不到词表 {vocab_path}"]
    probs, seen = [], set()
    pats = [
        r"[填选点勾]开?[击选]?「([^」]{1,20})」",
        r"「([^」]{1,20})」(?=必填|是必填|会变空|自动生成|不用填)",
    ]
    in_code = False
    for ln, line in enumerate(md.splitlines(), 1):
        if line.lstrip().startswith("```"):
            in_code = not in_code
            continue
        if in_code or line.lstrip().startswith("<small"):
            continue
        for pat in pats:
            for m in re.finditer(pat, line):
                w = m.group(1).strip()
                if w in vocab or w in seen:
                    continue
                seen.add(w)
                probs.append(f"行{ln}: 「{w}」不在系统原词表里 → 是举例值就放着，"
                             f"是字段/按钮名就核对界面改成原名")
    return probs


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_suffix(".html")
    vocab_path = None
    argv = sys.argv[1:]
    if "--vocab" in argv:
        i = argv.index("--vocab")
        vocab_path = argv[i + 1] if i + 1 < len(argv) else None
        argv = argv[:i] + argv[i + 2:]
        src = Path(argv[0])
        dst = Path(argv[1]) if len(argv) > 1 else src.with_suffix(".html")
    md = src.read_text(encoding="utf-8")
    dst.write_text(render(md, src.parent), encoding="utf-8")
    print(f"已渲染：{dst}")
    probs = check(md, src.parent)
    vocab_notes = check_vocab(md, vocab_path)
    if not (src.parent / "outline.md").exists():
        probs.append("产出目录缺 outline.md：骨架（表、页面、章节、数据口径）没有留痕，阶段一可能被跳过")
    if vocab_notes:
        print(f"⚠ 界面名词待核 {len(vocab_notes)} 处（机器分不清字段名和举例值，逐条人工确认）：")
        for n in vocab_notes:
            print(f"  {n}")
    if probs:
        print(f"× 格式机检 {len(probs)} 处问题：")
        for p in probs:
            print(f"  {p}")
        sys.exit(2)
    print("✓ 格式机检通过（章序号、小节编号、图号图注、步骤序号）")


if __name__ == "__main__":
    main()
