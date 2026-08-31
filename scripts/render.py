#!/usr/bin/env python3
"""把手册 Markdown 渲染成 Linear 浅色皮肤的 HTML 预览（零依赖，图片走相对路径）。

用法：
  python3 render.py <文档.md> [输出.html]      # 省略输出则同名 .html

渲染后自动跑格式机检（章序号连续、小节编号对齐、图号图注格式、步骤序号、
图片相对路径且存在、操作小节图文对应、内部行话不入正文、
入口图必须有标注框、标注不出界、图注行与 alt 一致、核对类步骤有图、跨步骤不引图号、
册名合规、总览图在册头、业务流程册必须有册头总览图、正文不用围栏代码块、
常见问题格式、outline.md 存在、元信息变体、字段表列头、
正文不用 HTML 标签、章开场句式（名词化定义、疑问代词排比、泛指「你」、主语堆叠）、官腔动词），
再跑截图证据语义审计（每张 PNG 有 shot 落盘的 .meta.json、正文界面词有截图证据背书、
hac 内部名不冒充界面词、框住的元素正文都提到、多框角标顺序＝正文顺序、
notes.md 点位记到每张入册图），
以及覆盖度门禁（outline 章节清单细到操作小节且正文逐一存在、常见问题小节不许空壳、
改版任务传 --baseline <旧版.md> 对照小节集合和常见问题条数，缩水即报），
有问题逐条打印并以退出码 2 结束；
格式规则见 check()，证据规则见 check_evidence() / check_vocab()，
覆盖度规则见 check_outline() / check_baseline()。

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
    # 审批流办理界面的标准按钮：平台自带，不属于任何一张表，采集词表里采不到
    "办理", "去办理", "同意", "不同意", "转交", "加签", "撤回", "催办",
    "保存并重新发起审批", "仅保存数据", "我知道了",
}


# —— 措辞词表：本文件是唯一事实源，flow.py 复用同一份查流程图节点 ——
# 内部行话和元信息不许进正文：走查是 skill 术语，核验日期/本册适用于是说明书腔。
# 「以下操作对应/对应工作区」是实测踩过的绕法——机检拦了「本手册对应」，
# 模型换个触发词接着写，所以变体也逐个钉死。
LEAKS = ("走查", "核验日期", "本册适用于", "本手册旨在", "本手册", "适用范围：", "适用对象：",
         "以下操作对应", "对应工作区", "工作区 ID", "工作区ID", "采集时间")
# 陈词与例句照抄（user-manual-humanize.md）：AI 腔陈词，以及写作规范例句的特征片段
STOCK = ("旨在", "致力于", "助力", "赋能", "极大提升", "高效便捷", "一目了然",
         "轻松实现", "值得注意的是", "总而言之", "综上所述", "众所周知")
# 书面行话与程序员说法：读者口头不会这么说（user-manual-humanize.md「用读者嘴里的词」）
JARGON = ("底册", "的串", "字符串", "拼接", "序列化", "映射关系",
          "需求行", "清单行", "明细行", "工序行", "数据行", "驱动", "条记录",
          "拉取", "回写", "载入")
ECHO = ("按下面步骤", "取数的档案")
# 官腔动词：动词直给（user-manual-humanize.md「动词直给」）。
# 「作为」不整词封禁——"作为默认单价带出"是正当用法，只拦「作为……角色」句式。
WORDY = ("进行", "实现", "予以", "加以", "用于")


def load_vocab(path):
    """读 vocab.py 产出的系统原词表，合并平台自带界面词。

    返回 (界面词集合, hac 内部名集合)。hac_names 是自动化等配置的内部名称，
    界面上未必这么叫，绝不并进界面词集合——它只用来拦「内部名当界面词写进正文」。
    """
    try:
        d = json.loads(Path(path).read_text())
    except Exception:
        return None, set()
    v = set(PLATFORM_UI)
    for k in ("tables", "fields", "options"):
        v |= {x.strip() for x in d.get(k, []) if isinstance(x, str)}
    hac = {x.strip() for x in d.get("hac_names", []) if isinstance(x, str)} - v
    return v, hac


def load_evidence(base: Path):
    """读 browser.py shot 落盘的截图证据（images/*.meta.json）。

    返回 (metas, ui)：metas 按图片文件名索引；ui 是所有证据里出现过的界面原文
    （被框元素的文字 + 截图当时页面可见交互元素的文字），是「界面上真的这么写」
    的机器记录，正文界面词审计以它为准。
    """
    metas, ui = {}, set()
    img_dir = base / "images"
    if img_dir.is_dir():
        for p in sorted(img_dir.glob("*.meta.json")):
            try:
                m = json.loads(p.read_text())
            except Exception:
                continue
            metas[p.name[: -len(".meta.json")]] = m
            ui |= {t.strip() for t in m.get("ui_texts", [])
                   if isinstance(t, str) and t.strip()}
            for tg in m.get("targets", []):
                t = (tg.get("ui_text") or "").strip()
                if t:
                    ui.add(t)
    return metas, ui


def check_evidence(md: str, base: Path, metas: dict) -> list:
    """截图证据审计：逐图核对 .meta.json 与正文的一致性。

    - 正文引用的每张 PNG 都要有证据文件（shot 自动落盘；没有 = 旧方式截的，重截）
    - 图上框住的元素原文必须在本节正文出现（框 ↔ 正文一一对应）
    - 多框的角标顺序要与正文提及顺序一致（角标顺序＝操作顺序）
    - notes.md 点位清单要记到每张入册截图
    """
    probs: list = []
    lines = md.splitlines()
    # 切块：每个标题（#/##/###）到下一个标题算一节，图归它所在的节
    sections = []          # (标题, 正文行列表, [(行号, src, alt)])
    cur_title, cur_txt, cur_imgs = "", [], []

    def flush():
        nonlocal cur_title, cur_txt, cur_imgs
        if cur_txt or cur_imgs:
            sections.append((cur_title, cur_txt, cur_imgs))
        cur_title, cur_txt, cur_imgs = "", [], []

    in_code = False
    for ln, raw in enumerate(lines, 1):
        if raw.lstrip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        m = re.match(r"^(#{1,3})\s+(.*)$", raw)
        if m:
            flush()
            cur_title = m.group(2).strip()
            continue
        im = IMG_RE.match(raw)
        if im:
            cur_imgs.append((ln, im.group(2), im.group(1)))
            continue
        if not raw.lstrip().startswith("<small"):
            cur_txt.append((ln, raw))
    flush()

    # 新增类按钮名逐表不同（这张表是「添加数据」，那张表是「创建」），全局白名单
    # 分不出来；只要本节有截图证据，就要求正文写的新增按钮出现在本节证据里。
    NEW_BTNS = ("添加数据", "创建新数据", "创建", "新建")
    referenced: list = []
    for title, txt, imgs in sections:
        body = re.sub(r"\s+", "", "\n".join(raw for _, raw in txt))
        sec_ui: set = set()
        for _, src, _ in imgs:
            m = metas.get(Path(src).name)
            if m:
                sec_ui |= {t for t in m.get("ui_texts", []) if isinstance(t, str)}
                sec_ui |= {(tg.get("ui_text") or "").strip() for tg in m.get("targets", [])}
        if sec_ui:
            for ln, raw in txt:
                for mm in re.finditer(r"点[击开]?[^。，；：「」]{0,6}「(%s)」" % "|".join(NEW_BTNS), raw):
                    w = mm.group(1)
                    if w in sec_ui:
                        continue
                    actual = [b for b in NEW_BTNS if b != w and b in sec_ui]
                    probs.append(f"行{ln}: 正文写点「{w}」，但本节截图证据里的界面上没有这个按钮"
                                 + (f"（证据里是「{actual[0]}」）" if actual else "")
                                 + "；不同表的新增按钮名不同，以本节截图当时的界面原词为准")
        for ln, src, alt in imgs:
            name = Path(src).name
            if src.lower().endswith(".png") and src.startswith("images/"):
                referenced.append(name)
            meta = metas.get(name)
            if meta is None:
                if metas and src.lower().endswith(".png") and src.startswith("images/"):
                    probs.append(f"行{ln}: 图「{name}」没有同名 .meta.json 证据文件，"
                                 f"界面原文没有留底；用 scripts/browser.py shot 重截"
                                 f"（不要手写证据文件，它是机器记录）")
                continue
            # 只核按钮/字段量级的短文字；大区域框的 innerText 是整块内容，不参与比对
            tgs = [(t.get("order", i + 1), (t.get("ui_text") or "").strip())
                   for i, t in enumerate(meta.get("targets", []))]
            tgs = [(o, w) for o, w in tgs if 1 <= len(w) <= 12]
            # body 已去全部空白，目标词也去掉再比对，否则「导入 Excel」这类带空格的词永远失配
            found = [(o, w, body.find(re.sub(r"\s+", "", w))) for o, w in tgs]
            for o, w, p in found:
                if p < 0:
                    probs.append(f"行{ln}: 图「{name}」框住了「{w}」，但本节正文没提到它；"
                                 f"框 ↔ 正文要一一对应：正文写清这一步怎么用它，或者别框它")
            seq = sorted([(o, w, p) for o, w, p in found if p >= 0])
            if len(seq) >= 2 and any(seq[i][2] > seq[i + 1][2] for i in range(len(seq) - 1)):
                probs.append(f"行{ln}: 图「{name}」的角标顺序和正文顺序对不上"
                             f"（图上依次是 {' → '.join(w for _, w, _ in seq)}，正文提及顺序不同）；"
                             f"角标顺序＝操作顺序，按正文步骤顺序重排 --highlight 的选择器重截")

    if referenced and not metas:
        probs.append("images/ 下没有任何 .meta.json 截图证据：正文写的按钮名、字段名无从核对。"
                     "所有配图用 scripts/browser.py shot 重截即可自动补齐"
                     "（旧方式截的图没有界面原文留底，重渲染停在这里是预期行为）")

    if referenced:
        notes_p = base / "notes.md"
        notes = notes_p.read_text(encoding="utf-8", errors="ignore") if notes_p.exists() else ""
        if not notes:
            probs.append("产出目录缺 notes.md：点位清单没有留痕，走查可能被跳过"
                         "（格式见 walkthrough-guide 第七节）")
        else:
            miss = [n for n in dict.fromkeys(referenced) if n not in notes]
            if miss:
                probs.append(f"notes.md 的点位清单没记这 {len(miss)} 张入册截图："
                             f"{'、'.join(miss[:6])}{' 等' if len(miss) > 6 else ''}；"
                             f"每张图都要有点位条目（页面、按钮原文、点击结果、截图名，"
                             f"见 walkthrough-guide 第七节），打勾不算记录")
    return probs


CN_NUM = "零一二三四五六七八九"

# 看板类章节：整屏都是指标和图表，框不出「该点哪里」，免于强制画框
DASHBOARD_CH = re.compile(r"工作台|看板|大屏")

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
    ch_title = ""     # 当前章标题：看板类章节的图免框，操作流程章节的图一律要框
    step_expect = 0   # 当前步骤块的下一个期望序号；0 = 不在步骤块里
    in_code = False
    head_svg = False  # 册头（第一章之前）有没有 SVG 总览流程图

    # 操作小节的图文对应：有步骤没配图的小节要报出来（字段说明等纯参考小节豁免）。
    NO_IMG_OK = ("字段说明", "注意事项", "常见问题", "核对字段", "改动影响")
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
    open_pending = False  # 章标题刚过、还没遇到本章开场第一段
    faq_open = None   # (行号, 标题) 当前在常见问题小节里
    faq_entries = 0   # 该小节已见的问答条数

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
            if in_code:
                # 手册读者是业务人员，正文没有围栏代码块的正当用途。
                # 实测的漏法：册头该用 flow.py 出 SVG，改成在代码块里敲 ASCII 流程图，
                # 图注和图号检查都绕过去了，交付前谁也没发现。
                probs.append(f"行{ln}: 正文出现围栏代码块；手册里不放代码。"
                             f"册头全流程图用 flow.py 出 SVG（flow.json → images/0-全流程总览.svg），"
                             f"短流程用文本箭头 → 直接写进正文")
            continue
        if in_code:
            continue

        m = re.match(r"^(#{1,4})\s+(.*)$", line)
        if m:
            step_expect = 0
            level, title = len(m.group(1)), m.group(2).strip()
            # 常见问题小节收尾：只有标题没有一条问答，是"删条目消检查面"的形态
            if faq_open and faq_entries == 0 and level <= 3:
                probs.append(f"行{faq_open[0]}: 「{faq_open[1]}」小节没有一条问答；"
                             f"常见问题至少一条加粗编号问句（**1. 问题？**），"
                             f"暂无积累就标 [待补充]，不许留空壳过检")
            if level <= 3:
                faq_open = None
            if level in (2, 3):
                flush_section()

            if level == 3:
                section_title = title
                if "常见问题" in title:
                    faq_open, faq_entries = (ln, title), 0
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
                ch_title = mm.group(2) if mm else title
                open_pending = True
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
                if src.lower().endswith(".svg"):
                    head_svg = True
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
                    # 看板类章节（工作台、看板、大屏）通篇是图表和指标，整屏即内容，免框；
                    # 其余章节的图都落在操作步骤里，读者要照着找元素，一律要框。
                    if has_box(base / src) is False and not DASHBOARD_CH.search(ch_title):
                        probs.append(f"行{ln}: 图「{src}」没有画标注框；"
                                     f"操作流程章节的图都要把这一步点名的按钮、字段、区域框出来"
                                     f"（只有工作台、看板、大屏这类章节免框）")
                    if box_clipped(base / src):
                        probs.append(f"行{ln}: 图「{src}」的标注框或序号角标画到了图外被截断，"
                                     f"重新框选让它整个落在画面内")
            continue

        # —— 章开场句式检查：册头导语各段 + 每章标题后的第一段 ——
        # 生硬集中在开场那几句：名词化定义、疑问代词排比、泛指的「你」、主语堆叠。
        # 正例见 writing-guide「场景介绍写法」、user-manual-humanize「指代补全」。
        _s0 = line.strip()
        _plain = (_s0 and not _s0.startswith(("|", ">", "<small", "-", "*", "!", "#"))
                  and not re.match(r"^\d+\.\s", _s0) and not line.startswith("    "))
        if _plain and (open_pending or (ch == 0 and h1_count == 1)):
            open_pending = False
            _first = re.split(r"[。！？]", _s0)[0]
            _clause = re.split(r"[，。：]", _s0)[0]
            if re.search(r"记的是|指的是|管的是|负责的是", _first) or re.search(r"的(来源|地方|档案|前提)$", _clause):
                probs.append(f"行{ln}: 章开场拿名词化定义起头（「记的是 / 管的是 / 是……的来源」）；"
                             f"用读者的处境或动作起头，动词说清它管什么用"
                             f"（见 writing-guide「场景介绍写法」）")
            # 总起冒号句式：「XX 管的是…的全过程：」「这条线上就三件事：」——修辞冒号
            # 不进开篇（humanize 第 17 条），实测它是各册开头跨册盖章的重灾区。
            # 只拦抽象总起词收尾的，真枚举（"五张表：商品、仓库…"）不受影响。
            _m17 = re.match(r"^[^。！？]{4,30}(全?过程|全?流程|[一几两三]件事|主线|闭环|一整条线)：(.{0,16})", _s0)
            if _m17 and "、" not in _m17.group(2):
                probs.append(f"行{ln}: 开场用「短句总起：展开」的修辞冒号（"
                             f"「…的全过程：」这类）；开篇平铺直叙，直接从业务场景讲起，"
                             f"冒号只留给真枚举（见 user-manual-humanize.md 第 17 条）")
            if len(re.findall(r"[什谁][么买]?的", _s0)) >= 2:
                probs.append(f"行{ln}: 章开场堆疑问代词排比（什么的/谁的/向谁买的）；"
                             f"视角统一成这个角色在业务里干什么"
                             f"（见 user-manual-humanize.md「句式不套路」）")
            if "你" in _s0:
                probs.append(f"行{ln}: 章开场用「你」泛指读者；主语写具体角色（销售、采购、仓管、财务）"
                             f"或具体的物，公司层面的往来写「公司」"
                             f"（见 user-manual-humanize.md「指代补全」）")
            if _clause.count("「") >= 3:
                probs.append(f"行{ln}: 章开场首句把一长串「」名词堆在主语位，读者读到句尾才知道在说什么；"
                             f"先一句给结论，再展开列举")

        # 界面元素落图检查：描述行（非步骤行）提到界面元素记一笔账，
        # 之后出现配图即销账；图注行（<small）不算正文提及。
        # 步骤行不记：步骤序列的图文对应由过程图检查负责。
        if sec and not line.lstrip().startswith("<small"):
            is_step = bool(re.match(r"^\s*\d+\.\s", line))
            if sec_ui is None and sec_imgs == 0 and not is_step and not line.lstrip().startswith(("|", ">", "#")):
                ui = re.search(r"页签|按钮|下拉|弹窗|点开?「[^」]+」|行[内末][^。，」]{0,4}选「[^」]+」", line)
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

        # 操作列的能力描述必须用「」引界面原词：实测的编造重灾区正是
        # "列表右侧还可以查看详情、打开核销"这种不带引号的散文——引号词归证据审计管，
        # 不引号就绕过了机检。把它逼进引号里。
        for _sent in re.split(r"[。；]", line):
            if (re.search(r"行内|行末|列表右侧|操作列", _sent) and "「" not in _sent
                    and re.search(r"详情|审批|核销|收款|付款|对账|编辑|删除|发起|查看|打开", _sent)):
                probs.append(f"行{ln}: 「{_sent.strip()[:24]}…」描述行内/操作列的能力却没有用「」引界面原词；"
                             f"按钮叫什么以截图证据为准，逐词用「」引出来（没亲眼见过的按钮不写）")
                break

        if faq_open and re.match(r"^\s*(\*\*\d+[.、]|####\s|\[待补充\])", line):
            faq_entries += 1

        if "常见问题" in section_title and re.match(r"^\*?\*?[QA][：:]", line.strip()):
            probs.append(f"行{ln}: 常见问题不用 Q/A 前缀，问题写成加粗编号行「**1. 问题？**」，答案直接跟在下面")

        htag = re.match(r"^\s*</?(h[1-6]|ol|ul|li|p|div|br)\b", line)
        if htag:
            probs.append(f"行{ln}: 正文出现 HTML 标签 <{htag.group(1)}>；"
                         f"标题用 ## / ###、步骤用 1. 2. 3.、要点用 -，只有图注行用 <small>")

        for w in LEAKS:
            if w in line:
                probs.append(f"行{ln}: 正文出现「{w}」：内部行话和元信息不进手册（环境缺陷、走查情况记 notes.md）")

        # 实施元信息的数字形态：工作区/表 ID（13 位以上长数字）、应用版本号。
        # 单号示例（DD20260810001）不足 13 位数字连排，不误伤。
        if re.search(r"\d{13,}", line):
            probs.append(f"行{ln}: 正文出现长数字 ID（工作区/表 ID 一类）；实施元信息记 notes.md，不进手册")
        if re.search(r"\bv\d+\.\d+", line):
            probs.append(f"行{ln}: 正文出现应用版本号（v1.6.0 这类）；版本、环境信息记 notes.md，不进手册")

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
        for w in WORDY:
            if w in line:
                probs.append(f"行{ln}: 正文出现官腔动词「{w}」：动词直给——"
                             f"「对数据进行核对」就是「核对数据」，「无法实现余额管理」写成读者看得见的现象"
                             f"（见 user-manual-humanize.md「动词直给」）")
        if re.search(r"作为.{0,8}角色", line):
            probs.append(f"行{ln}: 正文出现「作为……角色」句式：是就写「是」，有就写「有」，"
                         f"见 user-manual-humanize.md「动词直给」")

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
    if faq_open and faq_entries == 0:
        probs.append(f"行{faq_open[0]}: 「{faq_open[1]}」小节没有一条问答；"
                     f"常见问题至少一条加粗编号问句（**1. 问题？**），"
                     f"暂无积累就标 [待补充]，不许留空壳过检")

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
    # 业务流程册的册头固定配一张 flow.py 出的全流程图。骨架里自己写了「业务流程型」
    # 却没出图，是实测漏过的一种：正文照样通过其余全部检查。
    _outline = base / "outline.md"
    if _outline.exists() and not head_svg:
        _o = _outline.read_text(encoding="utf-8", errors="ignore")
        # 只认「模块类型：」那一行的取值。整篇搜「业务流程」会被正文里的
        # 「归各业务流程册」这类说明命中（基础资料册实测误伤）。
        _m = re.search(r"^\s*[-*]?\s*模块类型[：:]\s*(.+)$", _o, re.M)
        if _m and "业务流程" in _m.group(1):
            probs.append("outline.md 写的是业务流程型模块，但册头没有 SVG 全流程图。"
                         "写 flow.json 后跑 flow.py 出图："
                         "python3 scripts/flow.py flow.json images/0-全流程总览.svg，"
                         "图放在模块介绍后面、第一章之前")
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



def check_vocab(md: str, vocab_path, ui: set, has_evidence: bool):
    """核对正文里当界面元素用的「X」是不是系统原词。

    返回 (硬错误列表, 待人工核清单)。事实来源分两层：
    - 界面层：截图证据里的原文（ui）+ 表/字段/选项词表 + 平台自带词——命中即通过
    - hac 层：自动化等配置的内部名（hac_names）——点击语境里命中它而界面层没有，
      是「把内部名当界面词」（实测踩过：配置叫「收款核销」，界面按钮是「核销应收」），
      直接报错，不给人工放行的余地
    只查语境明确的：填「X」/选「X」/点「X」/「X」必填/「X」会变空。举例值不查。
    """
    if not vocab_path:
        return [], ["界面名词校验没跑：未传 --vocab <vocab.json>，「」里的字段名是否生造无人核对"]
    vocab, hac_names = load_vocab(vocab_path)
    if vocab is None:
        return [], [f"界面名词校验没跑：读不到词表 {vocab_path}"]
    allow = vocab | ui
    probs, notes, seen = [], [], set()
    # 点击语境：点/勾「X」，以及"行内选「X」""右上角选「X」"这类位置词+选——
    # 后者实测里都是按钮点击，不是表单选项。动词和「」之间允许短方位词
    # （"点行末的「核销应收」""点右上角「添加数据」"），贴死会整类漏检。
    click_pat = re.compile(r"(?:[点勾]开?[击选]?[^。，；：「」]{0,6}|(?:行内|行末|右上角|列表右侧|操作列)[^。，」]{0,4}选)「([^」]{1,20})」")
    pats = [
        r"[填选点勾]开?[击选]?[^。，；：「」]{0,6}「([^」]{1,20})」",
        r"「([^」]{1,20})」(?=必填|是必填|会变空|自动生成|不用填)",
    ]
    in_code = False
    for ln, line in enumerate(md.splitlines(), 1):
        if line.lstrip().startswith("```"):
            in_code = not in_code
            continue
        if in_code or line.lstrip().startswith("<small"):
            continue
        clicks = {m.group(1).strip() for m in click_pat.finditer(line)}
        for pat in pats:
            for m in re.finditer(pat, line):
                w = m.group(1).strip()
                if w in allow or w in seen:
                    continue
                seen.add(w)
                if w in hac_names:
                    probs.append(f"行{ln}: 「{w}」是 hac 配置里的内部名称，没有出现在任何"
                                 f"截图证据和界面词表里；界面上未必叫这个名"
                                 f"（配置名≠按钮名），用 browser.py snapshot/eval 取界面原词改写；"
                                 f"若界面确实显示「{w}」，把它框进这一步的截图即可通过")
                elif w in clicks and has_evidence:
                    probs.append(f"行{ln}: 正文让读者点「{w}」，但它没有出现在任何截图证据里；"
                                 f"读者要点的东西必须在图里框出来——把这一步的按钮框进截图重截，"
                                 f"或核对界面改成原词")
                else:
                    notes.append(f"行{ln}: 「{w}」不在系统原词表和截图证据里 → 是举例值就放着，"
                                 f"是字段/按钮名就核对界面改成原名")
    return probs, notes


def check_outline(md: str, base: Path) -> list:
    """骨架小节级核对：outline 章节清单里列出的操作小节，正文必须逐一存在。

    改版实测的教训：机检报错后弱模型靠删小节、并小节缩小检查面，机检照样绿。
    骨架是用户确认的覆盖合同，细到小节级逐条核对，删内容就会在这里现形。
    只核 outline → 正文方向；常见问题、注意事项这类固定小节不用写进骨架。
    """
    p = base / "outline.md"
    if not p.exists():
        return []           # outline 缺失由既有检查负责
    text = p.read_text(encoding="utf-8", errors="ignore")
    # 认标题行定位，不裸搜子串：outline 正文里先提到「章节清单」四个字会把段落切错
    _h = re.search(r"^#{1,3}[^\n]*章节清单", text, re.M)
    if not _h:
        if "章节清单" not in text:
            return ["outline.md 没有「章节清单」段：骨架要列出章和操作小节，它是确认点一的凭证"]
        _h = re.search(r"章节清单", text)
    rest = text[_h.start():]
    nxt = rest.find("\n## ")
    seg = rest if nxt == -1 else rest[:nxt]
    subs = [m.group(1).strip() for m in re.finditer(r"^\s+[-*]\s+(\S.*)$", seg, re.M)]
    if not subs:
        return ["outline.md 章节清单没细到操作小节：每章下面用缩进列表列出操作小节名"
                "（如新建、核销、审批各一节），随确认点一让用户确认；"
                "机检拿它核正文覆盖度，删小节、并小节都会在这里报出来"]
    titles = " | ".join(re.sub(r"^\d+\.\d+\s*", "", t).strip()
                        for t in re.findall(r"^###\s+(.*)$", md, re.M))
    probs = []
    for s in subs:
        name = re.sub(r"[（(].*?[)）]", "", s).strip()
        if name and name not in titles:
            probs.append(f"outline.md 章节清单里的小节「{name}」在正文找不到对应 ### 小节；"
                         f"骨架是用户确认的覆盖合同，不许删小节、并小节消化机检报错；"
                         f"骨架本身要调整就改 outline 并重新让用户确认")
    return probs


def check_baseline(md: str, baseline_path) -> list:
    """改版覆盖度对照：新版相对旧版（--baseline）不许缩水。

    旧版的事实可能有错，但小节承载的业务点不能凭空消失——纠错是改内容不是删小节。
    对照两项：三级小节标题集合、常见问题条数。
    """
    try:
        old = Path(baseline_path).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return [f"--baseline 读不到：{baseline_path}"]

    def secs(t):
        return {re.sub(r"^\d+\.\d+\s*", "", x).strip() for x in re.findall(r"^###\s+(.*)$", t, re.M)}

    def faqs(t):
        return len(re.findall(r"^\s*(?:\*\*\d+[.、]|####\s)", t, re.M))

    probs = []
    miss = sorted(secs(old) - secs(md))
    if miss:
        probs.append(f"对照基线少了 {len(miss)} 个小节：{'、'.join(miss[:8])}"
                     + ("等" if len(miss) > 8 else "")
                     + "；改版不许用删小节消化机检报错——业务点保留，事实按证据逐项纠")
    fo, fn = faqs(old), faqs(md)
    if fn < fo:
        probs.append(f"常见问题从基线的 {fo} 条缩到 {fn} 条；能被证据支撑的逐条恢复，"
                     f"确实站不住的在 notes.md 列明原因，交付时报给用户裁决")
    return probs


def collapse_probs(probs: list, keep: int = 5, threshold: int = 8) -> list:
    """同一条规则的报错刷屏时折叠：只留前几条 + 一行汇总。

    修复方式相同的报错，看 5 条和看 30 条给 agent 的信息量一样，
    多出来的只是重复进上下文烧 token。按"去掉行号和「」内容后的模板"归组，
    组内条数达到 threshold 才折叠，正常量级的报错原样全打。
    """
    tmpl = lambda p: re.sub(r"行[\d、]+", "行N", re.sub(r"「[^」]*」", "「…」", p))
    groups: dict = {}
    for p in probs:
        groups.setdefault(tmpl(p), []).append(p)
    out: list = []
    for ps in groups.values():
        if len(ps) >= threshold:
            out += ps[:keep]
            out.append(f"…同类问题共 {len(ps)} 处，其余 {len(ps) - keep} 处已折叠"
                       f"（修复方式同上，修完重跑机检看剩余）")
        else:
            out += ps
    return out


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_suffix(".html")
    vocab_path = baseline_path = None
    argv = sys.argv[1:]
    for flag in ("--vocab", "--baseline"):
        if flag in argv:
            i = argv.index(flag)
            val = argv[i + 1] if i + 1 < len(argv) else None
            if flag == "--vocab":
                vocab_path = val
            else:
                baseline_path = val
            argv = argv[:i] + argv[i + 2:]
    if vocab_path or baseline_path:
        src = Path(argv[0])
        dst = Path(argv[1]) if len(argv) > 1 else src.with_suffix(".html")
    md = src.read_text(encoding="utf-8")
    dst.write_text(render(md, src.parent), encoding="utf-8")
    print(f"已渲染：{dst}")
    metas, ui = load_evidence(src.parent)
    probs = check(md, src.parent)
    probs += check_evidence(md, src.parent, metas)
    probs += check_outline(md, src.parent)
    if baseline_path:
        probs += check_baseline(md, baseline_path)
    hard, vocab_notes = check_vocab(md, vocab_path, ui, bool(metas))
    probs += hard
    if not (src.parent / "outline.md").exists():
        probs.append("产出目录缺 outline.md：骨架（表、页面、章节、数据口径）没有留痕，阶段一可能被跳过")
    if vocab_notes:
        print(f"⚠ 界面名词待核 {len(vocab_notes)} 处（机器分不清字段名和举例值，逐条人工确认）：")
        for n in vocab_notes:
            print(f"  {n}")
    if probs:
        print(f"× 机检 {len(probs)} 处问题：")
        for p in collapse_probs(probs):
            print(f"  {p}")
        sys.exit(2)
    print("✓ 机检通过（格式 + 截图证据语义审计：界面原词、框↔正文、角标顺序、notes 点位）")


if __name__ == "__main__":
    main()
