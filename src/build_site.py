#!/usr/bin/env python3
"""把单页版构建成「独立网站」：不依赖资料库壳，任何浏览器直接打开即用。

输入: build_single.py 产出的 dist/00-总览台.html + src/seed/seed.json（真实数据快照）
输出: dist/site/index.html

与 demo 的区别:
- 种子数据是资料库导出的真实数据（jobs/apps/interns/inbox）
- 没有演示横幅，改为「数据说明 + 导出备份 / 导入备份 / 重置为最新快照」工具条
- 数据存本机浏览器（qz_* 键），可导出 JSON 备份、换设备导入
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).parent
SEED = HERE / 'seed' / 'seed.json'
# 全量快照含作者个人投递/实习/收件箱记录，仓库是公开的 → 不入库。
# 公开快照（只含岗位）入库，供 CI 构建以及「本机没有全量快照」时兜底。
SEED_PUBLIC = HERE / 'seed' / 'seed.public.json'

SITE_ADAPTER = r"""
/* === STANDALONE SITE ADAPTER（独立站点：本机存储 + 备份） ============ */
(function(){
  function loadLS(name){
    try { return JSON.parse(localStorage.getItem('qz_'+name)||'[]'); } catch(e){ return []; }
  }
  function saveLS(name,rows){
    try { localStorage.setItem('qz_'+name, JSON.stringify(rows)); } catch(e){}
  }
  function loadSchema(){
    try { return JSON.parse(localStorage.getItem('qz_schema')||'null')||window.__SITE_SCHEMA__; }
    catch(e){ return window.__SITE_SCHEMA__; }
  }
  function loadGone(){
    try { return JSON.parse(localStorage.getItem('qz_seedGone')||'[]'); } catch(e){ return []; }
  }
  function saveGone(a){
    try { localStorage.setItem('qz_seedGone', JSON.stringify(a.slice(-3000))); } catch(e){}
  }
  // 取字段纯文本（select 存的是 {text,id} 对象，text 存的是字符串）
  function plain(v){
    if(v==null)return '';
    if(typeof v==='object')return String(v.text||v.value||v.name||'');
    return String(v);
  }
  // 稳定去重键：岗位表优先牛客ID（公司改名也能对上），实习表用公司+岗位名
  function keyOf(n,r){
    if(n==='jobs'){
      var id=plain(r['牛客ID']);
      return id ? ('nc:'+id) : (plain(r['公司']) ? 'co:'+plain(r['公司']) : '');
    }
    if(n==='interns'){
      return plain(r['公司']) ? ('co:'+plain(r['公司'])+'|'+plain(r['岗位名称'])) : '';
    }
    return '';
  }
  function mkRec(r){
    var c={};Object.keys(r).forEach(function(k){c[k]=r[k]});
    if(!c._id){var id='seed_'+Math.random().toString(36).slice(2,10)+'_'+Math.floor(Math.random()*1e6);c._id=id;c.record_id=c.record_id||id;c.id=c.id||id;}
    return c;
  }
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
  var NAMES=['jobs','apps','interns','inbox'];
  window.__SMART_PAGE__={database:fakeDb(NAMES)};
  // 每次打开都与内置快照对账：只补「快照里有、本机没有」的岗位，
  // 不动你已有的投递状态/备注，也不复活你手动删掉过的条目
  var SYNC_ADDED=0, SYNC_FIRST=false;
  function syncSeed(){
    var seed=window.__SITE_SEED__||{};
    var gone={}; loadGone().forEach(function(k){gone[k]=1});
    var first=!localStorage.getItem('qz_seeded');
    var added=0;
    NAMES.forEach(function(n){
      var rows=first?[]:loadLS(n);
      var have={};
      rows.forEach(function(r){var k=keyOf(n,r);if(k)have[k]=1;});
      (seed[n]||[]).forEach(function(r){
        var k=keyOf(n,r);
        if(!k){ if(first) rows.push(mkRec(r)); return; }  // apps/inbox 无稳定键，仅首次灌
        if(have[k]||gone[k])return;
        rows.push(mkRec(r)); have[k]=1; if(n==='jobs'||n==='interns') added++;
      });
      saveLS(n,rows);
    });
    localStorage.setItem('qz_seeded',seed.exportedAt||'1');
    SYNC_ADDED=added; SYNC_FIRST=first;
    return added;
  }
  syncSeed();
  var sch=loadSchema();
  window.__SITE_OPTS__={};
  NAMES.forEach(function(n){ window.__SITE_OPTS__[n]=(sch[n]||{}).options||{}; });
  // 备份 / 恢复 / 重置 工具条
  function collect(){
    var out={version:1,at:new Date().toISOString(),tables:{},storage:{}};
    NAMES.forEach(function(n){ out.tables[n]=loadLS(n); });
    for(var i=0;i<localStorage.length;i++){
      var k=localStorage.key(i);
      if(k&&(k.indexOf('wb_')===0||k.indexOf('qz_')===0)) out.storage[k]=localStorage.getItem(k);
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
    download(collect(),'JobSeeker备份_'+d.getFullYear()+p(d.getMonth()+1)+p(d.getDate())+'.json');
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
            if((k.indexOf('wb_')===0||k.indexOf('qz_')===0)&&k!=='qz_seeded'){try{localStorage.setItem(k,st[k])}catch(e){}}
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
    if(!confirm('用最新岗位快照覆盖本机数据？\n你自己加的投递记录、收件箱、任务等也会被清掉，建议先导出备份。'))return;
    var seed=window.__SITE_SEED__||{};
    NAMES.forEach(function(n){
      var rows=(seed[n]||[]).map(function(r){
        var c={};Object.keys(r).forEach(function(k){c[k]=r[k]});
        if(!c._id){var id='seed_'+Math.random().toString(36).slice(2,10);c._id=id;c.record_id=c.record_id||id;c.id=c.id||id;}
        return c;
      });
      saveLS(n,rows);
    });
    saveGone([]);
    localStorage.setItem('qz_seeded',seed.exportedAt||'1');
    location.reload();
  }
  // 侧栏底部：数据操作（导出 / 导入 / 重置），挂进 nav.tabbar .inner 末尾的 #snOps
  function mountOps(note){
    var host=document.getElementById('snOps');
    if(!host)return;
    var tip=SYNC_ADDED>0?('（'+(SYNC_FIRST?'已载入 ':'本次新增 ')+SYNC_ADDED+' 个岗位）'):'';
    host.innerHTML='<div class="snote">'+note+tip+'</div>'
      +'<button type="button" class="so" id="qzExp">导出备份</button>'
      +'<button type="button" class="so pri" id="qzImp">导入备份</button>'
      +'<button type="button" class="so danger" id="qzRst">重置为最新快照</button>';
    var e=document.getElementById('qzExp');if(e)e.onclick=doExport;
    var i2=document.getElementById('qzImp');if(i2)i2.onclick=doImport;
    var r2=document.getElementById('qzRst');if(r2)r2.onclick=doReset;
  }
  document.addEventListener('DOMContentLoaded',function(){
    mountOps('数据保存在本机浏览器，不上传服务器');
  });
})();
/* === END STANDALONE SITE ADAPTER ====================================== */

"""


def build_options():
    """从 canonical schema 文件抽取 select 选项（text+id），供下拉与筛选使用。"""

    def props_of(fname):
        p = HERE / fname
        if not p.exists():
            return {}
        d = json.loads(p.read_text(encoding='utf-8'))
        return {k: ((v or {}).get('select') or {}).get('options') or []
                for k, v in (d.get('properties') or {}).items()}

    autumn = props_of('canonical_autumn.json')
    intern = props_of('canonical_intern.json')
    overview = props_of('canonical_overview.json')
    job_opts = {k: autumn[k] for k in ('批次', '优先级', '投递状态', '来源') if autumn.get(k)}
    intern_opts = {k: intern[k] for k in ('投递状态', '来源') if intern.get(k)}
    apps_opts = {}
    if overview.get('当前阶段'):
        apps_opts['当前阶段'] = overview['当前阶段']
    inbox_opts = {}
    for k in ('类型', '来源', '置信度'):
        if overview.get(k):
            inbox_opts[k] = overview[k]
    inbox_opts['状态'] = [{'text': '待确认', 'id': 'st0'}, {'text': '已确认', 'id': 'st1'}, {'text': '已忽略', 'id': 'st2'}]
    return {
        'jobs': {'name': 'jobs', 'dbid': 'JOBS_ID_FAKE', 'options': job_opts},
        'apps': {'name': 'apps', 'dbid': 'APPS_ID_FAKE', 'options': apps_opts},
        'interns': {'name': 'interns', 'dbid': 'INTERN_ID_FAKE', 'options': intern_opts},
        'inbox': {'name': 'inbox', 'dbid': 'INBOX_ID_FAKE', 'options': inbox_opts},
    }


def patch(src):
    s = src.read_text(encoding='utf-8')
    for real, fake in (("GgZ71tywhs4HEZytFSqXTP", "JOBS_ID_FAKE"),
                       ("oBGkMFTv9Xv4Xn5gFOK18S", "APPS_ID_FAKE"),
                       ("tgH8096uENTaIj8RSY9qm5", "INTERN_ID_FAKE"),
                       ("EdCHnKtjZIXEw37tUmvhqL", "INBOX_ID_FAKE")):
        s = s.replace(real, fake)
    m = re.search(r'<script>(.*?)</script>', s, re.S)
    if not m:
        raise SystemExit('未找到内联 script')
    original = m.group(1)
    injected = SITE_ADAPTER + original
    injected = injected.replace(
        "ss.forEach(function(schema){(schema.properties||[]).forEach(function(f){if((f.type==='select'||f.type==='multi_select')&&f.config&&f.config.options){OPTS[f.name]=f.config.options}})});",
        "if(window.__SITE_OPTS__){Object.keys(window.__SITE_OPTS__).forEach(function(n){Object.keys(window.__SITE_OPTS__[n]).forEach(function(k){OPTS[k]=window.__SITE_OPTS__[n][k]})})}else{ss.forEach(function(schema){(schema.properties||[]).forEach(function(f){if((f.type==='select'||f.type==='multi_select')&&f.config&&f.config.options){OPTS[f.name]=f.config.options}})})};"
    )
    s = s[:m.start()] + '<script>' + injected + '</script>' + s[m.end():]
    return s


def main():
    src = SEED if SEED.exists() else SEED_PUBLIC
    if not src.exists():
        raise SystemExit(
            '缺少 src/seed/seed.json（全量）与 src/seed/seed.public.json（公开），'
            '先跑 export_seed.py 或 daily_sync.py')
    if src is SEED_PUBLIC:
        print('[note] 本机无全量快照，回落到 seed.public.json：'
              '站点版只含岗位，没有投递/实习记录')
    seed = json.loads(src.read_text(encoding='utf-8'))
    schema = build_options()
    head = ('<script>window.__SITE_SEED__=' + json.dumps(seed, ensure_ascii=False)
            + ';window.__SITE_SCHEMA__=' + json.dumps(schema, ensure_ascii=False) + ';</script>\n')
    html = patch(HERE.parent / 'dist' / '00-总览台.html')
    html = html.replace('<script>', head + '<script>', 1)
    # favicon 由单页版 head 内联（品牌 Logo 的 data URI），站点层不再覆盖；
    # 独立站点用更完整的商品名做标题
    html = html.replace('<title>Job Seeker · 秋招求职工作台</title>',
                        '<title>Job Seeker · 秋招岗位与投递管理台</title>', 1)
    site_dir = HERE.parent / 'dist' / 'site'
    site_dir.mkdir(parents=True, exist_ok=True)
    out = site_dir / 'index.html'
    out.write_text(html, encoding='utf-8')
    print('wrote dist/site/index.html, %d bytes (jobs=%d apps=%d interns=%d inbox=%d, seed=%s)'
          % (len(html), len(seed.get('jobs', [])), len(seed.get('apps', [])),
             len(seed.get('interns', [])), len(seed.get('inbox', [])), seed.get('exportedAt')))


if __name__ == '__main__':
    main()
