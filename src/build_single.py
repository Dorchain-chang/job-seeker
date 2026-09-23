#!/usr/bin/env python3
"""Build ONE single-file app that merges all 4 workbench pages.

Reuses build_pages.py generators, extracts each page's <body> sections + <script>,
namespaces element IDs and state fields per module, then merges into a single HTML
where the top nav switches views in-page (no navigation, data fetched once).

Deploy target: same single file is pushed to all 4 nodes so every existing link
opens the full app.
"""
import os, re, sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

import build_pages as bp

MODULES = ["overview", "autumn", "soe", "intern"]

# ---- per-module ID lists (from body templates) + prefix ----
IDS = {
    "overview": ["todayCnt","todayMine","todayList","stWait","stDone","stDdl","stLive",
                 "tdW7","tdNode","tdIb","tdTotal",
                 "aiProvider","aiBase","aiKey","aiModel","aiRemember","aiTest","aiClear","aiStatus",
                 "agStatus","agFnSel","agMt","agT","agTVal","agSys","agSaveTune","agResetTune","agAB",
                 "agAbBox","agAbIn","agAbL","agAbR","agTraceCnt","agTrace","agTip",
                 "rsCount","rsName","rsIntent","rsNote","rsFile","rsPaste","rsSave","rsList",
                 "rpStatus","rpGen","rpClr","rpOut",
                 "cntAutumn","cntSOE","cntIntern","appCnt","appForm","fStage","funnelSvg",
                 "appCards","tplBox","tplApp"],
    "autumn":   ["jobCnt","jobForm","fBatch","fPrio","batchChips","q","fCity","fCareer",
                 "fSt","fBatchF","fSort","filterHint","jobCards","tplBox","tplJob"],
    "soe":      ["jobCnt","jobForm","fBatch","fPrio","q","fCity","fCareer","fSt","fSort",
                 "filterHint","jobCards","tplBox","tplJob"],
    "intern":   ["jobCnt","internForm","q","fSt","fSort","filterHint","jobCards","tplBox","tplJob"],
}
PREFIX = {"overview": "ov", "autumn": "at", "soe": "so", "intern": "ir"}

# shared `state.<field>` fields that must be namespaced (used by multiple modules)
STATE_FIELDS = ["fBatchF", "fSt", "fCity", "fCareer", "q", "fSort"]

REFRESH_LINE = {
    "overview": "function refreshAll(){renderToday();renderTdStats();renderStats();renderModuleCounts();renderFunnel();renderInbox();renderApps();}",
    "autumn":   "function refreshAll(){renderFilterFacets();renderJobs();}",
    "soe":      "function refreshAll(){renderFilterFacets();renderJobs();}",
    "intern":   "function refreshAll(){renderInterns();}",
}

