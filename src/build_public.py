#!/usr/bin/env python3
"""把单页版构建成「公开版」：给任何访客用的求职工作台，隐私零外泄。

输入: build_single.py 产出的 dist/00-总览台.html + src/seed/seed.json（真实数据快照）
输出: dist/public/index.html

与 dist/site（私有独立站点）的区别:
1. **内嵌快照只保留秋招岗位表**。投递记录 apps / 实习私备注 interns / 收件箱 inbox
   一律不进产物 —— 那些是作者本人的隐私，site 版把它们灌进了每个访客浏览器。
2. **localStorage 命名空间隔离**：公开版用 `qc_*` 键，私有站点版用 `qz_*`，Demo 用
   `qiuzhao_demo_*`。三种形态在同一浏览器打开互不干扰。
3. **首次打开二选一**：访客自己决定「载入岗位库」还是「从空白开始，只记我的投递」。
   门闩 `qc_pubAsked` 记住选择，之后不再打扰。
4. 剔除岗位表里 5 条手工预置的「示例预置」条目（非牛客同步数据，属演示残留）。

为什么要派生这个文件而不是给 build_site.py 加 --public 分支：CI 门禁会重跑全部构建后
`git diff --exit-code -- dist`，要求既有产物字节完全一致。SITE_ADAPTER 是 raw 常量、
patch() 用固定正则取「第一个」script、main() 里 seed 是整份四表 —— 在这三处热路径插条件
分支极易改到既有产物。派生脚本把风险隔离在单文件内，也让 build_site.py 保持原样。
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).parent
SEED = HERE / 'seed' / 'seed.json'
# 全量快照不入库（含个人数据）；公开快照只含 jobs，入库供 CI 与本机兜底
SEED_PUBLIC = HERE / 'seed' / 'seed.public.json'

# 公开版不内嵌的表（作者隐私）。这些表在产物里既没有种子数据，也不会被灌进 localStorage。
PRIVATE_TABLES = ('apps', 'interns', 'inbox')
# 只从快照灌种的表
SEEDED_TABLES = ('jobs',)
# 手工预置的演示条目，公开版剔除
SAMPLE_SOURCE = '示例预置'

PUBLIC_ADAPTER = r"""
/* === PUBLIC ADAPTER（公开版：只带岗位库 + 访客自选起点） ================ */
(function(){
  // 公开版独占的 localStorage 命名空间：qc_（前缀见下面 PFX）
  var PFX='qc_';
  function loadLS(name){
    try { return JSON.parse(localStorage.getItem(PFX+name)||'[]'); } catch(e){ return []; }
  }
  function saveLS(name,rows){
    try { localStorage.setItem(PFX+name, JSON.stringify(rows)); } catch(e){}
  }
  function loadSchema(){
    try { return JSON.parse(localStorage.getItem(PFX+'schema')||'null')||window.__SITE_SCHEMA__; }
    catch(e){ return window.__SITE_SCHEMA__; }
  }
  function loadGone(){
    try { return JSON.parse(localStorage.getItem(PFX+'seedGone')||'[]'); } catch(e){ return []; }
  }
  function saveGone(a){
    try { localStorage.setItem(PFX+'seedGone', JSON.stringify(a.slice(-3000))); } catch(e){}
  }
  // 取字段纯文本（select 存的是 {text,id} 对象，text 存的是字符串）
  function plain(v){
    if(v==null)return '';
    if(typeof v==='object')return String(v.text||v.value||v.name||'');
    return String(v);
  }
  // 稳定去重键：岗位表优先牛客ID（公司改名也能对上）
  function keyOf(n,r){
    if(n==='jobs'){
      var id=plain(r['牛客ID']);
      return id ? ('nc:'+id) : (plain(r['公司']) ? 'co:'+plain(r['公司']) : '');
    }
    return '';
  }
  function mkRec(r){
    var c={};Object.keys(r).forEach(function(k){c[k]=r[k]});
    if(!c._id){var id='seed_'+Math.random().toString(36).slice(2,10)+'_'+Math.floor(Math.random()*1e6);c._id=id;c.record_id=c.record_id||id;c.id=c.id||id;}
    return c;
  }
  // 四张表的「名字」必须全部登记：fakeDb 靠 loadSchema()[name].dbid 建 id→表名 的映射，
  // 少一个名字，主逻辑里带该 databaseId 的 fetch 就会走 nameOf 的回落分支（names[0]），
  // 于是投递记录/实习/收件箱会全部读出岗位数据。真正控制「灌不灌种子」的是 SEEDED。
  var NAMES=['jobs','apps','interns','inbox'];
  var SEEDED=['jobs'];
  function fakeDb(names){
    var map={};
    names.forEach(function(n){ map[(loadSchema()[n]||{}).dbid||n]=n; });
    function nameOf(opts){
      var id=(opts&&opts.databaseId)||'';
      return Object.prototype.hasOwnProperty.call(map,id) ? map[id] : names[0];
    }
    function nextId(){ return 'rec_'+Date.now()+'_'+Math.floor(Math.random()*1e6); }
    return {
      query:function(opts){
        return Promise.resolve({results:loadLS(nameOf(opts)),hasMore:false,nextCursor:null});
      },
      addRecord:function(opts){
        var n=nameOf(opts), rows=loadLS(n), id=nextId();
        var rec={_id:id,record_id:id,id:id};
        Object.keys(opts.properties||{}).forEach(function(k){rec[k]=opts.properties[k];});
        rows.push(rec); saveLS(n,rows);
        return Promise.resolve({_id:id,record_id:id});
      },
      updateRecord:function(opts){
        var n=nameOf(opts), rows=loadLS(n);
        for(var i=0;i<rows.length;i++){
          if((rows[i]._id||rows[i].record_id)===opts.recordId){
            Object.keys(opts.properties||{}).forEach(function(k){rows[i][k]=opts.properties[k]});
            break;
          }
        }
        saveLS(n,rows);
        return Promise.resolve({ok:true});
      },
      deleteRecord:function(opts){
        var n=nameOf(opts), gone=loadGone();
        var rows=loadLS(n).filter(function(r){
          if((r._id||r.record_id)!==opts.recordId) return true;
          var k=keyOf(n,r); if(k) gone.push(k);   // 记住删过的快照条目，下次同步不再塞回来
          return false;
        });
        saveLS(n,rows); saveGone(gone);
        return Promise.resolve({ok:true});
      },
      getSchema:function(opts){
        var s=loadSchema()[nameOf(opts)]||{};
        var props=[];
        Object.keys(s.options||{}).forEach(function(k){
          props.push({name:k,type:'select',config:{options:s.options[k]||[]}});
        });
        return Promise.resolve({properties:props});
      }
    };
  }
  window.__SMART_PAGE__={database:fakeDb(NAMES)};

  var SYNC_ADDED=0, SYNC_FIRST=false;
  // 与内置快照对账：只补「快照里有、本机没有」的岗位，不动你自己的投递状态/备注，
  // 也不复活你手动删掉过的条目。公开版只有 jobs 参与对账（SEEDED）。
  function syncSeed(){
    var seed=window.__SITE_SEED__||{};
    var gone={}; loadGone().forEach(function(k){gone[k]=1});
    var first=!localStorage.getItem(PFX+'seeded');
    var added=0;
    SEEDED.forEach(function(n){
      var rows=first?[]:loadLS(n);
      var have={};
      rows.forEach(function(r){var k=keyOf(n,r);if(k)have[k]=1;});
      (seed[n]||[]).forEach(function(r){
        var k=keyOf(n,r);
        if(!k){ if(first) rows.push(mkRec(r)); return; }
        if(have[k]||gone[k])return;
        rows.push(mkRec(r)); have[k]=1; added++;
      });
      saveLS(n,rows);
    });
    localStorage.setItem(PFX+'seeded',seed.exportedAt||'1');
    SYNC_ADDED=added; SYNC_FIRST=first;
    return added;
  }
  // 首次打开的起点选择：门闩 qc_pubAsked = 'seed' | 'empty'，未设 = 还没问过。
  // 注意 syncSeed 必须在 DOM 之前决策，所以这里先读门闩再决定灌不灌；
  // 没问过时先不灌，等访客在弹层里选完再灌（选完 reload，下次进这就直接灌了）。
  function asked(){ try{ return localStorage.getItem(PFX+'pubAsked'); }catch(e){ return null; } }
  (function(){
    var c=asked();
    if(c==='seed') syncSeed();
    // c==='empty'：什么都不灌，岗位库保持空；c===null：等弹层
  })();
  var sch=loadSchema();
  window.__SITE_OPTS__={};
  NAMES.forEach(function(n){ window.__SITE_OPTS__[n]=(sch[n]||{}).options||{}; });
  // 备份 / 恢复 / 重置 工具条
  function collect(){
    var out={version:1,at:new Date().toISOString(),tables:{},storage:{}};
    NAMES.forEach(function(n){ out.tables[n]=loadLS(n); });
    for(var i=0;i<localStorage.length;i++){
      var k=localStorage.key(i);
      if(k&&(k.indexOf('wb_')===0||k.indexOf(PFX)===0)) out.storage[k]=localStorage.getItem(k);
    }
    return out;
  }
  function download(obj,name){
    var blob=new Blob([JSON.stringify(obj)],{type:'application/json'});
    var a=document.createElement('a');
    a.href=URL.createObjectURL(blob);a.download=name;
    document.body.appendChild(a);a.click();
    setTimeout(function(){URL.revokeObjectURL(a.href);a.remove()},500);
  }
  function doExport(){
    var d=new Date();
    function p(n){return (n<10?'0':'')+n}
    download(collect(),'JobSeeker公开版备份_'+d.getFullYear()+p(d.getMonth()+1)+p(d.getDate())+'.json');
  }
  function doImport(){
    var inp=document.createElement('input');
    inp.type='file';inp.accept='.json';
    inp.onchange=function(){
      var f=inp.files&&inp.files[0];if(!f)return;
      var fr=new FileReader();
      fr.onload=function(){
        try{
          var d=JSON.parse(String(fr.result));
          var t=d.tables||{};
          NAMES.forEach(function(n){ if(t[n]) saveLS(n,t[n]); });
          var st=d.storage||{};
          Object.keys(st).forEach(function(k){
            if((k.indexOf('wb_')===0||k.indexOf(PFX)===0)&&k!==PFX+'seeded'&&k!==PFX+'pubAsked'){try{localStorage.setItem(k,st[k])}catch(e){}}
          });
          alert('导入完成，页面将刷新');
          location.reload();
        }catch(e){alert('文件格式不对，导入失败')}
      };
      fr.readAsText(f);
    };
    inp.click();
  }
  function doReset(){
    if(!confirm('用最新岗位快照覆盖本机岗位库？\n你自己加的投递记录不受影响，建议先导出备份。'))return;
    var seed=window.__SITE_SEED__||{};
    SEEDED.forEach(function(n){
      var rows=(seed[n]||[]).map(function(r){
        var c={};Object.keys(r).forEach(function(k){c[k]=r[k]});
        if(!c._id){var id='seed_'+Math.random().toString(36).slice(2,10);c._id=id;c.record_id=c.record_id||id;c.id=c.id||id;}
        return c;
      });
      saveLS(n,rows);
    });
    saveGone([]);
    localStorage.setItem(PFX+'seeded',seed.exportedAt||'1');
    location.reload();
  }
  // 首次打开的起点选择弹层
  function askOnce(){
    var seedCnt=((window.__SITE_SEED__||{}).jobs||[]).length;
    var mask=document.createElement('div');
    mask.id='qcAskMask';
    mask.style.cssText='position:fixed;inset:0;z-index:99999;background:rgba(15,23,42,.55);display:flex;align-items:center;justify-content:center;padding:20px;transform:translateZ(0)';
    var card=document.createElement('div');
    card.style.cssText='background:#fff;border-radius:3px;border-top:4px solid #0b5cff;max-width:440px;width:100%;padding:22px 22px 18px;box-shadow:0 12px 40px rgba(15,23,42,.28)';
    card.innerHTML='<div style="font-size:16px;font-weight:800;margin-bottom:6px">欢迎使用 Job Seeker</div>'
      +'<div style="font-size:13px;color:#64748b;line-height:1.7;margin-bottom:16px">这是一份可以自己用的求职工作台。你的数据全部保存在<b>你自己浏览器</b>里，不会上传到任何服务器。<br>先选一个起点：</div>'
      +'<button type="button" id="qcPickSeed" style="display:block;width:100%;text-align:left;border:1px solid #b9cdfd;background:#e8efff;border-radius:0;padding:12px 14px;cursor:pointer;font-family:inherit;margin-bottom:10px">'
      +'<b style="font-size:14px;color:#0b5cff">载入岗位库</b><span style="font-size:12px;color:#64748b;display:block;margin-top:3px">内置 '+seedCnt+' 条牛客校招岗位，按截止日期跟进</span></button>'
      +'<button type="button" id="qcPickEmpty" style="display:block;width:100%;text-align:left;border:1px solid #d7dee8;background:#fff;border-radius:0;padding:12px 14px;cursor:pointer;font-family:inherit">'
      +'<b style="font-size:14px;color:#0f172a">从空白开始</b><span style="font-size:12px;color:#64748b;display:block;margin-top:3px">岗位库留空，只记我自己的投递记录</span></button>'
      +'<div style="font-size:11.5px;color:#94a3b8;margin-top:12px;line-height:1.6">之后可以在侧栏底部「重置为最新快照」里重新载入岗位库。</div>';
    mask.appendChild(card);
    // 弹层必须追加到 body 末尾盖住整页；侧栏底部操作区由 mountOps 注入 #snOps。
    document.body.appendChild(mask);
    function pick(v,empty){
      try{ localStorage.setItem(PFX+'pubAsked',v); }catch(e){}
      if(empty){ saveLS('jobs',[]); localStorage.setItem(PFX+'seeded','1'); }
      location.reload();
    }
    card.querySelector('#qcPickSeed').onclick=function(){ pick('seed',false) };
    card.querySelector('#qcPickEmpty').onclick=function(){ pick('empty',true) };
  }
  // 侧栏底部：数据操作（导出 / 导入 / 重置），挂进 nav.tabbar .inner 末尾的 #snOps
  function mountOps(note){
    var host=document.getElementById('snOps');
    if(!host)return;
    var tip=SYNC_ADDED>0?('（'+(SYNC_FIRST?'已载入 ':'本次新增 ')+SYNC_ADDED+' 个岗位）'):'';
    host.innerHTML='<div class="snote">'+note+tip+'</div>'
      +'<button type="button" class="so" id="qcExp">导出备份</button>'
      +'<button type="button" class="so pri" id="qcImp">导入备份</button>'
      +'<button type="button" class="so danger" id="qcRst">重置为最新快照</button>';
    var e=document.getElementById('qcExp');if(e)e.onclick=doExport;
    var i2=document.getElementById('qcImp');if(i2)i2.onclick=doImport;
    var r2=document.getElementById('qcRst');if(r2)r2.onclick=doReset;
  }
  document.addEventListener('DOMContentLoaded',function(){
    mountOps('数据保存在你的浏览器，不上传服务器');
    if(!asked()) askOnce();
  });
})();
/* === END PUBLIC ADAPTER =============================================== */

