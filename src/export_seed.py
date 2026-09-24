#!/usr/bin/env python3
"""导出 4 张资料库表为独立站点用的种子数据（只读）。

stdin 首行: token
输出: src/seed/seed.json  {jobs, apps, interns, inbox, exportedAt}
"""
import json
import subprocess
import sys
import time
from pathlib import Path

DB = r"D:/workbuddy/resources/app.asar.unpacked/resources/plugins/workbuddy-builtin/skills/library/database"
PY = sys.executable
HERE = Path(__file__).parent

TABLES = {
    "jobs": "GgZ71tywhs4HEZytFSqXTP",
    "apps": "oBGkMFTv9Xv4Xn5gFOK18S",
    "interns": "tgH8096uENTaIj8RSY9qm5",
    "inbox": "EdCHnKtjZIXEw37tUmvhqL",
}


def query_all(dbid, token):
    recs, cursor, pages = [], None, 0
    while pages < 60:
        args = [PY, DB + "/query_database_record.py", "--database-id", dbid,
                "--page-size", "100", "--token-stdin"]
        if cursor:
            args += ["--start-cursor", cursor]
        r = subprocess.run(args, input=(token + "\n").encode(), capture_output=True)
        out = r.stdout.decode("utf-8", "replace").strip()
        try:
            d = json.loads(out.splitlines()[0])
        except Exception:
            print(f"  QUERY FAIL {dbid}: {out[:300]}")
            break
        recs += d.get("results") or []
        cursor = d.get("next_cursor") or d.get("nextCursor")
        pages += 1
        if not cursor or not (d.get("has_more") or d.get("hasMore")):
            break
        time.sleep(0.15)
    return recs


def main():
    token = sys.stdin.readline().strip()
    out = {"exportedAt": time.strftime("%Y-%m-%d %H:%M")}
    for name, dbid in TABLES.items():
        recs = query_all(dbid, token)
        out[name] = recs
        print(f"{name}: {len(recs)} 条")
    seed_dir = HERE / "seed"
    seed_dir.mkdir(exist_ok=True)
    p = seed_dir / "seed.json"
    p.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {p} ({p.stat().st_size/1024:.1f} KB)")
    # 同步入库的公开快照（只留 exportedAt + jobs）：CI 拿不到全量快照，会回落到它重建
    # dist/public。两者不同步会让 lint 的 `git diff --exit-code -- dist` 失败（v49 实际踩过）。
    # 固定 indent=1 + LF + 尾随换行，避免每次导出都产生无意义 diff。
    pub = seed_dir / "seed.public.json"
    with open(pub, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"exportedAt": out.get("exportedAt"), "jobs": out.get("jobs", [])},
                           ensure_ascii=False, indent=1) + "\n")
    print(f"wrote {pub} ({pub.stat().st_size/1024:.1f} KB)  <- CI 公开版兜底快照")


if __name__ == "__main__":
    main()
