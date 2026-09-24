#!/usr/bin/env python3
"""每日抓取 · 零 token 独立版。

牛客校招日程(tab=3)  -->  src/seed/seed.json  -->  dist/site + dist/public

**不需要任何 token、不需要 WorkBuddy 连接器**，可以直接用系统计划任务 / cron 定时跑，
也能丢到任何一台有 Python 3 的机器上跑。

用法：
    python scripts/daily_sync.py                # 抓取 + 增量合并 + 重建 site/public
    python scripts/daily_sync.py --dry-run      # 只报告会新增什么，不落盘
    python scripts/daily_sync.py --no-build     # 只更新 seed.json，不重建产物
    python scripts/daily_sync.py --max-new 60   # 单次每表最多新增条数（0 = 不限）

退出码：0 = 有更新并成功 / 2 = 无新增（正常）/ 1 = 出错
"""
import argparse
import io
import json
import os
import random
import re
import string
import subprocess
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SEED_PATH = os.path.join(ROOT, "src", "seed", "seed.json")
PUBLIC_SEED_PATH = os.path.join(ROOT, "src", "seed", "seed.public.json")
LOG_PATH = os.path.join(HERE, "daily_sync_last.log")

NOWCODER_URL = "https://www.nowcoder.com/np-api/u/school-schedule/list-card"
MAX_PAGES = 40
PAGE_SIZE = 100
GRACE_MS = 1 * 24 * 3600 * 1000          # 截止日期放宽 1 天
SOURCE = "牛客校招日程"
SAMPLE_SOURCE = "示例预置"
DEFAULT_MAX_NEW = 60

TARGET_CITIES = ["成都", "北京", "天津"]
REMOTE_KW = ["远程", "线上", "居家", "全国", "不限", "多地"]
CAREER_KW = ["算法", "人工智能", "AI", "大模型", "机器学习", "深度学习", "数据", "软件", "开发",
             "计算机", "信息技术", "网络安全", "信息安全", "测试", "前端", "后端", "运维",
             "嵌入式", "研发", "通信"]

_LINES = []


def log(*args):
    line = " ".join(str(a) for a in args)
    print(line)
    _LINES.append(line)


def flush_log():
    try:
        with io.open(LOG_PATH, "w", encoding="utf-8") as f:
            f.write("\n".join(_LINES))
    except Exception:
        pass


# ---------------------------------------------------------------- 抓取

def fetch_nowcoder():
    """抓全部校招日程卡片（tab=3，含秋招/实习/暑期实习等批次）。"""
    def one(page):
        url = "%s?_=%d" % (NOWCODER_URL, int(time.time() * 1000))
        data = urllib.parse.urlencode(
            {"query": "", "propertyId": "", "page": page, "pageSize": PAGE_SIZE, "tab": "3"}
        ).encode()
        req = urllib.request.Request(url, data=data, headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": "https://www.nowcoder.com/jobs/school/schedule",
        })
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode())

    rows, page, total = [], 1, 1
    while page <= total and page <= MAX_PAGES:
        d = one(page).get("data") or {}
        total = d.get("totalPage") or 1
        rows += d.get("datas") or []
        time.sleep(0.25)
        page += 1
    return rows, total


def fetch_with_retry(tries=3):
    last = None
    for _ in range(tries):
        try:
            return fetch_nowcoder()
        except Exception as e:      # noqa: BLE001
            last = e
            time.sleep(2)
    raise RuntimeError("抓取牛客失败：%s" % str(last)[:200])


# ---------------------------------------------------------------- 转换

def ts2iso(ms):
    """毫秒时间戳 -> 'YYYY-MM-DDT00:00:00Z'（种子里的日期写法）。"""
    if not ms:
        return None
    try:
        return time.strftime("%Y-%m-%dT00:00:00Z", time.gmtime(int(ms) / 1000 + 8 * 3600))
    except Exception:               # noqa: BLE001
        return None


def new_id(n=21):
    alphabet = string.ascii_letters + string.digits
    return "".join(random.choice(alphabet) for _ in range(n))


def batch_of(row):
    b = str(row.get("batchName") or "")
    if "暑期实习" in b:
        return "27暑期实习"
    if "日常实习" in b:
        return "27日常实习"
    if "秋招" in b:
        return "27秋招"
    return "其他"


