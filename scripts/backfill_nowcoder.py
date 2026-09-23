#!/usr/bin/env python3
"""牛客 companyId 采集 + 回填到「牛客ID」字段。

用法：
    printf '%s\n' '<token>' | python backfill_nowcoder.py [--dry]

步骤：
  1) 抓牛客校招日程 tab=1（全量公司表）分页，建立 公司名 -> companyId 映射
  2) 补充 tab=3（秋招）以确保覆盖
  3) 拉取两张表全部记录，按公司名精确 / 归一化匹配
  4) 分批（100/批）batch-update 写入「牛客ID」
"""
import json, re, subprocess, sys, time, urllib.parse, urllib.request

DB = r"D:/workbuddy/resources/app.asar.unpacked/resources/plugins/workbuddy-builtin/skills/library/database"
PY = sys.executable
JOBS_DB = "GgZ71tywhs4HEZytFSqXTP"
INTERN_DB = "tgH8096uENTaIj8RSY9qm5"

UA = {"Content-Type": "application/x-www-form-urlencoded",
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
      "Referer": "https://www.nowcoder.com/jobs/school/schedule"}


def nowcoder_page(tab, page, page_size=100, query=""):
    url = "https://www.nowcoder.com/np-api/u/school-schedule/list-card?_=%d" % int(time.time() * 1000)
    body = urllib.parse.urlencode({"query": query, "propertyId": "", "page": page,
                                   "pageSize": page_size, "tab": str(tab)}).encode()
    req = urllib.request.Request(url, data=body, headers=UA)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode())
        except Exception:
            if attempt == 2:
                raise
            time.sleep(1.0)


def harvest():
    names = {}
    for tab in (1, 3):
        page, total_page = 1, 1
        while page <= total_page:
            d = (nowcoder_page(tab, page).get("data") or {})
            total_page = d.get("totalPage") or 1
            for row in (d.get("datas") or []):
                n = str(row.get("name") or "").strip()
                cid = row.get("companyId")
                if n and cid and n not in names:
                    names[n] = str(cid)
            page += 1
            time.sleep(0.2)
            if page > 260:
                break
        print("  tab=%d done, map=%d" % (tab, len(names)), flush=True)
    return names


def norm(s):
    s = re.sub(r"[\s（）()·,，.。-]", "", str(s or ""))
    for suf in ("股份有限公司", "有限责任公司", "有限公司", "集团股份", "集团", "科技", "公司"):
        if s.endswith(suf):
            s = s[: -len(suf)]
    return s


def db_query_all(dbid, token):
    out, cur = [], None
    while True:
        args = [PY, DB + "/query_database_record.py", "--database-id", dbid,
                "--page-size", "100", "--token-stdin"]
        if cur:
            args += ["--start-cursor", cur]
        r = subprocess.run(args, input=(token + "\n").encode(), capture_output=True)
        line = r.stdout.decode("utf-8", "replace").strip().splitlines()
        d = json.loads(line[0]) if line else {}
        if "error" in d:
            raise RuntimeError(d["error"])
        out += d.get("results") or []
        cur = d.get("next_cursor")
        if not cur or not d.get("has_more"):
            return out


def db_batch_update(dbid, records, token):
    payload = json.dumps({"database_id": dbid, "records": records}, ensure_ascii=False)
    r = subprocess.run([PY, DB + "/batch_update_database_records.py", "--stdin", "--token-stdin"],
                       input=(token + "\n" + payload).encode(), capture_output=True)
    line = r.stdout.decode("utf-8", "replace").strip().splitlines()
    try:
        return json.loads(line[0]) if line else {"error": "empty"}
    except Exception:
        return {"error": (r.stdout.decode("utf-8", "replace") or r.stderr.decode("utf-8", "replace"))[:200]}


def main():
    dry = "--dry" in sys.argv
    token = sys.stdin.readline().strip()
    if not token:
        print("NO TOKEN"); return

    print("harvest nowcoder company ids ...", flush=True)
    name2id = harvest()
    nid = {}
    for n, cid in name2id.items():
        nid.setdefault(norm(n), cid)
    print("normalized map:", len(nid), flush=True)

    for label, dbid in (("秋招岗位清单", JOBS_DB), ("成都实习岗位", INTERN_DB)):
        recs = db_query_all(dbid, token)
        hit, miss, updates = [], [], []
        for r in recs:
            c = r.get("公司")
            if isinstance(c, list):
                c = (c[0] or {}).get("text") if c else ""
            c = str(c or "").strip()
            if not c:
                continue
            if str(r.get("牛客ID") or "").strip():
                continue
            cid = name2id.get(c) or nid.get(norm(c))
            if cid:
                hit.append(c)
                updates.append({"record_id": r.get("record_id"),
                                "properties": {"牛客ID": {"text": cid}}})
            else:
                miss.append(c)
        print("\n=== %s === 记录 %d · 命中 %d · 未命中 %d" % (label, len(recs), len(hit), len(miss)))
        print("  未命中示例:", "、".join(miss[:15]))
        if dry:
            continue
        ok = 0
        for i in range(0, len(updates), 100):
            res = db_batch_update(dbid, updates[i:i + 100], token)
            if "error" in res:
                print("  UPDATE FAIL:", json.dumps(res, ensure_ascii=False)[:200]); break
            ok += len(updates[i:i + 100])
            print("  updated %d/%d" % (ok, len(updates)), flush=True)
            time.sleep(0.2)
        print("  -> 写入完成:", ok)


if __name__ == "__main__":
    main()
