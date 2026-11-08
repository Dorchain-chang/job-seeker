#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""牛客「实习岗位列表」数据源（v53，2026-11-08 引入）。

替代原来的「校招日程」来源。原因（2026-11-08 实测）：
- 校招日程 tab=3 只有 423 张卡，其中真实习批次在窗的仅 15 条，目标城市命中 6 条
- 实习岗位列表 recruitType=2 有 750 条在窗岗位，目标城市 376 条，AI/算法 109 条，
  且带 JD 正文、日薪、实习时长、每周天数 —— 这才是真正能投的实习

关于「寒假实习」：牛客没有寒假批次标签（全站 750 条里仅 1 条岗位名含"寒假"），
因此按 durationMonths 判定：<=2 个月记「寒假短期」，3 个月+ 记「长期可投」。

被 sync_interns.py（自动化/DB 路径）与 daily_sync.py（零 token/种子路径）共用，
两份口径必须只有这一份实现，避免漂移。
"""
import json
import re
import time
import urllib.parse
import urllib.request

API = "https://www.nowcoder.com/np-api/u/job/search"
REFERER = "https://www.nowcoder.com/jobs/intern/center"
PAGE_SIZE = 50
MAX_PAGES = 60

TARGET_CITIES = ["成都", "北京", "天津"]
REMOTE_KW = ["远程", "线上", "居家", "全国", "不限", "多地"]
# 强 AI 词：只认岗位名里的明确方向词。裸 "AI"/"数据" 不进这里 ——
# "AI 产品市场经理"/"数据分析师" 会误判成算法岗（2026-11-08 实测踩过）
AI_KW = ["算法", "大模型", "机器学习", "深度学习", "推理", "人工智能",
         "自然语言", "NLP", "视觉", "多模态", "推荐", "搜索", "Agent", "LLM"]
AI_RE = re.compile(r"(?<![A-Za-z])AI(?![A-Za-z])", re.I)
TECH_KW = AI_KW + ["数据", "软件", "开发", "计算机", "信息技术", "网络安全", "信息安全",
                   "测试", "前端", "后端", "运维", "嵌入式", "研发", "通信", "客户端", "架构"]

SOURCE = "牛客实习岗位"

# 直连（本机注册表代理 127.0.0.1:7890 非常开）
urllib.request.getproxies = lambda: {}
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

_HDR = {
    "Content-Type": "application/x-www-form-urlencoded",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36",
    "Referer": REFERER,
    "Origin": "https://www.nowcoder.com",
}


def _fetch_page(page):
    form = {"page": str(page), "pageSize": str(PAGE_SIZE), "recruitType": "2",
            "query": "", "jobCity": "", "careerJobId": "-1", "order": "-1", "latest": "false"}
    req = urllib.request.Request(API, data=urllib.parse.urlencode(form).encode(), headers=_HDR)
    with _OPENER.open(req, timeout=25) as r:
        return json.loads(r.read().decode())


def fetch_jobs(pages=None, on_page=None):
    """拉全部在窗实习岗位。返回 (rows, total_page, total_count)。"""
    rows, page, total, count = [], 1, 1, 0
    limit = pages or MAX_PAGES
    while page <= total and page <= limit:
        d = _fetch_page(page).get("data") or {}
        total = d.get("totalPage") or 1
        count = d.get("totalCount") or count
        rows += d.get("datas") or []
        if on_page:
            on_page(page, total, len(rows))
        page += 1
        time.sleep(0.15)
    return rows, total, count


# ---------------------------------------------------------------- 解析

def _clean(s, limit=None):
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s[:limit] if limit else s


def parse_ext(ext):
    """ext 是「字符串里套 JSON」：{"infos": 岗位职责, "requirements": 岗位要求, ...}。"""
    if isinstance(ext, dict):
        return ext
    try:
        return json.loads(ext or "{}")
    except Exception:
        return {}


def company_of(job):
    co = (job.get("recommendInternCompany") or {}).get("companyName")
    if co:
        return _clean(co)
    co = job.get("companyName")
    if co:
        return _clean(co)
    for ident in ((job.get("user") or {}).get("identity") or []):
        if ident.get("companyName"):
            return _clean(ident["companyName"])
    return ""


def cities_of(job):
    cs = [_clean(c) for c in (job.get("jobCityList") or []) if c]
    if not cs and job.get("jobCity"):
        cs = [_clean(job["jobCity"])]
    return cs


def city_hit(cities):
    """目标城市或远程/不限。没写城市视为可投。"""
    if not cities:
        return True, "不限城市/远程"
    hit = [c for c in cities if any(t in c for t in TARGET_CITIES)]
    if hit:
        return True, "、".join(hit)
    rem = [c for c in cities if any(k in c for k in REMOTE_KW)]
    if rem:
        return True, "、".join(rem)
    return False, ""


def is_ai(text):
    t = str(text or "")
    return any(k.lower() in t.lower() for k in AI_KW) or bool(AI_RE.search(t))


def is_tech(text):
    t = str(text or "")
    return any(k.lower() in t.lower() for k in TECH_KW)


def _date(ms):
    if not ms:
        return None
    try:
        ms = int(ms)
        if ms > 4102416000000:      # 4803724800000 这类哨兵值 = 无限期
            return None
        return time.strftime("%Y-%m-%d", time.gmtime(ms / 1000 + 8 * 3600))
    except Exception:
        return None


def to_flat(job):
    """牛客岗位 -> 扁平记录（表/种子共用字段名）。不过滤，只做字段映射。"""
    name = _clean(job.get("jobName"), 60)
    co = company_of(job)
    if not name or not co:
        return None
    ok, place = city_hit(cities_of(job))
    if not ok:
        return None

    months = job.get("durationMonths") or 0
    days = job.get("durationDays") or 0
    smin, smax = job.get("salaryMin"), job.get("salaryMax")
    short = bool(months) and int(months) <= 2

    ext = parse_ext(job.get("ext"))
    jd = ""
    if ext.get("infos") or ext.get("requirements"):
        jd = (_clean(ext.get("infos")) + " " + _clean(ext.get("requirements"))).strip()
        jd = re.sub(r"^岗?位?职责[:：]?\s*", "", jd)
        jd = re.sub(r"\s*岗位要求[:：]?\s*", " ", jd)
    # 卡片上「岗位要求」是 jmeta 里的一行内联小字（薪资 ｜ 地点 ｜ 岗位要求），
    # 塞整段 JD 会把卡片撑爆 → 只留前 60 字，完整 JD 看投递链接
    jd_short = jd[:60]

    tags = ["技术岗" if is_tech(name) else "非技术岗"]
    tags.append("寒假短期" if short else "长期可投")
    if months:
        tags.append("%s个月" % int(months))
    if days:
        tags.append("%s天/周" % int(days))
    if is_ai(name):
        tags.append("AI相关")

    pay = ""
    if smin and smax:
        pay = "%s-%s元/天" % (int(smin), int(smax))
    elif smin or smax:
        pay = "%s元/天" % int(smin or smax)

    rec = {
        "公司": co,
        "岗位名称": name,
        "薪资": pay,
        "工作地点": place,
        "岗位要求": jd_short or ("%s实习" % ("%s个月" % int(months) if months else "长期")),
        "投递状态": "待投递",
        "来源": SOURCE,
        "备注": " · ".join(tags),
        "岗位ID": str(job.get("id") or ""),
        "牛客ID": str(job.get("companyId") or ""),
        "投递链接": "https://www.nowcoder.com/jobs/detail/%s" % job.get("id"),
    }
    begin, end = _date(job.get("deliverBegin")), _date(job.get("deliverEnd"))
    if begin:
        rec["网申开始"] = begin
    if end:
        rec["截止日期"] = end
    return rec


def key_of(rec):
    """去重键：公司 + 岗位名称（与站点端 key_intern 一致）。"""
    co = _clean(rec.get("公司"))
    nm = _clean(rec.get("岗位名称"))
    if not co:
        return ""
    return "co:" + co + "|" + nm


def merge_city_variants(rows):
    """同一公司同一岗位常在多个城市各发一条（快手/字节常见）。
    直接按「公司+岗位名」去重会连其他城市一起丢掉 → 先合并城市列表再落记录。
    返回 (合并后的 jobs, 合并掉多少条)。"""
    out, index, dropped = [], {}, 0
    for job in rows:
        co, nm = company_of(job), _clean(job.get("jobName"), 60)
        k = (co, nm)
        if not co or not nm:
            continue
        if k not in index:
            job = dict(job)
            job["jobCityList"] = list(cities_of(job))
            index[k] = job
            out.append(job)
        else:
            cur = index[k]["jobCityList"]
            for c in cities_of(job):
                if c not in cur:
                    cur.append(c)
            dropped += 1
    return out, dropped


def collect(cities_only=True, ai_only=False, max_new=0):
    """抓取 + 合并同岗多城 + 过滤 + 去重。返回 (records, stats)。"""
    rows, total_page, total_count = fetch_jobs()
    merged, city_merged = merge_city_variants(rows)
    flat, seen = [], set()
    for job in merged:
        if ai_only and not is_ai(_clean(job.get("jobName"))):
            continue
        rec = to_flat(job)
        if not rec:
            continue
        k = key_of(rec)
        if not k or k in seen:
            continue
        seen.add(k)
        flat.append(rec)

    # AI 相关 + 寒假短期 优先（同分按截止日期近的在前）
    flat.sort(key=lambda r: (0 if "AI相关" in r["备注"] else 1,
                             0 if "寒假短期" in r["备注"] else 1,
                             r.get("截止日期") or "9999-99-99"))
    if max_new:
        flat = flat[:max_new]
    stats = {"rows": len(rows), "total_page": total_page, "total_count": total_count,
             "city_merged": city_merged, "merged": len(merged), "kept": len(flat)}
    return flat, stats


def to_db(rec):
    """扁平记录 -> 资料库 batch_add 的 properties 结构。"""
    out = {
        "公司": {"text": rec["公司"]},
        "岗位名称": {"text": rec["岗位名称"]},
        "工作地点": {"text": rec["工作地点"]},
        "岗位要求": {"text": rec["岗位要求"]},
        "投递状态": {"select": rec.get("投递状态") or "待投递"},
        "来源": {"text": rec.get("来源") or SOURCE},
        "备注": {"text": rec.get("备注") or ""},
    }
    if rec.get("薪资"):
        out["薪资"] = {"text": rec["薪资"]}
    if rec.get("牛客ID"):
        out["牛客ID"] = {"text": rec["牛客ID"]}
    if rec.get("投递链接"):
        out["投递链接"] = {"url": {"text": "投递入口", "link": rec["投递链接"]}}
    if rec.get("网申开始"):
        out["网申开始"] = {"date": rec["网申开始"]}
    if rec.get("截止日期"):
        out["截止日期"] = {"date": rec["截止日期"]}
    return out


def to_seed(rec, record_id):
    """扁平记录 -> seed.json 的 interns 行（与站点内嵌结构一致）。"""
    out = {
        "公司": rec["公司"],
        "岗位名称": rec["岗位名称"],
        "薪资": rec.get("薪资") or "",
        "工作地点": rec["工作地点"],
        "岗位要求": rec["岗位要求"],
        "投递状态": rec.get("投递状态") or "待投递",
        "来源": rec.get("来源") or SOURCE,
        "备注": rec.get("备注") or "",
        "record_id": record_id,
    }
    if rec.get("牛客ID"):
        out["牛客ID"] = rec["牛客ID"]
    if rec.get("投递链接"):
        out["投递链接"] = [{"link": rec["投递链接"], "text": "投递入口"}]
    if rec.get("网申开始"):
        out["网申开始"] = rec["网申开始"] + "T00:00:00Z"
    if rec.get("截止日期"):
        out["截止日期"] = rec["截止日期"] + "T00:00:00Z"
    return out
