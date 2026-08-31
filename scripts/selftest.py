#!/usr/bin/env python3
"""机检回归测试：一条命令验证 render.py / browser.py 的全部检查逻辑。

改任何脚本后跑一次：
  python3 scripts/selftest.py

用例覆盖 v1.5 ~ v1.7 实测踩过的坑：hac 内部名冒充界面词、新增按钮逐表不同、
角标顺序、证据缺失、带空格词匹配、操作列编造、开场句式模板、覆盖度门禁
（骨架小节、基线对照、FAQ 空壳）、元信息变体、snapshot 差异输出、报错折叠。
新增机检规则时在这里补用例；跑不绿不许提交。
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


r = load("render")
b = load("browser")

PASS = 0


def ok(cond, label, detail=""):
    global PASS
    if cond:
        PASS += 1
        print(f"  ✓ {label}")
    else:
        print(f"  × {label}\n    {detail}")
        sys.exit(2)


def build_fixture(base: Path):
    """一册能全绿通过的最小手册 + 证据 + 骨架 + 笔记。"""
    from PIL import Image, ImageDraw
    img = base / "images"
    img.mkdir(parents=True)
    for n in ["2-1-收款单列表.png", "2-2-收款单表单.png", "2-3-核销.png"]:
        im = Image.new("RGB", (800, 500), "#ffffff")
        ImageDraw.Draw(im).rectangle([100, 100, 300, 200], outline=(217, 119, 87), width=3)
        im.save(img / n)
    meta = lambda p, d: (img / (p + ".meta.json")).write_text(
        json.dumps(d, ensure_ascii=False))
    meta("2-1-收款单列表.png", {
        "url": "https://app.huoban.com/x", "title": "收款单", "viewport": [1440, 800],
        "targets": [{"order": 1, "ui_text": "添加数据", "rect": [1, 1, 10, 10]},
                    {"order": 2, "ui_text": "核销应收", "rect": [2, 2, 10, 10]}],
        "ui_texts": ["添加数据", "核销应收", "收款单", "发起流程"]})
    meta("2-2-收款单表单.png", {
        "url": "u", "title": "t", "viewport": [1440, 800],
        "targets": [{"order": 1, "ui_text": "发起流程", "rect": [1, 1, 9, 9]}],
        "ui_texts": ["发起流程", "保存"]})
    meta("2-3-核销.png", {"url": "u", "title": "t", "viewport": [1440, 800],
                          "targets": [], "ui_texts": ["核销应收", "确定"]})
    (base / "vocab.json").write_text(json.dumps(
        {"tables": ["收款单"], "fields": ["收款金额", "收款日期"], "options": [],
         "hac_names": ["收款核销"]}, ensure_ascii=False))
    (base / "outline.md").write_text(
        "模块类型：基础资料\n\n## 章节清单\n\n1. 收款登记\n   - 新建收款单\n\n<!-- 用户已确认 -->\n")
    (base / "notes.md").write_text(
        "### 1-1 收款单列表\n- 页面：收款单列表\n- 按钮原文：添加数据、核销应收\n"
        "- 点击结果：点「添加数据」打开收款单表单\n"
        "- 截图：2-1-收款单列表.png、2-2-收款单表单.png、2-3-核销.png\n")
    md = """# 收付款

财务每天在这里登记收款。

## 一、收款登记

财务收到货款后登记一笔收款。

### 1.1 新建收款单

1. 打开「收款单」列表，点右上角「添加数据」新建；已有收款要抵旧账，点行末的「核销应收」。
    ![图 1-1：收款单列表](images/2-1-收款单列表.png)
    <small style="color:#8A8F98">图 1-1：收款单列表</small>
2. 填「收款金额」，点「发起流程」提交，弹出确认框。
    ![图 1-2：收款单表单](images/2-2-收款单表单.png)
    <small style="color:#8A8F98">图 1-2：收款单表单</small>
3. 系统提示已提交，单号自动生成。
    ![图 1-3：核销界面](images/2-3-核销.png)
    <small style="color:#8A8F98">图 1-3：核销界面</small>

### 1.2 常见问题

**1. 收不到款怎么办？**

联系客户。

### 1.3 注意事项