def _clean(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


def build_job(row):
    """一张秋招/校招卡片 -> 种子行（扁平结构，与 seed.json 一致）。"""
    name = _clean(row.get("name"))
    if not name:
        return None
    rec = {
        "优先级": "P2",
        "公司": name,
        "岗位方向": "、".join(str(c) for c in (row.get("careerNameList") or []) if c)[:80],
        "工作地点": "、".join(str(c) for c in (row.get("cityList") or []) if c)[:60],
        "批次": batch_of(row),
        "投递状态": "待投递",
        "来源": SOURCE,
    }
    if row.get("companyId"):
        rec["牛客ID"] = str(row["companyId"])
    begin, end = ts2iso(row.get("wangshenBeginDate")), ts2iso(row.get("wangshenEndDate"))
    if begin:
        rec["网申开始"] = begin
    if end:
        rec["截止日期"] = end
    link = row.get("customWangshenLink") or row.get("sourceInformation") or ""
    if link:
        rec["投递链接"] = [{"link": link, "text": "网申入口"}]
    ev = _clean(row.get("companyEvaluation"))[:60]
    if ev:
        rec["备注"] = ev
    rec["record_id"] = new_id()
    return rec


def build_intern(row):
    """只收真实习批次（batchName 含「实习」），并在目标城市/远程范围内。"""
    batch = str(row.get("batchName") or "")
    if "实习" not in batch:
        return None
    cities = [c for c in (row.get("cityList") or []) if c]
    hit_cities = [c for c in cities if any(str(c).find(t) >= 0 for t in TARGET_CITIES)]
    remote_hit = [c for c in cities if any(str(c).find(t) >= 0 for t in REMOTE_KW)]
    broad = (not cities) or bool(remote_hit)
    if not (hit_cities or broad):
        return None
    name = _clean(row.get("name"))
    if not name:
        return None
    place = "、".join(hit_cities) if hit_cities else ("、".join(remote_hit) if remote_hit else "不限城市/远程")
    careers = row.get("careerNameList") or []
    hit_careers = [c for c in careers if any(k.lower() in str(c).lower() for k in CAREER_KW)]
    rec = {
        "公司": name,
        "岗位名称": ("、".join(str(c) for c in hit_careers[:6])
                  or "、".join(str(c) for c in careers[:3]) or "实习")[:60],
        "工作地点": place,
        "岗位要求": batch or "实习",
        "投递状态": "待投递",
        "来源": SOURCE,
        "备注": ("技术岗 · " if hit_careers else "非技术岗 · ") + (batch + " · " if batch else "")
                + (_clean(row.get("companyEvaluation"))[:60] or "牛客同步"),
    }
    if row.get("companyId"):
        rec["牛客ID"] = str(row["companyId"])
    link = row.get("customWangshenLink") or row.get("sourceInformation") or ""
    if link:
        rec["投递链接"] = [{"link": link, "text": "投递入口"}]
    begin, end = ts2iso(row.get("wangshenBeginDate")), ts2iso(row.get("wangshenEndDate"))
    if begin:
        rec["网申开始"] = begin
    if end:
        rec["截止日期"] = end
    rec["record_id"] = new_id()
    return rec


# ------------------------------------------------- 去重键（必须与站点端 keyOf 一致）

def key_job(rec):
    nid = _clean(rec.get("牛客ID"))
    if nid:
        return "nc:" + nid
    co = _clean(rec.get("公司"))
    return ("co:" + co) if co else ""


def key_intern(rec):
    co = _clean(rec.get("公司"))
    if not co:
        return ""
    return "co:" + co + "|" + _clean(rec.get("岗位名称"))


def in_window(row, now_ms):
    end = row.get("wangshenEndDate")
    if end and int(end) < now_ms - GRACE_MS:
        return False
    return True


# ---------------------------------------------------------------- 合并

def merge_table(old_rows, new_recs, keyfn, max_new):
    """保留用户已有数据，只追加新键；返回 (合并结果, 新增列表)。"""
    seen = set()
    for r in old_rows:
        k = keyfn(r)
        if k:
            seen.add(k)
    added, dup = [], 0
    for rec in new_recs:
        k = keyfn(rec)
        if not k:
            continue
        if k in seen:
            dup += 1
            continue
        seen.add(k)
        if max_new and len(added) >= max_new:
            continue
        added.append(rec)
    return list(old_rows) + added, added, dup


def load_seed():
    if not os.path.exists(SEED_PATH):
        raise RuntimeError("找不到 %s，请先跑一次 src/export_seed.py 生成基线快照。" % SEED_PATH)
    with io.open(SEED_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_seed(seed):
    tmp = SEED_PATH + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(seed, f, ensure_ascii=False, indent=1)
    os.replace(tmp, SEED_PATH)
    # 一并同步入库的公开快照：CI 拿不到全量快照，会回落到 seed.public.json 重建 dist/public。
    # 两者一旦不同步，lint 的 `git diff --exit-code -- dist` 就会失败（v49 实际踩过）。
    pub = {"exportedAt": seed.get("exportedAt"), "jobs": seed.get("jobs", [])}
    ptmp = PUBLIC_SEED_PATH + ".tmp"
    with io.open(ptmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(pub, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(ptmp, PUBLIC_SEED_PATH)


# ---------------------------------------------------------------- 构建

def rebuild():
    """按顺序重建离线产物（site 与 public 都依赖 seed.json）。"""
    py = sys.executable
    for name in ("build_site.py", "build_public.py"):
        script = os.path.join(ROOT, "src", name)
        if not os.path.exists(script):
            log("SKIP 找不到 %s" % script)
            continue
        r = subprocess.run([py, script], capture_output=True, cwd=ROOT)
        if r.returncode != 0:
            log("BUILD FAIL %s\n%s" % (name, r.stderr.decode("utf-8", "replace")[:400]))
            return False
        log("BUILD OK  %s" % name)
    return True


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser(description="零 token 每日抓取：牛客 -> seed.json -> 重建站点")
    ap.add_argument("--dry-run", action="store_true", help="只报告，不写文件")
    ap.add_argument("--no-build", action="store_true", help="只更新 seed.json")
    ap.add_argument("--max-new", type=int, default=DEFAULT_MAX_NEW, help="每表单次最多新增（0=不限）")
    args = ap.parse_args()

    log("=" * 62)
    log("每日抓取 %s" % time.strftime("%Y-%m-%d %H:%M:%S"))
    log("seed: %s" % SEED_PATH)
    log("=" * 62)

    # 1) 抓取
    try:
        rows, total_page = fetch_with_retry()
    except Exception as e:          # noqa: BLE001
        log("FETCH FAIL: %s" % e)
        flush_log()
        return 1
    log("nowcoder tab3 cards: %d (totalPage=%s)" % (len(rows), total_page))

    # 2) 转换 + 窗口过滤
    now_ms = int(time.time() * 1000)
    jobs_raw, interns_raw = [], []
    seen_job_name = set()
    for r in rows:
        if in_window(r, now_ms):
            rec = build_job(r)
            if rec and rec["公司"] not in seen_job_name:
                seen_job_name.add(rec["公司"])
                jobs_raw.append(rec)
        rec_i = build_intern(r)
        if rec_i:
            interns_raw.append(rec_i)
    log("candidates: 秋招 %d / 实习 %d" % (len(jobs_raw), len(interns_raw)))

    # 3) 合并
    seed = load_seed()
    jobs_before, interns_before = len(seed.get("jobs") or []), len(seed.get("interns") or [])
    jobs_after, jobs_added, jobs_dup = merge_table(seed.get("jobs") or [], jobs_raw, key_job, args.max_new)
    interns_after, interns_added, interns_dup = merge_table(
        seed.get("interns") or [], interns_raw, key_intern, args.max_new)

    log("秋招: %d -> %d（新增 %d，重复跳过 %d）" % (jobs_before, len(jobs_after), len(jobs_added), jobs_dup))
    log("实习: %d -> %d（新增 %d，重复跳过 %d）" % (
        interns_before, len(interns_after), len(interns_added), interns_dup))
    if jobs_added:
        log("新岗位: " + "、".join(r["公司"] for r in jobs_added[:30])
            + ("…" if len(jobs_added) > 30 else ""))
    if interns_added:
        log("新实习: " + "、".join(r["公司"] for r in interns_added[:30])
            + ("…" if len(interns_added) > 30 else ""))

    if not jobs_added and not interns_added:
        log("无新增，无需重建")
        flush_log()
        return 2

    if args.dry_run:
        log("--dry-run：未写文件、未重建")
        flush_log()
        return 0

    # 4) 落盘（apps / inbox 一字不动）
    seed["jobs"] = jobs_after
    seed["interns"] = interns_after
    seed["exportedAt"] = time.strftime("%Y-%m-%d %H:%M")
    save_seed(seed)
    log("已写 seed.json（exportedAt=%s）" % seed["exportedAt"])

    # 5) 重建产物
    if args.no_build:
        log("--no-build：跳过重建")
    elif not rebuild():
        flush_log()
        return 1

    flush_log()
    log("完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