"""


def build_options():
    """从 canonical schema 文件抽取 select 选项（text+id），供下拉与筛选使用。

    四张表的 name/dbid 骨架必须全留 —— fakeDb 靠 loadSchema()[name].dbid 建映射，
    砍掉哪张表的骨架，主逻辑里带该 databaseId 的 fetch 就会回落读成岗位数据。
    但 options 只给「公开版真正会用到的」：岗位表全部 + 投递表的当前阶段（纯枚举、
    不含隐私，让访客自记投递时下拉可用）。实习/收件箱不内嵌选项。
    """

    def props_of(fname):
        p = HERE / fname
        if not p.exists():
            return {}
        d = json.loads(p.read_text(encoding='utf-8'))
        return {k: ((v or {}).get('select') or {}).get('options') or []
                for k, v in (d.get('properties') or {}).items()}

    autumn = props_of('canonical_autumn.json')
    overview = props_of('canonical_overview.json')
    job_opts = {k: autumn[k] for k in ('批次', '优先级', '投递状态', '来源') if autumn.get(k)}
    apps_opts = {}
    if overview.get('当前阶段'):
        apps_opts['当前阶段'] = overview['当前阶段']
    return {
        'jobs':    {'name': 'jobs',    'dbid': 'JOBS_ID_FAKE',   'options': job_opts},
        'apps':    {'name': 'apps',    'dbid': 'APPS_ID_FAKE',   'options': apps_opts},
        'interns': {'name': 'interns', 'dbid': 'INTERN_ID_FAKE', 'options': {}},
        'inbox':   {'name': 'inbox',   'dbid': 'INBOX_ID_FAKE',  'options': {}},
    }


def patch(src):
    s = src.read_text(encoding='utf-8')
    # 4 个真实 databaseId 一律替换成 FAKE：即使公开版只内嵌岗位表，
    # 也要抹掉投递/实习/收件箱三张隐私表的真实 id
    for real, fake in (("GgZ71tywhs4HEZytFSqXTP", "JOBS_ID_FAKE"),
                       ("oBGkMFTv9Xv4Xn5gFOK18S", "APPS_ID_FAKE"),
                       ("tgH8096uENTaIj8RSY9qm5", "INTERN_ID_FAKE"),
                       ("EdCHnKtjZIXEw37tUmvhqL", "INBOX_ID_FAKE")):
        s = s.replace(real, fake)
    m = re.search(r'<script>(.*?)</script>', s, re.S)
    if not m:
        raise SystemExit('未找到内联 script')
    original = m.group(1)
    injected = PUBLIC_ADAPTER + original
    injected = injected.replace(
        "ss.forEach(function(schema){(schema.properties||[]).forEach(function(f){if((f.type==='select'||f.type==='multi_select')&&f.config&&f.config.options){OPTS[f.name]=f.config.options}})});",
        "if(window.__SITE_OPTS__){Object.keys(window.__SITE_OPTS__).forEach(function(n){Object.keys(window.__SITE_OPTS__[n]).forEach(function(k){OPTS[k]=window.__SITE_OPTS__[n][k]})})}else{ss.forEach(function(schema){(schema.properties||[]).forEach(function(f){if((f.type==='select'||f.type==='multi_select')&&f.config&&f.config.options){OPTS[f.name]=f.config.options}})})};"
    )
    s = s[:m.start()] + '<script>' + injected + '</script>' + s[m.end():]
    return s


def build_public_seed(full):
    """公开版快照：只留岗位表，并剔除手工预置的示例条目。

    seed 里的「来源」是纯字符串（text 字段导出的形态），不是 {text,id} 对象；
    这里两种形态都兼容，免得日后导出格式变了静默漏过滤。
    """
    jobs = []
    for r in full.get('jobs') or []:
        src = r.get('来源')
        if isinstance(src, dict):
            src = src.get('text')
        if src == SAMPLE_SOURCE:
            continue
        jobs.append(r)
    return {'exportedAt': full.get('exportedAt'), 'jobs': jobs}, jobs


def main():
    src = SEED if SEED.exists() else SEED_PUBLIC
    if not src.exists():
        raise SystemExit(
            '缺少 src/seed/seed.json（全量）与 src/seed/seed.public.json（公开），'
            '先跑 export_seed.py 或 daily_sync.py')
    full = json.loads(src.read_text(encoding='utf-8'))
    seed, jobs = build_public_seed(full)
    schema = build_options()
    head = ('<script>window.__SITE_SEED__=' + json.dumps(seed, ensure_ascii=False)
            + ';window.__SITE_SCHEMA__=' + json.dumps(schema, ensure_ascii=False) + ';</script>\n')
    html = patch(HERE.parent / 'dist' / '00-总览台.html')
    html = html.replace('<script>', head + '<script>', 1)
    # favicon 由单页版 head 内联（品牌 Logo 的 data URI），站点层不再覆盖
    html = html.replace('<title>Job Seeker · 秋招求职工作台</title>',
                        '<title>Job Seeker · 秋招岗位与投递管理台（公开版）</title>', 1)
    public_dir = HERE.parent / 'dist' / 'public'
    public_dir.mkdir(parents=True, exist_ok=True)
    out = public_dir / 'index.html'
    out.write_text(html, encoding='utf-8')
    dropped = len(full.get('jobs') or []) - len(jobs)
    print('wrote dist/public/index.html, %d bytes (jobs=%d，剔除示例 %d 条；'
          '未内嵌 %s；seed=%s)'
          % (len(html), len(jobs), dropped, '/'.join(PRIVATE_TABLES), seed.get('exportedAt')))


if __name__ == '__main__':
    main()