# hand-written per-module registration (bind/setup) replacing the old init()
TAIL = {
"overview": """
MODS.push({refresh:function(){renderToday();renderTdStats();renderStats();renderModuleCounts();renderFunnel();renderInbox();renderApps();renderHeatmap();},setup:function(){fillStageOv();initAiSettings();initAgPanel();initResumes();},bind:function(){
  bindSubmitApp();
  bindFormCache('ov_appForm');
  bindQuickIntel();
  $('ov_todayMine').addEventListener('change',function(){state.todayMine=$('ov_todayMine').checked;renderToday()});
}});
function fillStageOv(){
  var sel=$('ov_fStage');if(!sel)return;sel.innerHTML='';var o0=document.createElement('option');o0.value='';o0.textContent='请选择';sel.appendChild(o0);
  (OPTS['当前阶段']||[]).forEach(function(o){if(o.text===DROP_STAGE)return;var oo=document.createElement('option');oo.value=o.id;oo.textContent=o.text;sel.appendChild(oo)});
}
/* ---- 投递热力图 ---- */
var HM_EV_STAGES=['笔试','一面','二面','HR面','Offer'];
function hmData(){
  var apps={},evs={};
  state.apps.forEach(function(a){
    var d=dOnly(a['投递日期']);
    if(d){(apps[d]=apps[d]||[]).push(a)}
    var st=appStage(a),nd=dOnly(a['下次节点']);
    if(nd&&HM_EV_STAGES.indexOf(st)>=0){(evs[nd]=evs[nd]||[]).push({a:a,st:st,desc:plain(a['节点说明'])})}
  });
  return {apps:apps,evs:evs};
}
function hmLevel(n){return n>=5?4:n>=3?3:n>=2?2:n>=1?1:0}
function hmFmt(dt){return dt.getFullYear()+'-'+('0'+(dt.getMonth()+1)).slice(-2)+'-'+('0'+dt.getDate()).slice(-2)}
function renderHeatmap(){
  var grid=$('hmGrid'),sum=$('hmSum');if(!grid)return;
  var d=hmData(),t=today();
  var end=new Date(t+'T00:00:00');
  var start=new Date(end);start.setDate(start.getDate()-181);
  start.setDate(start.getDate()-start.getDay());
  var totalA=0,totalE=0,streak=0,k;
  for(k in d.apps)totalA+=d.apps[k].length;
  for(k in d.evs)totalE+=d.evs[k].length;
  var cur=new Date(end);
  while(true){var ds=hmFmt(cur);if(d.apps[ds]&&d.apps[ds].length){streak++;cur.setDate(cur.getDate()-1)}else break}
  grid.innerHTML='';
  var frag=document.createDocumentFragment();
  var cur2=new Date(start),endMs=end.getTime();
  while(cur2.getTime()<=endMs){
    var ds2=hmFmt(cur2);
    var n=(d.apps[ds2]||[]).length;
    var c=document.createElement('div');
    c.className='hm-cell l'+hmLevel(n)+(d.evs[ds2]?' ev':'');
    c.setAttribute('data-date',ds2);
    c.setAttribute('title',ds2+' · 投递 '+n+' 家'+(d.evs[ds2]?' · 节点 '+d.evs[ds2].length+' 项':''));
    c.addEventListener('click',function(){showHmDetail(this.getAttribute('data-date'))});
    frag.appendChild(c);
    cur2.setDate(cur2.getDate()+1);
  }
  grid.appendChild(frag);
  if(sum)sum.textContent='近 26 周：累计投递 '+totalA+' 家 · 推进节点 '+totalE+' 项 · 连续投递 '+streak+' 天';
}
function showHmDetail(ds){
  var d=hmData();
  var list=d.apps[ds]||[],ev=d.evs[ds]||[];
  var m=$('hmModal');if(!m)return;
  setText('hmDate',ds+'（投递 '+list.length+' 家 · 节点 '+ev.length+' 项）');
  var h='';
  list.forEach(function(a){h+='<div class="hmrow"><span class="tag ok">投递</span><b>'+esc(plain(a['公司']))+'</b><span class="hm-sub">'+esc(plain(a['岗位'])||'')+' · 当前：'+esc(appStage(a))+'</span></div>'});
  ev.forEach(function(x){h+='<div class="hmrow"><span class="tag" style="background:#fdf3e3;color:#d97706">'+esc(x.st)+'</span><b>'+esc(plain(x.a['公司']))+'</b><span class="hm-sub">'+esc(x.desc||'参加'+x.st)+'</span></div>'});
  if(!h)h='<div class="empty">这一天没有记录</div>';
  $('hmDetail').innerHTML=h;
  m.style.display='flex';
}
(function(){
  var m=$('hmModal');if(!m)return;
  $('hmClose').addEventListener('click',function(){m.style.display='none'});
  m.addEventListener('click',function(e){if(e.target===m)m.style.display='none'});
  document.addEventListener('keydown',function(e){if(e.key==='Escape')m.style.display='none'});
})();
""",
"autumn": """
MODS.push({refresh:function(){renderFilterFacets();renderJobs();},setup:function(){renderSelectOptions();},bind:function(){
  bindSubmitJob();
  $('at_q').addEventListener('input',function(){state.at_q=$('at_q').value.trim();renderJobs()});
  $('at_fSt').addEventListener('change',function(){state.at_fSt=$('at_fSt').value;renderJobs()});
  $('at_fBatchF').addEventListener('change',function(){state.at_fBatchF=$('at_fBatchF').value;renderJobs()});
  $('at_fCity').addEventListener('change',function(){state.at_fCity=$('at_fCity').value;renderJobs()});
  $('at_fCareer').addEventListener('change',function(){state.at_fCareer=$('at_fCareer').value;renderJobs()});
  $('at_fSort').addEventListener('change',function(){state.at_fSort=$('at_fSort').value;renderJobs()});
  Array.prototype.forEach.call(document.querySelectorAll('#at_batchChips .chip'),function(ch){
    ch.addEventListener('click',function(){state.batchMode=ch.getAttribute('data-mode');Array.prototype.forEach.call(document.querySelectorAll('#at_batchChips .chip'),function(x){x.className='chip'+(x===ch?' active':'')});renderJobs();});
  });
}});
""",
"soe": """
MODS.push({refresh:function(){renderFilterFacets();renderJobs();},setup:function(){renderSelectOptions();},bind:function(){
  bindSubmitJob();
  $('so_q').addEventListener('input',function(){state.so_q=$('so_q').value.trim();renderJobs()});
  $('so_fSt').addEventListener('change',function(){state.so_fSt=$('so_fSt').value;renderJobs()});
  $('so_fCity').addEventListener('change',function(){state.so_fCity=$('so_fCity').value;renderJobs()});
  $('so_fCareer').addEventListener('change',function(){state.so_fCareer=$('so_fCareer').value;renderJobs()});
  $('so_fSort').addEventListener('change',function(){state.so_fSort=$('so_fSort').value;renderJobs()});
}});
""",
"intern": """
MODS.push({refresh:function(){renderInterns();},setup:function(){renderSelectOptions();},bind:function(){
  bindSubmitIntern();
  bindFormCache('ir_internForm');
  $('ir_q').addEventListener('input',function(){state.ir_q=$('ir_q').value.trim();renderInterns()});
  $('ir_fSt').addEventListener('change',function(){state.ir_fSt=$('ir_fSt').value;renderInterns()});
  $('ir_fSort').addEventListener('change',function(){state.ir_fSort=$('ir_fSort').value;renderInterns()});
}});
""",
}

