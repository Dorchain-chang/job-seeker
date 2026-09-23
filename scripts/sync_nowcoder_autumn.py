#!/usr/bin/env python3
"""Sync Nowcoder school-schedule (tab=3) -> 秋招岗位清单 (GgZ71tywhs4HEZytFSqXTP).

Filter: careerNameList hits AI/algorithm keywords; wangshenEndDate empty or >= now-1d;
        batchName contains "27".
Dedupe against existing 公司; write at most 30 new records, earliest deadline first.

stdin first line: token.
"""
import json, re, subprocess, sys, time, urllib.parse, urllib.request

DB_ID = "GgZ71tywhs4HEZytFSqXTP"
DB_DIR = r"D:/workbuddy/resources/app.asar.unpacked/resources/plugins/workbuddy-builtin/skills/library/database"
PY = sys.executable

CAREER_KW = ["算法", "人工智能", "AI", "大模型", "机器学习", "深度学习", "数据"]
MAX_PAGES = 40
PAGE_SIZE = 20
MAX_NEW = 30
BATCH = 50
DAY_MS = 86400000


def fetch_page(page, retries=3):
    url = "https://www.nowcoder.com/np-api/u/school-schedule/list-card?_=%d" % int(time.time() * 1000)
    body = urllib.parse.urlencode({
        "query": "", "propertyId": "", "page": page,
        "pageSize": PAGE_SIZE, "tab": "3",
    }).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.nowcoder.com/school/schedule",
    })
    last = None
    for i in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode())
        except Exception as exc:
            last = exc
            if i < retries - 1:
                time.sleep(1.0)
    raise last


def fetch_all():
    rows, page, total_page = [], 1, 1
    while page <= total_page and page <= MAX_PAGES:
        resp = fetch_page(page)
        d = resp.get("data") or {}
        total_page = int(d.get("totalPage") or 1)
        rows += d.get("datas") or []
        print("  page %d/%d rows=%d" % (page, total_page, len(rows)), flush=True)
        page += 1
        if page <= total_page:
            time.sleep(0.3)
    return rows


def ts2date(ms):
    if not ms:
        return None
    try:
        return time.strftime("%Y-%m-%d", time.gmtime(int(ms) / 1000 + 8 * 3600))
    except Exception:
        return None


def batch_select(batch_name):
    b = str(batch_name or "")
    if "暑期实习" in b:
        return "27暑期实习"
    if "日常实习" in b:
        return "27日常实习"
    if "秋招" in b:
        return "27秋招"
    return "其他"


def hit_careers(row):
    careers = row.get("careerNameList") or []
    hits = []
    for c in careers:
        cs = str(c)
        if any(k.lower() in cs.lower() for k in CAREER_KW):
            if cs not in hits:
                hits.append(cs)
    return hits


def build(row):
    name = str(row.get("name") or "").strip()
    if not name:
        return None
    careers = hit_careers(row)
    if not careers:
        return None
    batch = str(row.get("batchName") or "")
    if "27" not in batch:
        return None
    end_raw = row.get("wangshenEndDate")
    now = int(time.time() * 1000)
    if end_raw and int(end_raw) < now - DAY_MS:
        return None

    cities = [str(c) for c in (row.get("cityList") or []) if c][:5]
    link = str(row.get("customWangshenLink") or row.get("sourceInformation") or "").strip()
    eval_txt = re.sub(r"\s+", " ", str(row.get("companyEvaluation") or "")).strip()[:60]

    rec = {
        "公司": {"text": name},
        "批次": {"select": batch_select(batch)},
        "岗位方向": {"text": "、".join(careers)},
        "工作地点": {"text": "、".join(cities)},
        "优先级": {"select": "P2"},
        "投递状态": {"select": "待投递"},
        "来源": {"text": "牛客校招日程"},
        "备注": {"text": eval_txt or (batch or "牛客同步")},
    }
    if row.get("companyId"):
        rec["牛客ID"] = {"text": str(row["companyId"])}
    begin, end = ts2date(row.get("wangshenBeginDate")), ts2date(end_raw)
    if begin:
        rec["网申开始"] = {"date": begin}
    if end:
        rec["截止日期"] = {"date": end}
    if link:
        rec["投递链接"] = {"url": {"text": "网申入口", "link": link}}
    return rec, end_raw


