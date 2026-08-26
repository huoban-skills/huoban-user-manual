#!/usr/bin/env python3
"""从落盘的采集文件生成章节摘要包（紧凑 Markdown），AI 只读本脚本输出，不读原始 JSON。

前置落盘（采集目录下）：
  facts.json / layout-<table_id>.json / automation-<table_id>.json
  三样都由 collect.py 一次落齐：
      python3 collect.py --space-id <sid> --dir <采集目录> --tables "表A,表B"

用法：
  python3 digest.py --dir <采集目录> --tables "表名A,表名B" --outline <产出目录>/outline.md

门闩：--outline 指向的 outline.md 必须存在且含用户确认标记 <!-- 用户已确认 -->，
否则拒绝运行——阶段一的交付物是 outline.md 本身，先交用户确认再进阶段二。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load(path: Path):
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def field_note(f: dict, table_names: dict) -> str:
    notes = []
    if f.get("options"):
        notes.append("选项: " + " / ".join(str(o) for o in f["options"]))
    rel = f.get("relation")
    if rel:
        target = rel.get("target_table_name") or table_names.get(str(rel.get("target_table_id")), "?")
        sel = "多选" if rel.get("selection") == "multiple" else "单选"
        notes.append(f"→ {target}（{sel}）")
    if f.get("unique"):
        notes.append("不可重复")
    if f.get("derived"):
        notes.append("系统计算")
    if f.get("system"):
        notes.append("系统字段")
    return "；".join(notes)


def flatten_layout(main_layout) -> list:
    ids = []
    for row in main_layout or []:
        if isinstance(row, list):
            ids.extend(str(i) for i in row)
        else:
            ids.append(str(row))
    return ids


def digest_table(table: dict, layout: dict | None, auto: dict | None, table_names: dict) -> str:
    out = []
    tid = table["table_id"]
    stats = table.get("stats") or {}
    head = f"## {table['name']}（table_id: {tid}"
    if stats.get("item_count") is not None:
        head += f"，现有 {stats['item_count']} 条记录"
    out.append(head + "）")

    fields = {str(f["field_id"]): f for f in table.get("fields", [])}

    # 字段顺序：优先表单主区布局，缺布局按 facts 顺序
    ordered, seen = [], set()
    form_fields = {}
    if layout:
        form_fields = {str(f["field_id"]): f for f in layout.get("form_fields", [])}
        for fid in flatten_layout(layout.get("main_layout")):
            ff = form_fields.get(fid)
            if ff and ff.get("field_type") == "separator":
                ordered.append(("sep", ff.get("name", "")))
                seen.add(fid)
                continue
            if fid in fields and fid not in seen:
                ordered.append(("field", fields[fid]))
                seen.add(fid)
    for f in table.get("fields", []):
        if f.get("field_type") in ("separator", "description"):
            continue
        if str(f["field_id"]) not in seen:
            ordered.append(("field", f))
            seen.add(str(f["field_id"]))

    out.append("\n### 字段（顺序=表单主区布局）" if layout else "\n### 字段（未取布局，按采集顺序）")
    out.append("| 字段 | 类型 | 必填 | 要点 |")
    out.append("|---|---|---|---|")
    for kind, item in ordered:
        if kind == "sep":
            out.append(f"| **—— {item} ——** | 分组 | | |")
            continue
        f = item
        note = field_note(f, table_names)
        prompt = ""
        ff = form_fields.get(str(f["field_id"]))
        if ff and ff.get("has_input_prompt"):
            prompt = f"填写提示:「{ff.get('input_prompt', '')}」"
        note = "；".join(x for x in [note, prompt] if x)
        out.append(f"| {f['name']} | {f.get('type_label', f.get('field_type'))} | {'是' if f.get('required') else ''} | {note} |")

    if layout:
        tabs = [t for t in (layout.get("tabs") or {}).get("items", []) if t.get("is_show")]
        subs = {str(s["layout_field_id"]): s for s in layout.get("sub_tables", [])}
        if tabs:
            out.append("\n### 详情页标签页（隐藏的已排除）")
            for t in tabs:
                line = f"- {t['name']}（{t['type']}"
                s = subs.get(str(t.get("layout_field_id")))
                if s and s.get("child_table_id"):
                    child = table_names.get(str(s["child_table_id"]), s["child_table_id"])
                    line += f"，子表 → {child}"
                out.append(line + "）")

    if auto:
        autos = auto.get("automations") or []
        enabled = [a for a in autos if a.get("status") == "enable"]
        disabled = len(autos) - len(enabled)
        if enabled:
            out.append("\n### 自动化（深查用 hac --output-mode purpose automation get --automation-id <id>）")
            for a in enabled:
                line = f"- [{a['type']}] {a['name']}（id: {a['automation_id']}）"
                for desc in a.get("description") or []:
                    line += f"\n  - {desc}"
                out.append(line)
        if disabled:
            out.append(f"\n（另有 {disabled} 条停用自动化，不写入手册）")

    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="采集目录（含 facts.json 等落盘文件）")
    ap.add_argument("--tables", required=True, help="表名或 table_id，逗号分隔")
    ap.add_argument("--outline", required=True, help="产出目录里的 outline.md 路径（须含用户确认标记）")
    args = ap.parse_args()

    outline = Path(args.outline)
    if not outline.exists():
        sys.exit("× outline.md 不存在。先完成阶段一：盘表盘页面、定章节清单，写进 outline.md。\n"
                 "  阶段一的交付物就是 outline.md 本身：输出章节清单给用户，本次任务到此正常完成。")
    if "<!-- 用户已确认 -->" not in outline.read_text(encoding="utf-8"):
        sys.exit("× outline.md 还没有用户确认标记。\n"
                 "  现在结束任务，把 outline.md 的章节清单展示给用户；这就是本次任务的完整交付。\n"
                 "  用户回复确认后，在 outline.md 末尾加一行 <!-- 用户已确认 --> 再继续阶段二。")

    base = Path(args.dir)
    facts = load(base / "facts.json")
    if not facts:
        sys.exit(f"缺 {base}/facts.json，先跑 collect.py")

    all_tables = facts.get("tables", [])
    table_names = {str(t["table_id"]): t["name"] for t in all_tables}
    for t in facts.get("external_tables", []):
        table_names.setdefault(str(t.get("table_id")), t.get("name", "外部表"))

    wanted = [w.strip() for w in args.tables.split(",") if w.strip()]
    chunks = []
    for w in wanted:
        matches = [t for t in all_tables if t["table_id"] == w or t["name"] == w]
        if not matches:
            fuzzy = [t for t in all_tables if w in t["name"]]
            if len(fuzzy) == 1:
                matches = fuzzy
            else:
                sys.exit(f"表「{w}」在 facts.json 里找不到或不唯一（模糊命中 {len(fuzzy)} 个）")
        t = matches[0]
        tid = t["table_id"]
        chunks.append(digest_table(t, load(base / f"layout-{tid}.json"), load(base / f"automation-{tid}.json"), table_names))

    print("\n\n---\n\n".join(chunks))


if __name__ == "__main__":
    main()