NAV_SINGLE = """
<nav class="tabbar">
  <div class="inner">
    <a class="logo" data-goto="overview" title="Job Seeker · 秋招求职工作台"><span class="lm">""" + bp.LOGO_SVG + """</span><span class="lw">Job <b>Seeker</b></span></a>
    <div class="sngroup">发现</div>
    <button type="button" class="tab" data-view="autumn">秋招岗位</button>
    <button type="button" class="tab" data-view="soe">央国企</button>
    <button type="button" class="tab" data-view="intern">实习直通</button>
    <div class="sngroup">我的</div>
    <button type="button" class="tab" data-view="today" data-sub="today">今日提醒</button>
    <button type="button" class="tab snsec" data-sec="apps">投递记录</button>
    <button type="button" class="tab snsec" data-sec="sched">日程安排</button>
    <button type="button" class="tab snsec" data-sec="agent">求职助理</button>
    <button type="button" class="tab snsec" data-sec="rag">个人知识库</button>
    <button type="button" class="tab snsec" data-sec="tasks">定时任务</button>
    <button type="button" class="tab snsec" data-sec="mail">招聘邮箱</button>
    <button type="button" class="tab" data-view="overview" data-sub="me">个人中心</button>
    <div class="sngroup">配置</div>
    <button type="button" class="tab snsec" data-sec="cfg">AI 配置</button>
    <div class="sync" id="syncBox"><span class="dot"></span><span id="syncTxt">连接中…</span></div>
    <div class="snops" id="snOps"></div>
  </div>
</nav>
"""