def db_script(name, args, token, stdin_payload=None):
    cmd = [PY, DB_DIR + "\\" + name] + args
    inp = (token + "\n" + (stdin_payload or "")).encode() if stdin_payload is not None else (token + "\n").encode()
    r = subprocess.run(cmd, input=inp, capture_output=True)
    out = r.stdout.decode("utf-8", "replace").strip()
    first = out.splitlines()[0].strip() if out else ""
    try:
        return json.loads(first)
    except Exception:
        return {"error": (out or r.stderr.decode("utf-8", "replace"))[:300]}


def query_all(token):
    out, cur = [], None
    while True:
        args = ["--database-id", DB_ID, "--page-size", "100", "--token-stdin"]
        if cur:
            args += ["--start-cursor", cur]
        d = db_script("query_database_record.py", args, token)
        if "error" in d:
            raise RuntimeError(d["error"])
        out += d.get("results") or []
        cur = d.get("next_cursor")
        if not cur or not d.get("has_more"):
            return out


def main():
    token = sys.stdin.readline().strip()
    if not token:
        print("NO TOKEN")
        return

    rows = []
    try:
        rows = fetch_all()
    except Exception as exc:
        print("FETCH FAIL:", type(exc).__name__, str(exc)[:120])
        return
    print("nowcoder tab3 cards:", len(rows))

    existed_names, filtered = set(), []
    try:
        for rec in query_all(token):
            props = rec.get("properties") or rec
            comp = props.get("公司")
            if isinstance(comp, list):
                comp = (comp[0] or {}).get("text") if comp else ""
            if isinstance(comp, dict):
                comp = comp.get("text")
            comp = str(comp or "").strip()
            if comp:
                existed_names.add(comp)
    except Exception as exc:
        print("QUERY FAIL:", str(exc)[:200])
        return
    print("existing companies:", len(existed_names))

    seen = set()
    for r in rows:
        b = build(r)
        if not b:
            continue
        rec, end_raw = b
        nm = rec["公司"]["text"]
        if nm in seen:
            continue
        seen.add(nm)
        filtered.append((rec, nm))
    print("matched & still open:", len(filtered))

    todo = [(rec, nm) for rec, nm in filtered if nm not in existed_names]
    todo.sort(key=lambda t: (t[0].get("截止日期", {}).get("date") or "9999-99-99"))
    overflow = len(todo) - MAX_NEW
    todo = todo[:MAX_NEW]
    print("to add:", len(todo), ("(skipped %d over cap)" % overflow) if overflow > 0 else "")
    if not todo:
        print("NOTHING TO ADD")
        return
    if "--dry" in sys.argv:
        for rec, nm in todo:
            print("DRY:", json.dumps(rec, ensure_ascii=False))
        return

    added, failed = [], []
    for i in range(0, len(todo), BATCH):
        chunk = [rec for rec, _ in todo[i:i + BATCH]]
        payload = json.dumps({"database_id": DB_ID, "records": chunk}, ensure_ascii=False)
        a = db_script("batch_add_database_records.py", ["--stdin", "--token-stdin"], token, stdin_payload=payload)
        if "error" in a:
            failed += [(rec["公司"]["text"], str(a["error"])[:100]) for rec in chunk]
            print("  ADD FAIL:", json.dumps(a, ensure_ascii=False)[:200])
        else:
            added += [rec["公司"]["text"] for rec in chunk]
            print("  added %d/%d" % (len(added), len(todo)), flush=True)
        time.sleep(0.2)

    print("=== RESULT added=%d failed=%d" % (len(added), len(failed)))
    if added:
        print("ADDED:", "、".join(added))
    for nm, why in failed:
        print("FAILED:", nm, "|", why)


if __name__ == "__main__":
    main()
