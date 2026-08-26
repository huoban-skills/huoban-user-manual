#!/usr/bin/env python3
"""阶段二轻采集：把范围内每张表的配置、表单布局、自动化清单落盘，并组装 digest.py 认的 facts.json。

替代已下线的 `hac table er-diagram-collect`。逐表跑三条 hac 命令，AI 不读原始 JSON。

用法：
  python3 collect.py --space-id <sid> --dir <采集目录> --tables "产品/物料表,单位表,仓库信息"
  python3 collect.py --space-id <sid> --dir <采集目录> --tables-file <每行一个表名的文件>
  # 表名也可直接写 table_id（纯数字），混写也行

产出（采集目录下）：
  facts.json              全部范围表的字段投影，digest.py 的输入
  layout-<table_id>.json  hac table form-layout get 原样输出
  automation-<table_id>.json  自动化清单，已从 by_type 摊平成 {"automations": [...]}

注意：facts.json 不含记录数（stats）。条数走查时界面直读，不值当为它多跑一轮接口。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

# 不可录入的系统字段类型：digest 里标「系统字段」
SYSTEM_TYPES = {"created_on", "created_by", "updated_on", "updated_by", "auto_number", "item_id"}

# field-config list-types 覆盖不到的布局类字段，补中文名
EXTRA_LABELS = {"sub_table": "子表", "separator": "分组标题", "separator2": "分隔符"}


def hac(*args: str) -> dict:
    """跑一条 hac 命令，返回解析后的 JSON。禁止 2>&1：stdout 是数据，stderr 是 token 统计。"""
    p = subprocess.run(["hac", *args], capture_output=True, text=True)
    if p.returncode != 0 or not p.stdout.strip():
        sys.exit(f"× hac {' '.join(args)} 失败：{p.stderr.strip()[:400]}")
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError:
        sys.exit(f"× hac {' '.join(args)} 输出不是 JSON：{p.stdout[:300]}")


def type_label_map() -> dict:
    d = hac("table", "field-config", "list-types")
    return {**{t["type"]: t["name"] for t in d.get("data", [])}, **EXTRA_LABELS}


def resolve_tables(space_id: str, wanted: list[str]) -> tuple[list[tuple[str, str]], dict]:
    """把表名/ID 列表解析成 [(table_id, name)]（顺序保持传入顺序），并附带全区 table_id→表名 映射。"""
    d = hac("table", "list-tables", "--space-id", space_id)
    by_id = {t["table_id"]: t["name"] for t in d["data"]["tables"]}
    by_name = {t["name"]: t["table_id"] for t in d["data"]["tables"]}
    out = []
    for w in wanted:
        w = w.strip()
        if not w:
            continue
        if w in by_id:
            out.append((w, by_id[w]))
        elif w in by_name:
            out.append((by_name[w], w))
        else:
            fuzzy = [(tid, n) for n, tid in by_name.items() if w in n]
            if len(fuzzy) == 1:
                out.append(fuzzy[0])
            else:
                sys.exit(f"× 表「{w}」在工作区 {space_id} 里找不到或不唯一（模糊命中 {len(fuzzy)} 个）")
    return out, by_id


def project_field(f: dict, labels: dict, table_names: dict) -> dict:
    ft = f.get("field_type", "")
    cfg = f.get("config") or {}
    out = {
        "field_id": f["field_id"],
        "name": f.get("name", ""),
        "field_type": ft,
        "type_label": labels.get(ft, ft),
        "required": bool(f.get("required")),
        "unique": bool(f.get("unique")),
    }
    if ft == "calculation" or f.get("auto_calculate"):
        out["derived"] = True
    if ft in SYSTEM_TYPES:
        out["system"] = True
    opts = [o["name"] for o in cfg.get("options") or [] if o.get("status") == "active"]
    if opts:
        out["options"] = opts
    if f.get("type") in ("relation", "sub_table"):
        tid = cfg.get("table_id")
        target = cfg.get("table") or {}
        out["relation"] = {
            "target_table_id": tid,
            "target_table_name": target.get("name") or table_names.get(str(tid)),
            "selection": "multiple" if (f["type"] == "sub_table" or cfg.get("is_multi")) else "single",
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--space-id", required=True)
    ap.add_argument("--dir", required=True, help="采集目录，不存在会自动建")
    ap.add_argument("--tables", help="表名或 table_id，逗号分隔")
    ap.add_argument("--tables-file", help="每行一个表名的文件")
    args = ap.parse_args()

    if not (args.tables or args.tables_file):
        sys.exit("× --tables 和 --tables-file 至少给一个")
    wanted = []
    if args.tables:
        wanted += args.tables.split(",")
    if args.tables_file:
        wanted += Path(args.tables_file).read_text(encoding="utf-8").splitlines()

    base = Path(args.dir)
    base.mkdir(parents=True, exist_ok=True)

    labels = type_label_map()
    targets, table_names = resolve_tables(args.space_id, wanted)

    tables = []
    for tid, name in targets:
        print(f"采集 {name} ({tid}) ...", file=sys.stderr)

        tc = hac("--output-mode", "full", "table", "get-table", "--table-id", tid)["data"]["table_config"]
        tables.append({
            "table_id": str(tid),
            "name": tc.get("name", name),
            "stats": {},
            "fields": [project_field(f, labels, table_names) for f in tc.get("fields", [])],
        })

        layout = hac("table", "form-layout", "get", "--table-id", tid)
        (base / f"layout-{tid}.json").write_text(
            json.dumps(layout, ensure_ascii=False, indent=1), encoding="utf-8")

        auto = hac("automation", "list", "--table-id", tid, "--space-id", args.space_id)
        flat = []
        for grp in auto.get("by_type", []):
            flat.extend(grp.get("automations", []))
        (base / f"automation-{tid}.json").write_text(
            json.dumps({"automations": flat}, ensure_ascii=False, indent=1), encoding="utf-8")

    facts = {"space_id": args.space_id, "tables": tables}
    (base / "facts.json").write_text(json.dumps(facts, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n完成：{len(tables)} 张表 → {base}/facts.json", file=sys.stderr)


if __name__ == "__main__":
    main()