HEATMAP_HTML = """
<section id="hmSec">
  <h2 style="color:var(--green)"><svg viewBox="0 0 24 24" fill="none" stroke="#059669" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18M9 16l2 2 4-4"/></svg>投递热力图 · 每日足迹</h2>
  <div class="hmSum" id="hmSum"></div>
  <div class="hmWrap"><div class="hmGrid" id="hmGrid"></div></div>
  <div class="hmLegend">少
    <span class="sq" style="background:#ebedf0"></span><span class="sq" style="background:#9be9a8"></span><span class="sq" style="background:#40c463"></span><span class="sq" style="background:#30a14e"></span><span class="sq" style="background:#216e39"></span>多
    <span style="margin-left:10px;display:inline-flex;align-items:center;gap:5px"><span class="sq" style="background:#fff;box-shadow:inset 0 0 0 2px #fff,0 0 0 2px #d97706"></span>有笔试 / 面试 / Offer 节点</span>
    <span style="margin-left:10px">点击任意格子查看当天明细</span>
  </div>
</section>

<div id="hmModal" style="display:none;position:fixed;inset:0;background:rgba(15,23,42,.45);z-index:99;align-items:center;justify-content:center;padding:20px">
  <div style="background:#fff;border-radius:14px;max-width:560px;width:100%;max-height:70vh;overflow:auto;padding:18px;box-shadow:0 10px 30px rgba(15,23,42,.2)">
    <b id="hmDate" style="font-size:15px"></b>
    <div id="hmDetail" style="margin-top:8px"></div>
    <div style="display:flex;justify-content:flex-end;margin-top:10px"><button class="btn btn-gray btn-sm" id="hmClose">关闭</button></div>
  </div>
</div>
"""

CSS_EXTRA = """
nav.tabbar .tab{cursor:pointer;font-family:inherit}
.view{display:none}
.view.active{display:block}
/* ---- 投递热力图 ---- */
.hmSum{font-size:12px;color:var(--sub);margin-bottom:10px}
.hmWrap{overflow-x:auto;padding-bottom:2px}
.hmGrid{display:grid;grid-auto-flow:column;grid-template-rows:repeat(7,12px);gap:3px;width:max-content}
.hm-cell{width:12px;height:12px;border-radius:3px;background:#ebedf0;cursor:pointer}
.hm-cell:hover{outline:1.5px solid var(--pri);outline-offset:0}
.hm-cell.l1{background:#9be9a8}
.hm-cell.l2{background:#40c463}
.hm-cell.l3{background:#30a14e}
.hm-cell.l4{background:#216e39}
.hm-cell.ev{box-shadow:inset 0 0 0 2px #fff,0 0 0 2px #d97706}
.hmLegend{display:flex;align-items:center;gap:5px;margin-top:10px;font-size:11px;color:var(--sub);flex-wrap:wrap}
.hmLegend .sq{width:11px;height:11px;border-radius:3px;display:inline-block}
.hmrow{display:flex;align-items:center;gap:8px;padding:7px 0;border-bottom:1px solid var(--line);font-size:13px;flex-wrap:wrap}
.hmrow:last-child{border-bottom:0}
.hmrow b{font-size:13px}
.hmrow .hm-sub{color:var(--sub);font-size:12px}
@media (max-width:768px){.hm-cell{width:10px;height:10px}.hmGrid{grid-template-rows:repeat(7,10px);gap:2px}}
"""