- 金额别填错。
"""
    (base / "手册.md").write_text(md)
    return md


def sec(intro):
    """套一个合规外壳，只测传入的开场句。"""
    return f"# 采购管理\n\n{intro}\n\n## 一、采购需求\n\n仓库缺货时提需求。\n"


def main():
    tmp = Path(tempfile.mkdtemp(prefix="hb-manual-selftest-"))
    fx = tmp / "fx"
    md = build_fixture(fx)
    metas, ui = r.load_evidence(fx)

    print("【基线：全绿手册】")
    probs = (r.check(md, fx) + r.check_evidence(md, fx, metas) + r.check_outline(md, fx)
             + r.check_vocab(md, fx / "vocab.json", ui, True)[0])
    ok(not probs, "全部检查零报", str(probs))
    cli = subprocess.run([sys.executable, str(HERE / "render.py"), str(fx / "手册.md"),
                          "--vocab", str(fx / "vocab.json")], capture_output=True, text=True)
    ok(cli.returncode == 0, "CLI 渲染 + 机检 exit 0", cli.stdout[-400:])

    print("【证据审计】")
    bad = md.replace("点行末的「核销应收」", "点行末的「收款核销」")
    hard, _ = r.check_vocab(bad, fx / "vocab.json", ui, True)
    ok(any("内部名称" in p for p in hard), "hac 内部名冒充界面词 → 硬报", str(hard))
    bad = md.replace("点右上角「添加数据」新建", "点右上角「创建」新建")
    ok(any("添加数据" in p and "创建" in p for p in r.check_evidence(bad, fx, metas)),
       "本节证据是「添加数据」时写「创建」 → 报")
    bad = md.replace("点右上角「添加数据」新建；已有收款要抵旧账，点行末的「核销应收」",
                     "先点「核销应收」抵旧账，再点右上角「添加数据」")
    ok(any("角标顺序" in p for p in r.check_evidence(bad, fx, metas)), "角标顺序与正文相反 → 报")
    (fx / "images/2-3-核销.png.meta.json").rename(fx / "meta.bak")
    ok(any("证据文件" in p for p in r.check_evidence(md, fx, r.load_evidence(fx)[0])),
       "图缺 .meta.json → 报")
    (fx / "meta.bak").rename(fx / "images/2-3-核销.png.meta.json")
    mj = fx / "images/2-3-核销.png.meta.json"
    m = json.loads(mj.read_text())
    m["targets"] = [{"order": 1, "ui_text": "导入 Excel", "rect": [1, 1, 9, 9]},
                    {"order": 2, "ui_text": "Save Draft", "rect": [2, 2, 9, 9]}]
    mj.write_text(json.dumps(m, ensure_ascii=False))
    sp = md.replace("系统提示已提交，单号自动生成。", "点「导入 Excel」批量导入，系统提示已提交。")
    p = r.check_evidence(sp, fx, r.load_evidence(fx)[0])
    ok(not any("导入" in x for x in p) and any("Save Draft" in x for x in p),
       "带空格词：正文有提不报、没提报原词", str(p))
    m["targets"] = []
    mj.write_text(json.dumps(m, ensure_ascii=False))

    print("【编造拦截】")
    bad = md.replace("弹出确认框", "弹出确认框。列表右侧还可以查看收款详情、打开收款核销或查看收款审批")
    ok(any("引界面原词" in p for p in r.check(bad, fx)), "操作列能力不带引号 → 报")
    hard, _ = r.check_vocab("在已通过的单据行内选「一个没证据的词」处理。", fx / "vocab.json", ui, True)
    ok(any("截图证据" in p for p in hard), "行内选「X」无证据 → 硬报")

    print("【开场句式】")
    p = r.check(sec("采购管理管的是一批货从缺货到付钱的全过程：仓库发现缺货就提需求。"), fx)
    ok(any("管的是" in x for x in p) and any("修辞冒号" in x for x in p), "「管的是…全过程：」双报", str(p))
    ok(not [x for x in r.check(sec("仓库或销售发现商品不够卖了，提一张采购需求，由采购合并下单。"), fx)
            if "开场" in x or "冒号" in x], "平铺直叙开场不误伤")
    ok(not any("冒号" in x for x in r.check(sec("采购这条线共三件事：下单、收货、付款，各归一章。"), fx)),
       "真枚举冒号不误伤")

    print("【覆盖度门禁】")
    (fx / "outline.md").write_text("模块类型：基础资料\n\n## 章节清单\n\n1. 收款登记\n"
                                   "   - 新建收款单\n   - 核销应收明细\n\n<!-- 用户已确认 -->\n")
    ok(any("核销应收明细" in x for x in r.check_outline(md, fx)), "outline 小节正文缺失 → 报")
    (fx / "outline.md").write_text("模块类型：基础资料\n\n## 章节清单\n\n1. 收款登记\n\n<!-- 用户已确认 -->\n")
    ok(any("没细到操作小节" in x for x in r.check_outline(md, fx)), "outline 没细到小节 → 报")
    (fx / "outline.md").write_text("输出：Markdown、章节清单见下。\n\n## 章节清单\n\n"
                                   "1. 收款登记\n   - 新建收款单\n\n<!-- 用户已确认 -->\n")
    ok(not r.check_outline(md, fx), "prose 先提到「章节清单」不干扰定位", str(r.check_outline(md, fx)))
    (fx / "outline.md").write_text("模块类型：基础资料\n\n## 章节清单\n\n1. 收款登记\n   - 新建收款单\n\n<!-- 用户已确认 -->\n")
    old = "### 2.1 新建收款单\n### 2.2 核销应收明细\n### 2.3 常见问题\n**1. A？**\n\n**2. B？**\n"
    new = "### 2.1 新建收款单\n### 2.2 常见问题\n**1. A？**\n"
    (tmp / "old.md").write_text(old)
    p = r.check_baseline(new, tmp / "old.md")
    ok(any("核销应收明细" in x for x in p) and any("常见问题从基线" in x for x in p),
       "基线对照：删小节 + 砍 FAQ 双报", str(p))
    hollow = sec("仓库缺货时提需求。") + "\n### 1.1 常见问题\n\n### 1.2 注意事项\n\n- 注意。\n"
    ok(any("空壳" in x for x in r.check(hollow, fx)), "常见问题空壳 → 报")
    ok(not any("空壳" in x for x in r.check(hollow.replace(
        "### 1.1 常见问题\n", "### 1.1 常见问题\n\n[待补充]\n"), fx)), "[待补充] 放行")

    print("【元信息变体】")
    p = r.check(sec("以下操作对应工作区 4000000007711359 中的「进销存管理 v1.6.0」。"), fx)
    for k in ("以下操作对应", "长数字 ID", "版本号"):
        ok(any(k in x for x in p), f"元信息「{k}」 → 报", str(p))
    ok(not any("长数字 ID" in x for x in r.check(sec("订单编号保存后自动生成 DD20260810001。"), fx)),
       "单号示例不误伤长 ID 检查")

    print("【输出治理】")
    many = [f"行{i}: 正文出现行话「底册」：换白话" for i in range(12)] + ["outline.md 缺失"]
    c = r.collapse_probs(many)
    ok(len(c) == 7 and "同类问题共 12 处" in c[5] and c[6] == "outline.md 缺失", "报错折叠", str(c))
    nav = "进销存管理\n财务管理\n收付款管理"
    els1 = [{"tag": "a", "type": "", "text": t} for t in ["财务管理", "收付款管理"]] + \
           [{"tag": "button", "type": "", "text": "添加数据"}, {"tag": "button", "type": "", "text": "核销应收"}]
    out1, st1 = b.snapshot_diff(nav + "\n收款单\n核销应收", els1, {}, 4000)
    els2 = els1[:2] + [{"tag": "button", "type": "", "text": "添加数据"},
                       {"tag": "button", "type": "", "text": "核销应付"}]
    out2, st2 = b.snapshot_diff(nav + "\n付款单\n核销应付", els2, st1, 4000)
    ok("省略" not in out1 and "行与上次相同已省略" in out2 and "[3] button: 核销应付" in out2,
       "snapshot 差异输出：首次全量、之后只报变化", out2)
    out3, _ = b.snapshot_diff(nav + "\n付款单\n核销应付", els2, st2, 4000)
    ok("完全相同" in out3, "同页重复 snapshot → 完全相同")

    print(f"\n✓ 全部 {PASS} 项通过")


if __name__ == "__main__":
    main()
