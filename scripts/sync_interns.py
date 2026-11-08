#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""牛客实习岗位 -> 资料库「成都实习岗位」表（v53，2026-11-08 换源）。

**为什么换源**：原来的「校招日程 tab=3」实测 423 张卡里真实习批次在窗的只有 15 条、
目标城市命中 6 条，每天跑几乎必然"无新增"。实习岗位列表（recruitType=2）有 750 条
在窗岗位，合并同岗多城后 207 个唯一岗位、目标城市 148 条、其中 AI 相关 46 条，
还自带 JD 正文 / 日薪 / 实习时长 / 每周天数 / 投递截止 —— 这才是能直接投的池子。

**「寒假实习」口径**：牛客没有寒假批次标签（750 条里仅 1 条岗位名含"寒假"）。
按 durationMonths 判定：<=2 个月标「寒假短期」，3 个月+ 标「长期可投」，
其余信息（月数/每周天数/日薪）全部写进备注，由用户在页面上自己判。

用法：
    printf '%s\\n' "<token>" | python scripts/sync_interns.py
    python scripts/sync_interns.py --dry-run      # 只打印口径，不写库（无需 token）
    python scripts/sync_interns.py --ai-only      # 只收 AI/算法相关岗位
    python scripts/sync_interns.py --max-new 200  # 单次上限（0=不限，默认 0）
"""
import argparse
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import intern_source as src  # noqa: E402

INTERN_DB = "tgH8096uENTaIj8RSY9qm5"
DB_DIR = r"D:/workbuddy/resources/app.asar.unpacked/resources/plugins/workbuddy-builtin/skills/library/database"
PY = sys.executable
BATCH = 50


def out(*args):
    print(*args)


def db_script(name, args, token, stdin_payload=None):
    """注意：batch_add_database_records.py 的 --stdin 是「整个 stdin 必须是一段 JSON」，
    前面拼 token 行会让它 json.loads 失败并报「输入 JSON 为空或格式非法」。"""
    cmd = [PY, DB_DIR + "\\" + name] + args
    inp = stdin_payload.encode() if stdin_payload is not None else (token + "\n").encode()
    r = subprocess.run(cmd, input=inp, capture_output=True)
    o = r.stdout.decode("utf-8", "replace").strip()
    first = o.splitlines()[0].strip() if o else ""
    try:
        return json.loads(first)
    except Exception:
        return {"error": (o or r.stderr.decode("utf-8", "replace"))[:300]}


def existing_keys(token):
    """拉全表已有记录，返回 (去重键集合, 公司集合)。游标翻页，避免 page-size 上限漏记录。"""
    keys, companies, cursor = set(), set(), None
    while True:
        args = ["--database-id", INTERN_DB, "--page-size", "100",
                "--fields", '["公司","岗位名称"]', "--token-stdin"]
        if cursor:
            args += ["--start-cursor", cursor]
        q = db_script("query_database_record.py", args, token)
        if "error" in q:
            raise RuntimeError(json.dumps(q, ensure_ascii=False)[:200])
        for rec in (q.get("results") or []):
            co = rec.get("公司")
            if isinstance(co, dict):
                co = co.get("text")
            nm = rec.get("岗位名称")
            if isinstance(nm, dict):
                nm = nm.get("text")
            co, nm = str(co or "").strip(), str(nm or "").strip()
            if co:
                companies.add(co)
                keys.add("co:" + co + "|" + nm)
        if q.get("has_more") and q.get("next_cursor"):
            cursor = q["next_cursor"]
        else:
            break
    return keys, companies


def main():
    ap = argparse.ArgumentParser(description="牛客实习岗位 -> 成都实习岗位表")
    ap.add_argument("--dry-run", action="store_true", help="只打印，不写库、不需要 token")
    ap.add_argument("--ai-only", action="store_true", help="只收 AI/算法相关岗位")
    ap.add_argument("--max-new", type=int, default=0, help="单次最多新增（0=不限）")
    args = ap.parse_args()

    recs, stats = src.collect(ai_only=args.ai_only, max_new=args.max_new)
    out("实习岗位池: %d 张卡 / %d 页 / %d 条在窗" % (stats["rows"], stats["total_page"], stats["total_count"]))
    out("同岗多城合并掉: %d 条 -> 唯一岗位 %d" % (stats["city_merged"], stats["merged"]))
    out("目标城市(成都/北京/天津)+远程命中: %d" % stats["kept"])

    ai_n = sum(1 for r in recs if "AI相关" in r["备注"])
    tech_n = sum(1 for r in recs if r["备注"].startswith("技术岗"))
    short_n = sum(1 for r in recs if "寒假短期" in r["备注"])
    out("其中 技术岗 %d / AI 相关 %d / 寒假短期(<=2月) %d" % (tech_n, ai_n, short_n))
    for city in ("北京", "成都", "天津"):
        out("   含 %s: %d" % (city, sum(1 for r in recs if city in r["工作地点"])))

    if args.dry_run:
        out("\n--dry-run：以下为前 15 条 --")
        for r in recs[:15]:
            out("  %-30s %-12s %s" % (r["岗位名称"][:30], r["工作地点"][:12], r["备注"]))
        out("\n未写库、未写文件。")
        return 0

    token = sys.stdin.readline().strip()
    if not token:
        out("NO TOKEN")
        return 1

    try:
        keys, companies = existing_keys(token)
    except Exception as e:  # noqa: BLE001
        out("QUERY FAIL: %s" % str(e)[:200])
        return 1
    out("表内已有: %d 条 / %d 家公司" % (len(keys), len(companies)))

    todo = [r for r in recs if src.key_of(r) not in keys]
    out("to add: %d" % len(todo))
    if not todo:
        out("NOTHING TO ADD")
        return 0

    added, failed = [], []
    for i in range(0, len(todo), BATCH):
        chunk = todo[i:i + BATCH]
        payload = json.dumps({"database_id": INTERN_DB, "records": [src.to_db(r) for r in chunk]},
                             ensure_ascii=False)
        a = db_script("batch_add_database_records.py", ["--stdin", "--token-stdin"], token,
                      stdin_payload=payload)
        if "error" in a:
            failed += [r["岗位名称"] for r in chunk]
            out("BATCH FAIL:", json.dumps(a, ensure_ascii=False)[:200])
            continue
        for item in (a.get("results") or []):
            idx = item.get("index")
            if item.get("success"):
                added.append(chunk[idx]["岗位名称"])
            else:
                failed.append(chunk[idx]["岗位名称"])

    out("ADD OK: %d" % len(added))
    out("companies:", "、".join(sorted({r["公司"] for r in todo if r["岗位名称"] in added})))
    if failed:
        out("failed: %d" % len(failed))
    return 0


if __name__ == "__main__":
    sys.exit(main())