BOOT_JS = r"""
var SEC_NAMES=['apps','sched','agent','rag','tasks','mail','cfg'];
function showView(name){
  if(SEC_NAMES.indexOf(name)>=0){
    Array.prototype.forEach.call(document.querySelectorAll('.view'),function(v){v.className='view'+(v.id==='view_overview'?' active':'')});
    Array.prototype.forEach.call(document.querySelectorAll('nav.tabbar .tab'),function(t){t.removeAttribute('aria-current')});
    if(window.ovSec)window.ovSec(name);
    try{history.replaceState(null,'','#'+name)}catch(e){}
    window.scrollTo(0,0);
    return;
  }
  var vn=name==='today'?'overview':name;
  Array.prototype.forEach.call(document.querySelectorAll('.view'),function(v){v.className='view'+(v.id==='view_'+vn?' active':'')});
  Array.prototype.forEach.call(document.querySelectorAll('nav.tabbar .tab'),function(t){if(t.getAttribute('data-view')===name){t.setAttribute('aria-current','page')}else{t.removeAttribute('aria-current')}});
  if((name==='today'||name==='overview')&&window.ovSub)window.ovSub(name==='today'?'today':'me');
  try{history.replaceState(null,'','#'+name)}catch(e){}
  window.scrollTo(0,0);
}
/* 必须挂到 window：侧栏分组的点击委托在 NAVSEC_JS（shared 段，作用域在本 IIFE 之外），
   它只认 window.showView；不挂的话从「秋招岗位/央国企/实习直通」点「个人知识库/定时任务」
   只会切容器显示、不会切视图，表现为侧栏高亮变了但内容没动。 */
window.showView=showView;
function bindTabs(){
  Array.prototype.forEach.call(document.querySelectorAll('nav.tabbar .tab'),function(t){t.addEventListener('click',function(){var v=t.getAttribute('data-view');if(!v)return;/* .snsec（data-sec）由 NAVSEC_JS 的委托处理 */showView(v)})});
  Array.prototype.forEach.call(document.querySelectorAll('[data-goto]'),function(a){a.addEventListener('click',function(e){e.preventDefault();showView(a.getAttribute('data-goto'))})});
  var h=(location.hash||'').replace('#','');
  showView(['overview','autumn','soe','intern','today'].concat(SEC_NAMES).concat(['me']).indexOf(h)>=0?h:'today');
}
function boot(){
  db=window.__SMART_PAGE__&&window.__SMART_PAGE__.database;
  bindIntelClose();
  bindExpress();
  $('lnkClose').addEventListener('click',function(){$('lnkModal').style.display='none'});
  $('lnkModal').addEventListener('click',function(e){if(e.target===$('lnkModal'))$('lnkModal').style.display='none'});
  bindTabs();
  if(!db){goOffline();return}
  MODS.forEach(function(m){m.bind&&m.bind()});
  /* 就绪链路抽成可重跑的 DB_READY：离线横幅的「重试连接」复用它，无需整页刷新 */
  DB_READY=function(){return initSchema(function(){MODS.forEach(function(m){m.setup&&m.setup()})})};
  DB_READY().catch(function(e){console.error('[database] 初始化失败:'+((e&&e.message)||String(e)));goOffline()});
}
if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',boot)}else{boot()}
"""


def extract(html):
    """Return (hero, wrap_body, script_js) from a built page."""
    i_nav_end = html.index("</nav>") + len("</nav>")
    i_wrap = html.index('<div class="wrap">')
    hero = html[i_nav_end:i_wrap].strip()
    i_lnk = html.index('<div id="lnkModal"')
    seg = html[i_wrap + len('<div class="wrap">'):i_lnk]
    seg = seg.strip()
    # drop leading offBanner (re-added once globally) and trailing wrap close
    seg = re.sub(r'^<div class="banner" id="offBanner">.*?</div>\s*', '', seg, flags=re.S)
    assert seg.endswith('</div>'), 'body should end with wrap close'
    seg = seg[: seg.rindex('</div>')]
    m = re.search(r'<script>(.*?)</script>', html, re.S)
    return hero, seg, m.group(1)


def prefix_ids(text, mod, is_js):
    p = PREFIX[mod]
    for x in IDS[mod]:
        if is_js:
            text = text.replace("$('%s')" % x, "$('%s_%s')" % (p, x))
            text = text.replace("setText('%s'" % x, "setText('%s_%s'" % (p, x))
            text = text.replace("fillSelect('%s'" % x, "fillSelect('%s_%s'" % (p, x))
            text = text.replace("bindFormCache('%s'" % x, "bindFormCache('%s_%s'" % (p, x))
            text = text.replace("'#%s" % x, "'#%s_%s" % (p, x))
            # indirect reference via pairs array: ['fCity',cities,'全部城市']
            text = text.replace("['%s'," % x, "['%s_%s'," % (p, x))
        else:
            text = text.replace('id="%s"' % x, 'id="%s_%s"' % (p, x))
    return text


def build_module_js(mod, page_js):
    p = PREFIX[mod]
    # namespace shared state fields
    for f in STATE_FIELDS:
        page_js = page_js.replace("state.%s" % f, "state.%s_%s" % (p, f))
    # dynamic funnel ids (overview)
    page_js = page_js.replace("$('fbar'", "$('ov_fbar'").replace("$('fcnt'", "$('ov_fcnt'")
    page_js = page_js.replace("'fbar'+i", "'ov_fbar'+i").replace("'fcnt'+i", "'ov_fcnt'+i")
    page_js = prefix_ids(page_js, mod, is_js=True)
    # drop old refreshAll definition
    page_js = page_js.replace(REFRESH_LINE[mod] + "\n", "")
    # drop trailing init() + goOffline()
    i = page_js.index("function init(){")
    page_js = page_js[:i].rstrip() + "\n"
    return "(function(){\n" + page_js + TAIL[mod] + "\n})();\n"


