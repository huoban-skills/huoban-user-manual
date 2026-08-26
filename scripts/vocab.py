#!/usr/bin/env python3
"""从采集目录抽出系统原词表，供 render.py 校验手册里的界面名词是否生造。

规则「界面名词用平台/系统原名，不转述不生造」原来没有任何执行点：写手册时
凭印象写字段名，读者按图索骥找不到。本脚本把落盘的表名、字段名、选项值汇成
一份 vocab.json，render.py --vocab 拿它逐个核对正文里「」引的界面名。

用法：
  python3 vocab.py --dir <采集目录> [--out <采集目录>/vocab.json]

输入（采集目录下，collect.py 的产物）：
  facts.json              全部表的表名与字段名
  layout-<table_id>.json  表单布局，含字段名（facts 缺字段时兜底）

产出 vocab.json：
  {"tables": [...], "fields": [...], "options": [...]}
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def walk_names(obj, out: set, key: str = "name"):
    """递归收集所有 name 值（字段名、选项名在各层级都可能出现）。"""
    if isinstance(obj, dict):
        v = obj.get(key)
        if isinstance(v, str) and 0 < len(v) <= 20:
            out.add(v.strip())
        for x in obj.values():
            walk_names(x, out, key)
    elif isinstance(obj, list):
        for x in obj:
            walk_names(x, out, key)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="采集目录")
    ap.add_argument("--out", help="输出路径，默认 <采集目录>/vocab.json")
    a = ap.parse_args()

    base = Path(a.dir)
    tables, fields, options = set(), set(), set()

    facts = base / "facts.json"
    if facts.exists():
        d = json.loads(facts.read_text())
        for t in d.get("tables", []):
            if t.get("name"):
                tables.add(t["name"].strip())
            for f in t.get("fields", []) or []:
                if isinstance(f, dict) and f.get("name"):
                    fields.add(f["name"].strip())
                # 单选/多选的候选值也是读者在界面上看到的词
                walk_names(f.get("options") or f.get("choices") or [], options)

    # 自动化里的快捷按钮名（客户对账、收款录入这类）也是界面上的原名
    buttons = set()
    for au in base.glob("automation-*.json"):
        try:
            walk_names(json.loads(au.read_text()), buttons)
        except Exception:
            continue
    options |= {b for b in buttons if len(b) <= 12}

    # 表单布局兜底：facts 里没展开字段的表，从 layout 里补
    for lay in base.glob("layout-*.json"):
        try:
            walk_names(json.loads(lay.read_text()), fields)
        except Exception:
            continue

    out = Path(a.out) if a.out else base / "vocab.json"
    payload = {
        "tables": sorted(tables),
        "fields": sorted(fields),
        "options": sorted(options),
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    print(f"已写 {out}：表 {len(tables)}、字段 {len(fields)}、选项 {len(options)}")


main()
