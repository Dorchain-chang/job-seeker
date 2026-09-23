#!/usr/bin/env python3
"""同步牛客校招日程(tab=3) -> 「秋招岗位清单」表，全量公司对齐（不限岗位方向）。

stdin 首行: token。
规则：
- 只要 wangshenEndDate 为空 或 >= 当前时间-1天 即入选（不限 careerNameList / batchName）
- 去重：拉取目标表全部已有「公司」
- 临期优先排序，单次最多新增 60 条，每批 50 条写入
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request

DB_ID = "GgZ71tywhs4HEZytFSqXTP"
DB_DIR = r"D:/workbuddy/resources/app.asar.unpacked/resources/plugins/workbuddy-builtin/skills/library/database"
PY = sys.executable
MAX_PAGES = 40
MAX_NEW = 60
BATCH = 50
GRACE_MS = 1 * 24 * 3600 * 1000  # 放宽 1 天
LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sync_autumn_last.log")
_LOG_LINES = []


def log(*args):
    """print + UTF-8 日志文件（避免 PowerShell 重定向转码乱码）。"""
    print(*args)
    _LOG_LINES.append(" ".join(str(a) for a in args))


def flush_log():
    try:
        with open(LOG_PATH, "w", encoding="utf-8") as f:
            f.write("\n".join(_LOG_LINES))
    except Exception:
        pass


def fetch_nowcoder():
    def fetch_page(page):
        url = "https://www.nowcoder.com/np-api/u/school-schedule/list-card?_=%d" % int(time.time() * 1000)
        data = urllib.parse.urlencode(
            {"query": "", "propertyId": "", "page": page, "pageSize": 100, "tab": "3"}
        ).encode()
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Referer": "https://www.nowcoder.com/jobs/school/schedule",
            },
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode())

    rows, page, total_page = [], 1, 1
    while page <= total_page and page <= MAX_PAGES:
        d = fetch_page(page).get("data", {}) or {}
        total_page = d.get("totalPage") or 1
        rows += d.get("datas") or []
        time.sleep(0.25)
        page += 1
    return rows, total_page


def ts2date(ms):
    if not ms:
        return None
    try:
        return time.strftime("%Y-%m-%d", time.gmtime(int(ms) / 1000 + 8 * 3600))
    except Exception:
        return None


def batch_of(row):
    b = str(row.get("batchName") or "")
    if "暑期实习" in b:
        return "27暑期实习"
    if "日常实习" in b:
        return "27日常实习"
    if "秋招" in b:
        return "27秋招"
    return "其他"


def build(row):
    name = re.sub(r"\s+", " ", str(row.get("name") or "")).strip()
    if not name:
        return None
    careers = [str(c) for c in (row.get("careerNameList") or []) if c]
    cities = [str(c) for c in (row.get("cityList") or []) if c]
    link = row.get("customWangshenLink") or row.get("sourceInformation") or ""
    eval_txt = re.sub(r"\s+", " ", str(row.get("companyEvaluation") or ""))[:60]
    rec = {
        "公司": {"text": name},
        "批次": {"select": batch_of(row)},
        "岗位方向": {"text": "、".join(careers[:6])[:80]},
        "工作地点": {"text": "、".join(cities[:5])},
        "优先级": {"select": "P2"},
        "投递状态": {"select": "待投递"},
        "来源": {"text": "牛客校招日程"},
        "备注": {"text": eval_txt},
    }
    begin, end = ts2date(row.get("wangshenBeginDate")), ts2date(row.get("wangshenEndDate"))
    if begin:
        rec["网申开始"] = {"date": begin}
    if end:
        rec["截止日期"] = {"date": end}
    if link:
        rec["投递链接"] = {"url": {"text": "网申入口", "link": link}}
    if row.get("companyId"):
        rec["牛客ID"] = {"text": str(row["companyId"])}
    if not rec["备注"]["text"]:
        rec.pop("备注")
    return rec


def db_call(name, args, token, payload=None):
    cmd = [PY, DB_DIR + "\\" + name] + args
    inp = (token + "\n" + (payload or "")).encode()
    r = subprocess.run(cmd, input=inp, capture_output=True)
    out = r.stdout.decode("utf-8", "replace").strip()
    first = out.splitlines()[0].strip() if out else ""
    try:
        return json.loads(first)
    except Exception:
        return {"error": (out or r.stderr.decode("utf-8", "replace"))[:300]}


def existing_companies(token):
    names, missing_id, cursor = set(), {}, None
    while True:
        args = ["--database-id", DB_ID, "--page-size", "100", "--fields", '["公司","牛客ID"]', "--token-stdin"]
        if cursor:
            args += ["--start-cursor", cursor]
        q = db_call("query_database_record.py", args, token)
        if "error" in q:
            raise RuntimeError(json.dumps(q, ensure_ascii=False)[:200])
        for rec in (q.get("results") or []):
            rid = rec.get("record_id") or rec.get("id")
            v = rec.get("公司")
            if isinstance(v, dict):
                v = v.get("text")
            if not v:
                continue
            name = str(v).strip()
            names.add(name)
            nid = rec.get("牛客ID")
            if isinstance(nid, dict):
                nid = nid.get("text")
            if rid and not nid:
                missing_id[name] = rid
        if q.get("has_more") and q.get("next_cursor"):
            cursor = q["next_cursor"]
        else:
            break
    return names, missing_id


def backfill_ids(token, missing_id, picked_map):
    """对已存在但牛客ID为空的公司，用候选数据补写。"""
    todo = [
        {"record_id": missing_id[name], "牛客ID": {"text": str(cid)}}
        for name, cid in picked_map.items()
        if name in missing_id and cid
    ]
    if not todo:
        return 0, []
    ok, failed = 0, []
    for i in range(0, len(todo), BATCH):
        chunk = todo[i : i + BATCH]
        payload = json.dumps({"database_id": DB_ID, "records": chunk}, ensure_ascii=False)
        a = db_call("batch_update_database_records.py", ["--stdin", "--token-stdin"], token, payload)
        if "error" in a:
            failed += [c["牛客ID"]["text"] for c in chunk]
            continue
        for item in a.get("results") or []:
            if item.get("success"):
                ok += 1
            else:
                failed.append(chunk[item.get("index")]["牛客ID"]["text"])
    return ok, failed


def main():
    token = sys.stdin.readline().strip()
    if not token:
        log("NO TOKEN")
        return

    rows = None
    last_err = None
    for attempt in range(3):  # 首次 + 重试 2 次
        try:
            rows, total_page = fetch_nowcoder()
            break
        except Exception as e:
            last_err = e
            time.sleep(2)
    else:
        log("FETCH FAIL:", str(last_err)[:200])
        return
    log("nowcoder tab3 cards: %d (totalPage=%s)" % (len(rows), total_page))

    now_ms = int(time.time() * 1000)
    picked, seen = [], set()
    for r in rows:
        end = r.get("wangshenEndDate")
        if end and int(end) < now_ms - GRACE_MS:
            continue
        rec = build(r)
        if not rec:
            continue
        name = rec["公司"]["text"]
        if name in seen:
            continue
        seen.add(name)
        picked.append((end or 0, rec))
    log("in-window unique: %d" % len(picked))

    # 临期优先：有截止日期的按升序在前，无截止日期的排最后
    far = now_ms + 10 * 365 * 24 * 3600 * 1000
    picked.sort(key=lambda x: x[0] if x[0] else far)

    try:
        existing, missing_id = existing_companies(token)
    except Exception as e:
        log("QUERY FAIL:", str(e)[:200])
        return
    log("existing companies: %d (missing nowcoder id: %d)" % (len(existing), len(missing_id)))

    # 候选公司名 -> companyId，用于补写
    picked_map = {}
    for _, rec in picked:
        nid = rec.get("牛客ID")
        if nid:
            picked_map[rec["公司"]["text"]] = nid["text"]

    backfilled, backfill_failed = backfill_ids(token, missing_id, picked_map)
    log("BACKFILL OK: %d%s" % (backfilled, (" failed: " + "、".join(backfill_failed)) if backfill_failed else ""))

    todo = [rec for _, rec in picked if rec["公司"]["text"] not in existing][:MAX_NEW]
    log("to add: %d" % len(todo))
    if not todo:
        log("NOTHING TO ADD")
        return

    added, failed = [], []
    for i in range(0, len(todo), BATCH):
        chunk = todo[i : i + BATCH]
        payload = json.dumps({"database_id": DB_ID, "records": chunk}, ensure_ascii=False)
        a = db_call("batch_add_database_records.py", ["--stdin", "--token-stdin"], token, payload)
        if "error" in a:
            failed += [c["公司"]["text"] for c in chunk]
            log("BATCH FAIL:", json.dumps(a, ensure_ascii=False)[:200])
            continue
        for item in a.get("results") or []:
            idx = item.get("index")
            if item.get("success"):
                added.append(chunk[idx]["公司"]["text"])
            else:
                failed.append(chunk[idx]["公司"]["text"])

    log("ADD OK: %d" % len(added))
    log("companies:", "、".join(added))
    if failed:
        log("failed:", "、".join(failed))
    flush_log()


if __name__ == "__main__":
    main()