def build():
    pages = {k: getattr(bp, "page_%s" % k)(bp.URLS) for k in MODULES}
    shared_done = False
    module_blocks = []
    views = []
    for mod in MODULES:
        hero, body, js = extract(pages[mod])
        # shared js = everything up to end of reloadAll definition
        marker = "function reloadAll(){return loadData().then(function(){refreshAll()},function(){refreshAll()});}"
        idx = js.index(marker) + len(marker)
        if not shared_done:
            shared = js[:idx]
            shared_done = True
        module_js = js[idx:]
        # strip old boot tail
        cut = module_js.index("\nif(document.readyState==='loading')")
        module_js = module_js[:cut]
        # overview: module cards -> in-page goto
        if mod == "overview":
            for key in MODULES:
                body = re.sub(r'<a class="moduleCard[^"]*" target="_top" href="%s"' % re.escape(bp.URLS[key]),
                              '<a class="moduleCard" data-goto="%s"' % key, body)
            body = body.replace('<div id="hmAnchor"></div>', HEATMAP_HTML)
        body = prefix_ids(body, mod, is_js=False)
        module_blocks.append("/* ====== module: %s ====== */\n%s" % (mod, build_module_js(mod, module_js)))
        views.append('<div class="view" id="view_%s">\n%s\n%s\n</div>' % (mod, hero, body))

    glue = """
var MODS=[];
function refreshAll(){MODS.forEach(function(m){m.refresh()});}
function goOffline(){offline=true;setSync('off');$('offBanner').style.display='block';MODS.forEach(function(m){m.refresh&&m.refresh()});}
"""
    js_all = shared + "\n" + glue + "\n" + "\n".join(module_blocks) + "\n" + BOOT_JS + "\n})();"

    # 单页版是自洽的：deploy_pages.py 把同一个文件推到全部 4 个节点，视图靠页内 showView
    # 切换。所以合并版里不能残留任何指向生产资料库节点的深链 —— lint 的「demo 自包含」
    # 与「合并版无跨节点跳转」两条断言就是拦这个的（demo 也由本文件派生）。
    # build_pages.py 给每个独立页注入了 var PAGE_URLS={...}，独立页需要它做跨页跳转，
    # 合并版里全部视图都在同一页，这里把它降级成页内空链接。
    for _url in bp.URLS.values():
        js_all = js_all.replace(_url, "#")
    # 打分时「还没有简历档案：请先到总览台 → 个人中心 → 简历档案」的引导链接
    # （mtNoResume 里动态创建的 a.mgo）在合并版里改成切视图，别跳走
    js_all = js_all.replace(
        "a.href=(typeof PAGE_URLS!=='undefined'&&PAGE_URLS&&PAGE_URLS.overview)?PAGE_URLS.overview:'#';",
        "a.href='#';a.onclick=function(ev){ev.preventDefault();showView('overview');};")

    html = """<!DOCTYPE html>
<!-- 本工作台通过 WorkBuddy 资料库能力（library skill）搭建、存储和部署 -->
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<title>Job Seeker · 秋招求职工作台</title>
<link rel="icon" href="{favicon}">
<style>{css}{css_extra}</style>
</head>
<body class="navside">
{nav}
<div class="wrap">
<div class="banner" id="offBanner">离线模式：未连接到在线数据表，数据读写暂不可用。请通过资料库链接打开本页面。<button type="button" class="btn btn-sm" id="offRetry" style="margin-left:10px;cursor:pointer">重试连接</button></div>
{views}
</div>
{lnk}
{intel}
<script>{js}</script>
</body>
</html>
""".format(css=bp.CSS, css_extra=CSS_EXTRA, favicon=bp.FAVICON_DATA, nav=NAV_SINGLE, views="\n".join(views),
           lnk=bp.LNKMODAL_HTML, intel=bp.INTELMODAL_HTML, js=js_all)

    out1 = HERE.parent / "dist" / "00-总览台.html"
    out1.parent.mkdir(exist_ok=True)
    out1.write_text(html, encoding="utf-8")
    print("wrote dist/%s (%d bytes), %d modules" % (out1.name, len(html), len(MODULES)))


if __name__ == "__main__":
    build()
