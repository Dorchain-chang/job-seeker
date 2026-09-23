#!/usr/bin/env python3
"""Sync Nowcoder schedule (tab=2) -> intern table, filtered by target cities + CS/AI careers.

stdin first line: token. Dedupes against existing companies in the table.
"""
import json, sys, time, re, subprocess, urllib.request, urllib.parse

INTERN_DB = "tgH8096uENTaIj8RSY9qm5"
DB_DIR = r"D:/workbuddy/resources/app.asar.unpacked/resources/plugins/workbuddy-builtin/skills/library/database"
PY = sys.executable

TARGET_CITIES = ["成都", "北京", "天津"]          # 目标城市，命中即收
REMOTE_KW = ["远程", "线上", "居家", "全国", "不限", "多地"]  # 远程/全国类也收（2026-09-23 放宽）
CAREER_KW = ["算法", "人工智能", "AI", "大模型", "机器学习", "深度学习", "数据", "软件", "开发",
             "计算机", "信息技术", "网络安全", "信息安全", "测试", "前端", "后端", "运维", "嵌入式", "研发", "通信"]


def fetch_nowcoder():
    def fetch_page(page):
        url = f"https://www.nowcoder.com/np-api/u/school-schedule/list-card?_={int(time.time()*1000)}"
        # tab=2（实习分类）只有 30 多条，池子太小；改抓 tab=3 全量校招日程，
        # 再靠 match() 里「batchName 必须含实习」的硬条件筛出真实习批次
        data = urllib.parse.urlencode({"query": "", "propertyId": "", "page": page, "pageSize": 100, "tab": "3"}).encode()
        req = urllib.request.Request(url, data=data, headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": "https://www.nowcoder.com/jobs/school/schedule"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())

    rows, page, total_page = [], 1, 1
    while page <= total_page and page <= 40:
        d = fetch_page(page).get("data", {})
        total_page = d.get("totalPage") or 1
        rows += d.get("datas") or []
        time.sleep(0.25)
        page += 1
    return rows


def ts2date(ms):
    """牛客返回的是毫秒时间戳，统一转北京时间 YYYY-MM-DD。"""
    if not ms:
        return None
    try:
        return time.strftime("%Y-%m-%d", time.gmtime(int(ms) / 1000 + 8 * 3600))
    except Exception:
        return None


def match(row):
    # HARD RULE: only true internship batches (27届实习/日常实习/暑期实习…).
    # 秋招/校招/春招批次绝不入实习表（曾在 2026-09-13 混入 16 条秋招后被清理）。
    batch = str(row.get("batchName") or "")
    if "实习" not in batch:
        return None
    cities = [c for c in (row.get("cityList") or []) if c]
    hit_cities = [c for c in cities if any(c.find(t) >= 0 for t in TARGET_CITIES)]
    remote_hit = [c for c in cities if any(c.find(t) >= 0 for t in REMOTE_KW)]
    # 没写城市、或写了「远程/全国/不限」的一并收录（仅实习批次，秋招批次仍被上面挡掉）
    broad = (not cities) or bool(remote_hit)
    if not (hit_cities or broad):
        return None
    place = "、".join(hit_cities) if hit_cities else ("、".join(remote_hit) if remote_hit else "不限城市/远程")
    careers = row.get("careerNameList") or []
    # 方向不再硬过滤：实习批次池子本来就小（约 37 条），2026-09-23 起非技术岗也收录，
    # 由用户在页面自行筛掉；hit_careers 只用来标注岗位名称
    hit_careers = [c for c in careers if any(k.lower() in str(c).lower() for k in CAREER_KW)]
    link = row.get("customWangshenLink") or row.get("sourceInformation") or ""
    eval_txt = re.sub(r"\s+", " ", str(row.get("companyEvaluation") or ""))[:60]
    rec = {
        "公司": {"text": str(row.get("name") or "").strip()},
        "岗位名称": {"text": ("、".join(str(c) for c in hit_careers[:6])
                          or "、".join(str(c) for c in careers[:3]) or "实习")[:60]},
        "工作地点": {"text": place},
        "岗位要求": {"text": batch or "实习"},
        "投递状态": {"select": "待投递"},
        "来源": {"text": "牛客校招日程"},
        "备注": {"text": ("技术岗 · " if hit_careers else "非技术岗 · ") + (f"{batch} · " if batch else "") + (eval_txt or "牛客同步")},
    }
    if row.get("companyId"):
        # 页面「公司情报」凭它生成牛客企业主页/面经/真题/薪资/讨论 5 条精准深链
        rec["牛客ID"] = {"text": str(row["companyId"])}
    if link:
        rec["投递链接"] = {"url": {"text": "投递入口", "link": link}}
    begin, end = ts2date(row.get("wangshenBeginDate")), ts2date(row.get("wangshenEndDate"))
    if begin:
        rec["网申开始"] = {"date": begin}
    if end:
        rec["截止日期"] = {"date": end}
    return rec


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


def main():
    token = sys.stdin.readline().strip()
    if not token:
        print("NO TOKEN"); return

    rows = fetch_nowcoder()
    print(f"nowcoder cards (tab=3): {len(rows)}")
    matched, seen = [], set()
    for r in rows:
        m = match(r)
        if m and m["公司"]["text"] and m["公司"]["text"] not in seen:
            seen.add(m["公司"]["text"])
            matched.append(m)
    print(f"matched (city+career): {len(matched)}")

    # dedupe against existing records
    q = db_script("query_database_record.py", ["--database-id", INTERN_DB, "--page-size", "200", "--token-stdin"], token)
    if "error" in q:
        print("QUERY FAIL:", json.dumps(q, ensure_ascii=False)[:200]); return
    # 兼容两种返回结构：顶层 results / 嵌套 data.records
    data = q.get("data") if isinstance(q.get("data"), dict) else q
    existing = set()
    for rec in (data.get("records") or data.get("results") or []):
        props = rec.get("properties") or rec
        comp = props.get("公司")
        if comp:
            existing.add(str(comp.get("text") if isinstance(comp, dict) else comp))
    print(f"existing companies: {len(existing)}")

    todo = [m for m in matched if m["公司"]["text"] not in existing]
    for m in todo:
        if m.get("投递链接") is None:
            m.pop("投递链接")
    print(f"to add: {len(todo)}")
    if not todo:
        print("NOTHING TO ADD"); return

    payload = json.dumps({"database_id": INTERN_DB, "records": todo}, ensure_ascii=False)
    a = db_script("batch_add_database_records.py", ["--stdin", "--token-stdin"], token, stdin_payload=payload)
    if "error" in a:
        print("ADD FAIL:", json.dumps(a, ensure_ascii=False)[:300]); return
    print("ADD OK:", json.dumps({k: a.get(k) for k in ("added", "count", "total")}, ensure_ascii=False))
    print("companies:", "、".join(m["公司"]["text"] for m in todo))


if __name__ == "__main__":
    main()
