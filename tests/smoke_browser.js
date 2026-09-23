/**
 * 生产单文件的浏览器冒烟测试：注入 mock SDK，跑通完整初始化链路。
 * 用法: node tests/smoke_browser.js
 */
const path = require('path');
const fs = require('fs');
const { chromium } = require('playwright-core');

const ROOT = path.resolve(__dirname, '..');
const TARGET = path.join(ROOT, 'dist', process.env.PAGE || '00-总览台.html');

// 造数据：秋招 620 条（跨多页）、投递跟踪 6 条、实习 40 条
function buildMock() {
  const jobs = [];
  const cities = ['北京', '成都', '天津', '上海', '深圳'];
  const careers = ['人工智能/算法', '后端开发', '前端开发', '数据', '测试'];
  const batches = ['27秋招', '27暑期实习', '其他'];
  for (let i = 0; i < 620; i++) {
    const d = new Date(2026, 8, 20 + (i % 40));
    jobs.push({
      record_id: 'job' + i,
      公司: '测试公司' + i,
      批次: batches[i % 3],
      岗位方向: careers[i % 5],
      工作地点: cities[i % 5],
      优先级: i % 3 === 0 ? 'P1' : 'P2',
      投递状态: i % 7 === 0 ? '已投递' : '待投递',
      网申开始: '2026-09-01T00:00:00Z',
      截止日期: d.toISOString(),
      投递链接: [{ text: '网申入口', link: 'https://example.com/' + i }],
      来源: '牛客校招日程',
      备注: '测试评价',
      牛客ID: String(800 + i),
    });
  }
  const apps = [];
  for (let i = 0; i < 6; i++) {
    apps.push({
      record_id: 'app' + i,
      公司: '投递公司' + i,
      岗位: '大模型算法',
      当前阶段: ['已投递', '笔试', '一面', 'Offer', '感谢信', '已终止'][i],
      投递日期: new Date(2026, 8, 1 + i).toISOString(),
      下次节点: new Date(2026, 8, 14 + i).toISOString(),
      节点说明: '节点说明' + i,
      复盘笔记: '',
      相关链接: [{ text: '链接', link: 'https://example.com/app' + i }],
    });
  }
  const interns = [];
  for (let i = 0; i < 40; i++) {
    interns.push({
      record_id: 'int' + i,
      公司: '实习公司' + i,
      岗位名称: '算法实习生',
      薪资: '',
      工作地点: '成都',
      岗位要求: '27届日常实习',
      投递状态: '待投递',
      网申开始: '2026-09-05T00:00:00Z',
      截止日期: new Date(2026, 8, 18 + (i % 30)).toISOString(),
      投递链接: [{ text: '投递入口', link: 'https://example.com/intern' + i }],
      来源: '牛客校招日程',
      备注: '牛客同步',
      牛客ID: String(900 + i),
    });
  }
  const inbox = [
    { record_id: 'ibx0', 公司: '字节跳动', 类型: '笔试', 事项时间: new Date(2026, 8, 20).toISOString(), 原文摘要: '笔试邀请：9月20日 14:00 在线测评', 发件人: 'noreply@bytedance.com', 来源: '邮件', 状态: '待确认', 置信度: '高' },
    { record_id: 'ibx1', 公司: '美团', 类型: '面试', 事项时间: new Date(2026, 8, 22).toISOString(), 原文摘要: '面试邀请：9月22日 10:00 视频面试', 发件人: 'careers@meituan.com', 来源: '邮件', 状态: '待确认', 置信度: '高' },
    { record_id: 'ibx2', 公司: '百度', 类型: 'Offer', 事项时间: new Date(2026, 8, 10).toISOString(), 原文摘要: '录用意向通知', 发件人: 'offer@baidu.com', 来源: '邮件', 状态: '已确认', 置信度: '高' },
  ];
  return { jobs, apps, interns, inbox };
}

const DATA = buildMock();
const SCHEMA = {
  GgZ71tywhs4HEZytFSqXTP: { properties: [
    '公司', '批次', '岗位方向', '工作地点', '优先级', '投递状态', '网申开始', '截止日期',
    '投递链接', '来源', '备注', '牛客ID',
  ].map((n) => ({ name: n, type: n === '投递状态' || n === '优先级' || n === '批次' ? 'select' : 'text' })) },
  oBGkMFTv9Xv4Xn5gFOK18S: { properties: ['公司', '岗位', '当前阶段', '投递日期', '下次节点', '节点说明', '复盘笔记', '相关链接'].map((n) => ({ name: n, type: 'text' })) },
  tgH8096uENTaIj8RSY9qm5: { properties: ['公司', '岗位名称', '薪资', '工作地点', '岗位要求', '投递状态', '网申开始', '截止日期', '投递链接', '来源', '备注', '牛客ID'].map((n) => ({ name: n, type: 'text' })) },
};
// 给 select 字段补 options
SCHEMA.GgZ71tywhs4HEZytFSqXTP.properties.forEach((p) => {
  if (p.name === '投递状态') p.config = { options: [{ id: 's1', text: '待投递' }, { id: 's2', text: '已投递' }, { id: 's3', text: '不投了' }] };
  if (p.name === '优先级') p.config = { options: [{ id: 'p1', text: 'P1' }, { id: 'p2', text: 'P2' }] };
  if (p.name === '批次') p.config = { options: [{ id: 'b1', text: '27秋招' }, { id: 'b2', text: '27暑期实习' }, { id: 'b3', text: '其他' }] };
});
SCHEMA.oBGkMFTv9Xv4Xn5gFOK18S.properties.forEach((p) => {
  if (p.name === '当前阶段') { p.type = 'select'; p.config = { options: ['已投递', '笔试', '一面', '二面', 'HR面', 'Offer', '感谢信', '已终止'].map((t, i) => ({ id: 'st' + i, text: t })) }; }
});
SCHEMA.tgH8096uENTaIj8RSY9qm5.properties.forEach((p) => {
  if (p.name === '投递状态') { p.type = 'select'; p.config = { options: [{ id: 's1', text: '待投递' }, { id: 's2', text: '已投递' }, { id: 's3', text: '不投了' }] }; }
});
SCHEMA.EdCHnKtjZIXEw37tUmvhqL = { properties: ['公司', '类型', '事项时间', '原文摘要', '发件人', '来源', '状态', '置信度', '消息ID', '收件时间'].map((n) => ({ name: n, type: 'text' })) };
SCHEMA.EdCHnKtjZIXEw37tUmvhqL.properties.forEach((p) => {
  if (p.name === '类型') { p.type = 'select'; p.config = { options: [{ id: 't1', text: '笔试' }, { id: 't2', text: '面试' }, { id: 't3', text: 'Offer' }, { id: 't4', text: '感谢信' }, { id: 't5', text: '其他' }] }; }
  if (p.name === '来源') { p.type = 'select'; p.config = { options: [{ id: 'm1', text: '邮件' }, { id: 'm2', text: '短信' }, { id: 'm3', text: '浏览器扩展' }] }; }
  if (p.name === '状态') { p.type = 'select'; p.config = { options: [{ id: 'w1', text: '待确认' }, { id: 'w2', text: '已确认' }, { id: 'w3', text: '已忽略' }] }; }
  if (p.name === '置信度') { p.type = 'select'; p.config = { options: [{ id: 'c1', text: '高' }, { id: 'c2', text: '中' }, { id: 'c3', text: '低' }] }; }
});

const TABLE = { GgZ71tywhs4HEZytFSqXTP: DATA.jobs, oBGkMFTv9Xv4Xn5gFOK18S: DATA.apps, tgH8096uENTaIj8RSY9qm5: DATA.interns, EdCHnKtjZIXEw37tUmvhqL: DATA.inbox };

const MOCK = `
(function(){
  window.__MOCK__={queries:0,onUpdatedCalls:0,writes:0,handlers:[],fired:0,uncaught:[]};
  window.addEventListener('error',function(e){window.__MOCK__.uncaught.push(String(e.message))});
  window.__SMART_PAGE__={database:{
    getSchema:function(o){return Promise.resolve(JSON.parse(JSON.stringify(window.__SCHEMA__[o.databaseId])))},
    query:function(o){window.__MOCK__.queries++;
      var all=window.__TABLE__[o.databaseId]||[],size=o.pageSize||50;
      var start=0;
      if(o.startCursor){var i=all.findIndex(function(r){return r.record_id===o.startCursor});start=i<0?0:i+1}
      var page=all.slice(start,start+size);
      var last=page.length?page[page.length-1].record_id:null;
      return Promise.resolve({results:JSON.parse(JSON.stringify(page)),nextCursor:last,hasMore:start+size<all.length});
    },
    addRecord:function(){window.__MOCK__.writes++;return Promise.resolve({record_id:'new'})},
    updateRecord:function(){window.__MOCK__.writes++;return Promise.resolve({})},
    deleteRecord:function(){window.__MOCK__.writes++;return Promise.resolve({})},
    onUpdated:function(h){window.__MOCK__.onUpdatedCalls++;window.__MOCK__.handlers.push(function(p){window.__MOCK__.fired++;return h(p)})}
  }};
})();
`;

(async () => {
  const EXE = process.env.CHROME_EXE || path.join(process.env.LOCALAPPDATA || '', 'ms-playwright', 'chromium-1228', 'chrome-win64', 'chrome.exe');
  const browser = await chromium.launch(fs.existsSync(EXE) ? { executablePath: EXE } : { channel: 'chromium' });
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push('pageerror: ' + e.message));
  // 自动接受 confirm/alert：批量打分与标记已投都有确认框
  page.on('dialog', (d) => d.accept());
  page.on('console', (m) => {
    if (m.type() === 'error') errors.push('console.error: ' + m.text());
    else if (process.env.DEBUG) console.log('PAGE>', m.text());
  });

  await page.addInitScript({ content: 'window.__SCHEMA__=' + JSON.stringify(SCHEMA) + ';window.__TABLE__=' + JSON.stringify(TABLE) + ';' });
  await page.addInitScript({ content: MOCK });
  // 关掉零配置免费通道：冒烟保持离线确定性（无 Key → Mock），不依赖外网
  await page.addInitScript({ content: 'try{localStorage.setItem("wb_ai_free","0")}catch(e){}' });
  const t0 = Date.now();
  await page.goto('file:///' + TARGET.replace(/\\/g, '/'));
  await page.waitForFunction(() => {
    const el = document.getElementById('ov_todayCnt');
    const cards = document.getElementById('at_jobCards');
    return el && cards && !/加载中/.test(cards.textContent);
  }, { timeout: 15000 });
  const tInit = Date.now() - t0;

  const r = await page.evaluate(() => {
    const q = (id) => document.getElementById(id);
    const mock = window.__MOCK__;
    const cards = document.querySelectorAll('#at_jobCards .jcard');
    return {
      queries: mock.queries, onUpdatedCalls: mock.onUpdatedCalls, writes: mock.writes,
      syncTxt: (q('syncTxt') || {}).textContent,
      today: (q('ov_todayList') || {}).innerHTML.length,
      todayCnt: (q('ov_todayCnt') || {}).textContent,
      autumnCards: cards.length,
      autumnCnt: (q('at_jobCnt') || {}).textContent,
      soeCards: document.querySelectorAll('#so_jobCards .jcard').length,
      internCards: document.querySelectorAll('#ir_jobCards .jcard').length,
      heatCells: document.querySelectorAll('#hmGrid .hm-cell').length,
      heatSum: (q('hmSum') || {}).textContent,
      cityOptions: (q('at_fCity') || { options: [] }).options.length,
      careerOptions: (q('at_fCareer') || { options: [] }).options.length,
      batchChips: document.querySelectorAll('#at_batchChips .chip').length,
      domNodes: document.getElementsByTagName('*').length,
      uncaught: mock.uncaught,
      views: document.querySelectorAll('.view').length,
    };
  });

  // 交互：切 Tab → 筛选城市 → 打开公司情报（带牛客ID 深链）→ 热力图弹层
  await page.click('nav.tabbar .tab[data-view="autumn"]');
  await page.click('#at_batchChips .chip[data-mode="autumn"]');
  const afterChip = await page.textContent('#at_jobCnt');
  await page.selectOption('#at_fCity', { index: 2 });
  const afterCity = await page.textContent('#at_jobCnt');
  await page.click('#at_jobCards .jsearch');
  const intel = await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('#intelBody .igoto')).map((b) => b.getAttribute('data-u'));
    return { secs: document.querySelectorAll('#intelBody .isec').length, items: btns.length, hasEnterprise: btns.some((u) => /enterprise\/\d+/.test(u)), sample: btns.slice(0, 3) };
  });
  const intelOpen = await page.evaluate(() => getComputedStyle(document.getElementById('intelModal')).display !== 'none');
  await page.click('#intelClose');
  await page.click('nav.tabbar .tab[data-view="overview"]');
  await page.evaluate(() => { if (window.ovSub) window.ovSub('me'); });
  await page.click('#hmGrid .hm-cell:nth-child(80)');
  const hmOpen = await page.evaluate(() => getComputedStyle(document.getElementById('hmModal')).display !== 'none');
  const hmDetail = await page.textContent('#hmDetail');
  await page.click('#hmClose');
  // 热力图/阶段/收件箱/漏斗都在「个人中心」子视图内，保持 ovSub('me') 继续测

  // 阶段快捷 UI：卡片有 已投/不投 快键；点阶段标签展开全部阶段选项（不点选项，避免触发写库）
  const stageUi = await page.evaluate(() => {
    const card = document.querySelector('#appCards .acard, #ov_appCards .acard');
    if (!card) return null;
    const qy = card.querySelector('.aquick');
    const qn = card.querySelector('.aquick2');
    const tag = card.querySelector('[data-field="当前阶段"]');
    const box = card.querySelector('.astagebox');
    if (!tag || !box) return null;
    const hiddenBefore = box.hidden;
    tag.click();
    const chips = Array.from(box.querySelectorAll('.schip')).map((b) => b.textContent);
    const visibleAfter = !box.hidden;
    const curMarked = !!box.querySelector('.schip.cur');
    tag.click();
    const hiddenAfterToggle = box.hidden;
    return { hasQuick: !!qy && !!qn, quickTxt: [qy && qy.textContent, qn && qn.textContent], hiddenBefore, visibleAfter, chips, curMarked, hiddenAfterToggle };
  });

  // 情报收件箱：待确认渲染 / 确认展开写入条 / 默认阶段映射 / 写库
  const inboxUi = await page.evaluate(() => {
    const cnt = document.getElementById('ibCnt') || document.getElementById('ov_ibCnt');
    const box = document.getElementById('ibCards') || document.getElementById('ov_ibCards');
    const cards = box ? Array.from(box.querySelectorAll('.acard')) : [];
    return { cnt: cnt ? cnt.textContent : '', n: cards.length, companies: cards.map((c) => { const b = c.querySelector('[data-field="公司"]'); return b ? b.textContent : ''; }) };
  });
  // 切到「招聘邮箱」视图（收件箱 section 现在归属我的空间，不再默认显示）
  await page.evaluate(() => { const b = Array.from(document.querySelectorAll('.snsec')).find((x) => x.getAttribute('data-sec') === 'mail'); if (b) b.click(); });
  await page.click('#ibCards .acard .ibok, #ov_ibCards .acard .ibok');
  const pickVisible = await page.evaluate(() => { const p = document.querySelector('#ibCards .acard .ibpick, #ov_ibCards .acard .ibpick'); return !!p && p.style.display !== 'none'; });
  const defStage = await page.evaluate(() => { const p = document.querySelector('#ibCards .acard .ibpick select, #ov_ibCards .acard .ibpick select'); return p ? p.value : ''; });
  const writesBefore = await page.evaluate(() => window.__MOCK__.writes);
  await page.click('#ibCards .acard .ibpick button.btn-pri, #ov_ibCards .acard .ibpick button.btn-pri');
  await page.waitForTimeout(600);
  const writesAfter = await page.evaluate(() => window.__MOCK__.writes);

  await page.click('nav.tabbar .tab[data-view="autumn"]');

  // 外部数据变更订阅：模拟他人在表格改数据 → 页面应自动重拉
  // 先静置 1.5s 以上，避开「刚拉过数就跳过」的回声抑制窗口
  await page.waitForTimeout(1600);
  const beforeQueries = await page.evaluate(() => window.__MOCK__.queries);
  await page.evaluate(() => { window.__MOCK__.handlers.forEach((h) => h({ databaseIds: ['GgZ71tywhs4HEZytFSqXTP'] })); });
  await page.waitForTimeout(1600);
  const afterQueries = await page.evaluate(() => window.__MOCK__.queries);
  const fired = await page.evaluate(() => window.__MOCK__.fired);

  // 内存/规模指标
  const mem = await page.evaluate(() => (performance.memory ? {
    usedMB: Math.round(performance.memory.usedJSHeapSize / 1048576),
    totalMB: Math.round(performance.memory.totalJSHeapSize / 1048576),
  } : null));

  console.log('--- 初始化 ---');
  console.log('初始化耗时(ms):', tInit);
  console.log('同步状态:', r.syncTxt, '| query 次数:', r.queries, '| onUpdated 注册:', r.onUpdatedCalls);
  console.log('--- 渲染 ---');
  console.log('今日处理条目数:', r.todayCnt, '| 区块 HTML 长度:', r.today);
  console.log('秋招卡片:', r.autumnCards, '计数文案:', r.autumnCnt, '| 央国企卡片:', r.soeCards, '| 实习卡片:', r.internCards);
  console.log('热力图格子:', r.heatCells, '| 摘要:', r.heatSum);
  console.log('城市选项:', r.cityOptions, '| 职业选项:', r.careerOptions, '| 批次 chips:', r.batchChips, '| 视图数:', r.views);
  console.log('DOM 节点总数:', r.domNodes);
  console.log('--- 交互 ---');
  console.log('切Tab+我的批次 后:', afterChip, '| 选城市后:', afterCity);
  console.log('情报面板: 分区', intel.secs, '条目', intel.items, '含牛客企业深链:', intel.hasEnterprise, '| 打开:', intelOpen);
  console.log('  样例链接:', intel.sample.join(' , '));
  console.log('热力图弹层打开:', hmOpen, '| 明细:', String(hmDetail).slice(0, 70));
  if (!stageUi) { console.error('阶段快捷UI: 未找到卡片/标签'); errors.push('stage UI missing'); }
  else {
    console.log('阶段快捷UI: 快键', stageUi.quickTxt.join('/'), '| 展开前隐藏:', stageUi.hiddenBefore, '| 点击后展开:', stageUi.visibleAfter, '| 当前阶段高亮:', stageUi.curMarked, '| 再点收起:', stageUi.hiddenAfterToggle);
    console.log('  阶段选项:', stageUi.chips.join(' · '));
    if (!stageUi.hasQuick || !stageUi.visibleAfter || !stageUi.curMarked || !stageUi.hiddenAfterToggle) errors.push('stage UI broken');
  }
  console.log('情报收件箱: 待确认', inboxUi ? inboxUi.n : '无', '条 计数', inboxUi && inboxUi.cnt, '| 公司:', inboxUi ? inboxUi.companies.join('/') : '-');
  console.log('  确认→展开写入条:', pickVisible, '| 默认阶段:', defStage, '| 写库次数', writesBefore, '→', writesAfter);
  if (!inboxUi || inboxUi.n !== 2 || !pickVisible || defStage !== '笔试' || writesAfter - writesBefore < 2) errors.push('inbox UI broken');

  // 主题色面板
  const theme = await page.evaluate(() => {
    const b = document.getElementById('themebtn');
    if (!b) return { ok: false };
    b.click();
    const pop = document.getElementById('themepop');
    const open = !!pop && pop.classList.contains('open');
    const sws = pop ? Array.from(pop.querySelectorAll('.sw')) : [];
    if (sws[2]) sws[2].click();
    const pri = getComputedStyle(document.documentElement).getPropertyValue('--pri').trim();
    const grad = getComputedStyle(document.documentElement).getPropertyValue('--grad');
    const saved = localStorage.getItem('wb_theme');
    const rgbVar = getComputedStyle(document.documentElement).getPropertyValue('--pri-rgb').trim();
    localStorage.removeItem('wb_theme');
    return { ok: true, open, n: sws.length, pri, grad: grad.trim(), saved, rgbVar };
  });
  console.log('主题面板: 打开=', theme.open, '| 预设数=', theme.n, '| 切预设后 --pri=', theme.pri, '| --grad=', theme.grad, '| 持久化=', theme.saved, '| --pri-rgb=', theme.rgbVar);
  if (!theme.ok || !theme.open || theme.n < 7 || theme.grad !== theme.pri) errors.push('theme picker broken');

  // Agent 高级自定义（AGTUNE_JS）：渲染 / 人设 / 预设 / 参数合并 / System 组装 / 备份
  const agx = await page.evaluate(() => {
    const b = document.querySelector('.agxbox');
    if (!b) return { missing: true };
    const sel = document.querySelector('select[id$="agFnSel"]');
    const out = { sections: b.querySelectorAll('.agx').length, chips: b.querySelectorAll('.agxpre').length, opts: sel ? sel.options.length : 0 };
    out.lab = (b.querySelector('[data-f="fnlab"]') || {}).textContent || '';
    // 人设
    b.querySelector('[data-f="persona"]').value = '测试人设：求职大模型实习';
    document.querySelector('.agxsavep').click();
    out.persona = localStorage.getItem('wb_agent_persona') || '';
    // 预设：第 5 个 = JSON 严格输出
    document.querySelectorAll('.agxpre')[4].click();
    const k0 = sel.value;
    out.presetApplied = (JSON.parse(localStorage.getItem('wb_agent_tune') || '{}')[k0] || {}).fmt === 'json';
    // 高级参数保存
    const setv = (n, v) => { const e = b.querySelector('[data-f="' + n + '"]'); if (e) e.value = v; };
    setv('tp', '0.9'); setv('model', 'my-model'); setv('lang', 'zh');
    document.querySelector('.agxsave').click();
    // 上方基础区保存不能冲掉高级参数（合并语义）
    const mt = document.querySelector('input[id$="agMt"]');
    if (mt) mt.value = 1600;
    const saveBtn = document.querySelector('[id$="agSaveTune"]');
    if (saveBtn) saveBtn.click();
    const t0 = JSON.parse(localStorage.getItem('wb_agent_tune') || '{}')[k0] || {};
    out.merged = { tp: t0.tp, model: t0.model, lang: t0.lang, mt: t0.mt };
    // 切换功能：面板跟随
    sel.value = 'review';
    sel.dispatchEvent(new Event('change', { bubbles: true }));
    out.switchedLab = (b.querySelector('[data-f="fnlab"]') || {}).textContent || '';
    out.switchedTp = (b.querySelector('[data-f="tp"]') || {}).value || '';
    // System 组装：人设 + 用户 system + 风格约束，且用户写了 system 就不带内置提示
    const msgs = window.agBuildMessages([{ role: 'system', content: '内置系统提示' }, { role: 'user', content: 'x' }], window.agTune('review'));
    out.sysRole = msgs[0] && msgs[0].role;
    out.sysHasPersona = msgs[0] && msgs[0].content.indexOf('测试人设') >= 0;
    // 备份往返
    const exported = window.agxExport();
    const parsed = JSON.parse(exported);
    localStorage.removeItem('wb_agent_tune');
    const cleared = Object.keys(JSON.parse(localStorage.getItem('wb_agent_tune') || '{}')).length;
    const okImp = window.agxImport(exported);
    out.backup = { keys: Object.keys(parsed.tune || {}).length, cleared, okImp, restored: Object.keys(JSON.parse(localStorage.getItem('wb_agent_tune') || '{}')).length };
    localStorage.removeItem('wb_agent_tune');
    localStorage.removeItem('wb_agent_persona');
    return out;
  });
  console.log('Agent 高级设置: 小节=', agx.sections, '| 预设=', agx.chips, '| 功能下拉=', agx.opts, '| 当前功能=', agx.lab, '→', agx.switchedLab);
  console.log('  人设保存=', JSON.stringify(agx.persona), '| 预设生效=', agx.presetApplied, '| 合并后=', JSON.stringify(agx.merged));
  console.log('  System 组装: role=', agx.sysRole, '| 含人设=', agx.sysHasPersona, '| 备份往返=', JSON.stringify(agx.backup));
  if (agx.missing) errors.push('agent advanced panel missing');
  else {
    if (agx.sections !== 4 || agx.chips < 5) errors.push('agent advanced panel broken');
    if (!agx.lab || !agx.switchedLab || agx.lab === agx.switchedLab) errors.push('agent panel does not follow function');
    if (!agx.persona || !agx.presetApplied) errors.push('agent persona/preset broken');
    if (agx.merged.tp !== '0.9' || agx.merged.model !== 'my-model' || agx.merged.mt !== 1600) errors.push('agent merge semantics broken');
    if (agx.sysRole !== 'system' || !agx.sysHasPersona) errors.push('agent system assembly broken');
    if (!agx.backup.okImp || agx.backup.restored < 1 || agx.backup.cleared !== 0) errors.push('agent backup broken');
  }

  // AI 设置（BYOK + Mock）：预设联动、无 Key 测试进演示模式
  const ai = await page.evaluate(() => {
    const g = (id) => document.getElementById('ov_' + id) || document.getElementById(id);
    const prov = g('aiProvider'), base = g('aiBase'), model = g('aiModel'), test = g('aiTest'), status = g('aiStatus');
    if (!prov || !test) return { missing: true };
    prov.value = 'kimi';
    prov.dispatchEvent(new Event('change'));
    const filled = base.value.indexOf('moonshot') >= 0 && !!model.value;
    test.click();
    const st = status.textContent;
    return { filled, st, isMock: st.indexOf('Mock') >= 0 || st.indexOf('演示') >= 0 };
  });
  if (ai.missing) {
    console.log('AI设置: 未找到面板');
    errors.push('ai settings missing');
  } else {
    console.log('AI设置: 预设联动=', ai.filled, '| 无Key测试状态=', ai.st);
    if (!ai.filled || !ai.isMock) errors.push('ai settings broken');
  }

  // Agent 调参台：载入默认 → 改参保存 → 读取生效 → 恢复默认 → A/B 对比 → trace
  const tune = await page.evaluate(async () => {
    const g = (id) => document.getElementById('ov_' + id) || document.getElementById(id);
    const sel = g('agFnSel'), t = g('agT'), mt = g('agMt'), sys = g('agSys');
    if (!sel || !t || !mt || !sys) return { missing: true };
    const emptyTune = () => { localStorage.removeItem('wb_agent_tune'); localStorage.removeItem('wb_ai_trace'); if (window.agPanelLoad) window.agPanelLoad(); };
    emptyTune();
    sel.value = 'parse'; sel.dispatchEvent(new Event('change'));
    const defT = window.agTune('parse');
    const loadedDefault = Math.abs(defT.t - 0.2) < 1e-6 && defT.mt === 2000 && sys.value.length > 10;
    // 改成 0.9 / 3000 并保存
    t.value = '0.9'; t.dispatchEvent(new Event('input'));
    mt.value = '3000';
    const showVal = g('agTVal').textContent;
    g('agSaveTune').click();
    const after = window.agTune('parse');
    const savedOk = Math.abs(after.t - 0.9) < 1e-6 && after.mt === 3000;
    const statusCustom = (g('agStatus') || {}).textContent || '';
    // 恢复默认
    g('agResetTune').click();
    const reset = window.agTune('parse');
    const resetOk = Math.abs(reset.t - 0.2) < 1e-6 && reset.mt === 2000;
    // A/B 对比（Mock 模式下两侧都出演示输出）
    g('agAB').click();
    const abIn = g('agAbIn');
    abIn.value = '测试输入：Python PyTorch RAG 项目经历';
    g('agAB').click();
    if (window.agABRun) window.agABRun();
    await new Promise((r) => setTimeout(r, 400));
    const L = (g('agAbL') || {}).textContent || '';
    const R = (g('agAbR') || {}).textContent || '';
    const abOk = L.indexOf('当前参数') >= 0 && R.indexOf('默认参数') >= 0 && L.length > 20 && R.length > 20;
    const trace = (g('agTrace') || {}).textContent || '';
    const traceOk = trace.indexOf('t=') >= 0;
    // 其他功能默认值抽查
    const defsOk = ['match', 'review', 'profile', 'inbox', 'reco', 'rag'].every((k) => window.agTune(k).t > 0);
    emptyTune();
    return { loadedDefault, savedOk, statusCustom, resetOk, abOk, traceOk, defsOk, showVal };
  });
  if (tune.missing) {
    console.log('调参台: 未找到面板');
    errors.push('agent tune panel missing');
  } else {
    console.log('调参台: 载默认=', tune.loadedDefault, '| 滑块显示=', tune.showVal, '| 改参生效=', tune.savedOk, '| 状态=', tune.statusCustom, '| 恢复默认=', tune.resetOk, '| A/B=', tune.abOk, '| 调用记录=', tune.traceOk, '| 七功能默认齐=', tune.defsOk);
    if (!tune.loadedDefault || !tune.savedOk || !tune.resetOk || !tune.abOk || !tune.traceOk || !tune.defsOk) errors.push('agent tune broken');
  }

  // 数据洞察：dmMine 合成数据校验（词典/城市/交叉）+ .dmbtn 开弹窗（620 条 mock）
  const dm = await page.evaluate(async () => {
    const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
    if (!window.dmMine || !window.dmOpen) return { missing: true };
    const rs = [
      { 公司: 'A公司', 岗位方向: '大模型算法', 工作地点: '北京/上海', 备注: '熟悉Python、PyTorch，有RAG与知识图谱项目经验，熟悉大模型推理部署' },
      { 公司: 'B公司', 岗位方向: '大模型算法', 工作地点: '北京', 备注: '熟悉Python，了解LangChain，有大模型微调经验' }
    ];
    const m = window.dmMine(rs);
    const lexHas = m.lex.some((x) => x.t === 'Python' && x.df === 2);
    const cityTop = !!m.cities[0] && m.cities[0][0] === '北京' && m.cities[0][1] === 2;
    const crossOk = m.cross.some((x) => x[0] === '北京 × 大模型算法' && x[1] === 2);
    document.querySelector('.dmbtn').click();
    await sleep(60);
    const mask = document.getElementById('dmModal');
    const open = !!mask && mask.className.indexOf('open') >= 0;
    const body = ((document.getElementById('dmBody') || {}).textContent) || '';
    const bars = document.querySelectorAll('#dmBody .dmfill').length;
    const secs = document.querySelectorAll('#dmBody .dmsec').length;
    let closeOk = false;
    if (mask) { const b = mask.querySelector('.dmclose'); if (b) b.click(); closeOk = document.getElementById('dmModal').className.indexOf('open') < 0; }
    return { lexHas, cityTop, crossOk, open, sample: body.indexOf('共 620 条') >= 0, bars, secs, closeOk };
  });
  if (dm.missing) {
    console.log('数据洞察: 未找到 dmMine/dmOpen');
    errors.push('dm module missing');
  } else {
    console.log('数据洞察: 词典命中=', dm.lexHas, '| 城市Top=', dm.cityTop, '| 交叉=', dm.crossOk, '| 弹窗=', dm.open, '| 样本量=', dm.sample, '| 条形数=', dm.bars, '| 分区数=', dm.secs, '| 关闭=', dm.closeOk);
    if (!dm.lexHas || !dm.cityTop || !dm.crossOk || !dm.open || !dm.sample || dm.bars < 5 || dm.secs < 4 || !dm.closeOk) errors.push('dm insight broken');
  }

  // RAG 知识库问答：分词 / 语料来源 / BM25 命中与单调 / 无关问题拒绝作答 / 引用角标 / 弹窗
  const rag = await page.evaluate(async () => {
    const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
    if (!window.ragCorpus || !window.ragAsk || !window.ragSearch || !window.ragTok) return { missing: true };
    const oldK = localStorage.getItem('wb_ai_key');
    const oldR = localStorage.getItem('wb_resumes');
    localStorage.removeItem('wb_ai_key');
    localStorage.setItem('wb_resumes', JSON.stringify([{ id: 'r-rag', name: 'RAG测试简历', intent: 'AI 大模型实习', note: '', text: '基于 KG-RAG 的汽车故障智能诊断系统，混合检索 BGE-M3 + BM25 + reranker，Neo4j 知识图谱三元组覆盖 95%，推理准确率 89.7%', parsed: null, at: '2026-09-18' }]));
    // 1) 中英混合分词：英文按词、中文按 2-gram
    const tk = window.ragTok('熟悉Python与RAG检索增强');
    const tokOk = tk.indexOf('python') >= 0 && tk.indexOf('检索') >= 0 && tk.indexOf('增强') >= 0;
    // 2) 语料来源：岗位 / 实习 / 简历 都进库
    const docs = window.ragCorpus();
    const srcs = {};
    docs.forEach((d) => { srcs[d.src] = (srcs[d.src] || 0) + 1; });
    const srcOk = (srcs['岗位'] || 0) > 100 && (srcs['实习'] || 0) > 0 && (srcs['简历'] || 0) === 1;
    // 3) BM25 命中：top1 必须真的含查询词，且分数单调不增
    const idx = window.ragIndex(docs);
    const hits = window.ragSearch(idx, 'RAG 知识图谱', 5);
    const t1 = hits.length ? (docs[hits[0].i].title + ' ' + docs[hits[0].i].text).toLowerCase() : '';
    const hitOk = hits.length > 0 && t1.indexOf('rag') >= 0 && t1.indexOf('知识') >= 0;
    let mono = true;
    for (let i = 1; i < hits.length; i++) if (hits[i].s > hits[i - 1].s + 1e-9) mono = false;
    // 4) 无关问题：必须 0 命中（这是「拒绝作答」的前提）
    const none = window.ragSearch(idx, 'zzzqqqxyzzy 甲乙丙丁戊己庚辛', 5).length;
    // 5) 卡片：点示例 chip → 出检索片段 + 引用角标；无 Key 时只检索不生成
    const sec = document.querySelector('.ragsec');
    const chip = sec ? sec.querySelector('.ragchip') : null;
    if (chip) chip.click();
    await sleep(250);
    const stat = sec ? sec.querySelector('.ragstat').textContent : '';
    const out = sec ? sec.querySelector('.ragout').textContent : '';
    const cites = sec ? sec.querySelectorAll('.ragsrc').length : 0;
    const statOk = stat.indexOf('语料') >= 0 && stat.indexOf('本机') >= 0;
    const outOk = out.indexOf('检索演示') >= 0;
    // 6) 点引用角标 → 对应原文片段高亮
    const cite = sec ? sec.querySelector('.ragcite') : null;
    let citeOk = false;
    if (cite) { cite.click(); citeOk = !!sec.querySelector('.ragsrc.hit'); }
    // 7) 展开原文
    const more = sec ? sec.querySelector('.ragmore') : null;
    let moreOk = true;
    if (more) { const before = more.textContent; more.click(); moreOk = more.textContent !== before; }
    // 8) 岗位页「问资料库」→ 弹窗开 / 关
    const rb = document.querySelector('.ragbtn');
    let openOk = false, closeOk = false;
    if (rb) {
      rb.click();
      await sleep(80);
      const mask = document.getElementById('ragModal');
      openOk = !!mask && mask.className.indexOf('open') >= 0 && !!mask.querySelector('.ragq');
      if (mask) { const cb = mask.querySelector('.ragclose'); if (cb) cb.click(); closeOk = document.getElementById('ragModal').className.indexOf('open') < 0; }
    }
    if (oldK != null) localStorage.setItem('wb_ai_key', oldK);
    if (oldR != null) localStorage.setItem('wb_resumes', oldR); else localStorage.removeItem('wb_resumes');
    return { tokOk, srcOk, srcs: JSON.stringify(srcs), hitOk, mono, none, statOk, outOk, cites, citeOk, moreOk, openOk, closeOk, stat: stat.slice(0, 70), hasBtn: !!rb };
  });
  if (rag.missing) {
    console.log('RAG 问答: 未找到 ragCorpus/ragAsk/ragTok');
    errors.push('rag module missing');
  } else {
    console.log('RAG 问答: 分词=', rag.tokOk, '| 语料=', rag.srcs, '| 命中=', rag.hitOk, '| 分数单调=', rag.mono, '| 无关问题命中=', rag.none, '| 状态=', rag.statOk, '| 只检索不生成=', rag.outOk, '| 片段=', rag.cites, '| 引用高亮=', rag.citeOk, '| 展开原文=', rag.moreOk, '| 按钮=', rag.hasBtn, '| 弹窗=', rag.openOk, '| 关闭=', rag.closeOk);
    if (!rag.tokOk || !rag.srcOk || !rag.hitOk || !rag.mono || rag.none !== 0 || !rag.statOk || !rag.outOk || rag.cites < 1 || !rag.citeOk || !rag.moreOk || !rag.openOk || !rag.closeOk) errors.push('rag qa broken');
  }

  // 简历档案（多份 + 意向 + Mock 解析）与投递画像（Mock 生成）
  const resume = await page.evaluate(() => {
    const g = (id) => document.getElementById('ov_' + id) || document.getElementById(id);
    const list = g('rsList'), gen = g('rpGen');
    if (!list || !gen) return { missing: true };
    const old = localStorage.getItem('wb_resumes');
    localStorage.setItem('wb_resumes', JSON.stringify([
      { id: 'rsmoke1', name: '冒烟测试版', intent: 'AI 大模型实习', note: '突出 RAG', text: '张三 本科 Python PyTorch RAG 项目…', parsed: null, parsedAt: '', at: '2026-09-15' },
      { id: 'rsmoke2', name: '数据运营版', intent: 'AI 数据运营', note: '', text: '李四 数据清洗 标注…', parsed: null, parsedAt: '', at: '2026-09-15' }
    ]));
    if (window.rsRender) window.rsRender();
    const cards = list.querySelectorAll('.acard').length;
    const cnt = (g('rsCount') || {}).textContent || '';
    const tags = Array.from(list.querySelectorAll('.tag')).map((t) => t.textContent);
    // Mock 解析第一份（无 Key → 演示解析结果）
    const btn = list.querySelector('.acard .rsparse') || Array.from(list.querySelectorAll('.acard button')).find((b) => b.textContent === 'AI 解析');
    let parsedOk = false;
    if (btn) { btn.click(); parsedOk = (localStorage.getItem('wb_resumes') || '').indexOf('已解析') >= 0 || (JSON.parse(localStorage.getItem('wb_resumes') || '[]')[0] || {}).parsed != null; }
    // Mock 画像
    gen.click();
    const out = g('rpOut');
    const profileOk = !!out && out.style.display !== 'none' && out.textContent.indexOf('画像') >= 0;
    // 还原
    if (old != null) localStorage.setItem('wb_resumes', old); else localStorage.removeItem('wb_resumes');
    localStorage.removeItem('wb_profile');
    if (window.rsRender) window.rsRender();
    return { cards, cnt, tags: tags.join('|'), parsedOk, profileOk };
  });
  if (resume.missing) {
    console.log('简历档案: 未找到模块');
    errors.push('resume module missing');
  } else {
    console.log('简历档案: 卡片数=', resume.cards, '| 计数=', resume.cnt, '| 意向标签=', resume.tags, '| Mock解析=', resume.parsedOk, '| Mock画像=', resume.profileOk);
    if (resume.cards < 2 || !resume.parsedOk || !resume.profileOk) errors.push('resume/profile broken');
  }

  // Word（docx）简历上传：浏览器原生解包 zip → 提取正文
  let docxOk = false;
  const docxPath = path.join(__dirname, 'fixtures', 'test_resume.docx');
  if (fs.existsSync(docxPath)) {
    const rsFile = (await page.$('#rsFile')) || (await page.$('#ov_rsFile'));
    if (rsFile) {
      await rsFile.setInputFiles(docxPath);
      await page.waitForTimeout(600);
      docxOk = await page.evaluate(() => {
        const g = (id) => document.getElementById('ov_' + id) || document.getElementById(id);
        const save = g('rsSave');
        if (save) save.click();
        const a = JSON.parse(localStorage.getItem('wb_resumes') || '[]');
        const last = a[a.length - 1] || {};
        const t = last.text || '';
        return t.indexOf('KG-RAG') >= 0 && t.indexOf('PyTorch') >= 0 && t.indexOf('窦畅') >= 0;
      });
      // 清理冒烟数据
      await page.evaluate(() => {
        const a = JSON.parse(localStorage.getItem('wb_resumes') || '[]');
        localStorage.setItem('wb_resumes', JSON.stringify(a.filter((r) => (r.text || '').indexOf('KG-RAG') < 0)));
        if (window.rsRender) window.rsRender();
      });
    }
  }
  console.log('Word上传: docx解析并保存=', docxOk);
  if (!docxOk) errors.push('docx upload broken');

  // PDF 简历上传：零依赖抽取（CID + ToUnicode CMap）；并校验只收 Word/PDF、不再收 txt/md
  let pdfOk = false, acceptOk = false, txtRejOk = false;
  const pdfPath = path.join(__dirname, 'fixtures', 'test_resume.pdf');
  const rsInput = (await page.$('#rsFile')) || (await page.$('#ov_rsFile'));
  if (fs.existsSync(pdfPath) && rsInput) {
    acceptOk = await page.evaluate(() => {
      const g = (id) => document.getElementById('ov_' + id) || document.getElementById(id);
      const f = g('rsFile');
      return !!f && f.getAttribute('accept') === '.doc,.docx,.pdf';
    });
    await page.evaluate(() => { localStorage.removeItem('wb_resumes'); if (window.rsRender) window.rsRender(); });
    await rsInput.setInputFiles(pdfPath);
    await page.waitForTimeout(900);
    pdfOk = await page.evaluate(() => {
      const g = (id) => document.getElementById('ov_' + id) || document.getElementById(id);
      const save = g('rsSave');
      if (save) save.click();
      const a = JSON.parse(localStorage.getItem('wb_resumes') || '[]');
      const t = (a[a.length - 1] || {}).text || '';
      return t.indexOf('窦畅') >= 0 && t.indexOf('KG-RAG') >= 0 && t.indexOf('PyTorch') >= 0 && t.indexOf('西南交通大学') >= 0;
    });
    // txt 已不再支持：上传后缓冲为空 → 点保存不会新增简历
    const txtPath = path.join(__dirname, 'tmp_smoke_resume.txt');
    fs.writeFileSync(txtPath, '不应该被接受的纯文本简历', 'utf8');
    await page.evaluate(() => { localStorage.removeItem('wb_resumes'); if (window.rsRender) window.rsRender(); });
    await rsInput.setInputFiles(txtPath);
    await page.waitForTimeout(300);
    txtRejOk = await page.evaluate(() => {
      const g = (id) => document.getElementById('ov_' + id) || document.getElementById(id);
      const save = g('rsSave');
      if (save) save.click();
      return JSON.parse(localStorage.getItem('wb_resumes') || '[]').length === 0;
    });
    fs.unlinkSync(txtPath);
    await page.evaluate(() => { localStorage.removeItem('wb_resumes'); if (window.rsRender) window.rsRender(); });
  }
  console.log('PDF上传: accept=', acceptOk, '| 中文抽取并保存=', pdfOk, '| txt 已拒绝=', txtRejOk);
  if (!acceptOk) errors.push('resume accept types wrong');
  if (!pdfOk) errors.push('pdf upload broken');
  if (!txtRejOk) errors.push('txt upload not rejected');

  // M2 匹配打分：无简历提示 → Mock 打分出徽章 → 按匹配度排序
  const match = await page.evaluate(async () => {
    const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
    const tabs = Array.from(document.querySelectorAll('nav.tabbar .tab'));
    const at = tabs.find((t) => t.getAttribute('data-view') === 'autumn');
    if (at) at.click();
    await sleep(60);
    const card0 = window.mtCardAt && window.mtCardAt(0);
    const card1 = window.mtCardAt && window.mtCardAt(1);
    if (!card0 || !card0.__mtRec) return { missing: true };
    const rec0 = card0.__mtRec, rec1 = card1 && card1.__mtRec;
    const sRes = localStorage.getItem('wb_resumes'), sJd = localStorage.getItem('wb_jd'), sMt = localStorage.getItem('wb_match');
    // ① 无简历 → 提示 + 不写结果
    localStorage.removeItem('wb_resumes');
    card0.querySelector('.jmatch').click();
    await sleep(30);
    const row0 = card0.querySelector('.jmatchrow');
    const noResumeHint = !!row0 && row0.textContent.indexOf('简历档案') >= 0 && row0.textContent.indexOf('上传简历') >= 0;
    const noWrite = !window.mtGet(rec0);
    // ② 有简历 + JD → Mock 打分出徽章
    localStorage.setItem('wb_resumes', JSON.stringify([{ id: 'r-mt', name: '打分测试版', intent: 'AI 大模型实习', note: '', text: 'Python PyTorch RAG 项目', parsed: null, at: '2026-09-15' }]));
    window.mtJdSet(rec0, '任职要求：熟悉 Python、PyTorch，有 RAG 项目经验优先');
    const jdOk = (window.mtJdGet(rec0) || '').indexOf('PyTorch') >= 0;
    card0.querySelector('.jmatch').click();
    await sleep(40);
    const badge0 = !!row0 && row0.textContent.indexOf('分') >= 0;
    const stored0 = window.mtGet(rec0);
    const storedOk = !!stored0 && typeof stored0.score === 'number';
    // ③ 按匹配度排序：塞两条不同分数，校验降序（95 分应排最前）
    let sortOk = false;
    if (rec1) {
      const k0 = window.mtKey(rec0), k1 = window.mtKey(rec1);
      localStorage.setItem('wb_match', JSON.stringify({ [k0]: { score: 40, at: '2026-09-15' }, [k1]: { score: 95, at: '2026-09-15' } }));
      window.mtRefreshRows();
      const fso = document.getElementById('at_fSort') || document.getElementById('fSort');
      if (fso) { fso.value = 'match'; fso.dispatchEvent(new Event('change')); }
      await sleep(60);
      const first = window.mtCardAt(0);
      const txt = (first && first.querySelector('.jmatchrow')) ? first.querySelector('.jmatchrow').textContent : '';
      sortOk = !!first && first.__mtRec === rec1 && txt.indexOf('95 分') >= 0;
    } else { sortOk = true; }
    // 还原
    if (sRes != null) localStorage.setItem('wb_resumes', sRes); else localStorage.removeItem('wb_resumes');
    if (sJd != null) localStorage.setItem('wb_jd', sJd); else localStorage.removeItem('wb_jd');
    if (sMt != null) localStorage.setItem('wb_match', sMt); else localStorage.removeItem('wb_match');
    const fso2 = document.getElementById('at_fSort') || document.getElementById('fSort');
    if (fso2) { fso2.value = ''; fso2.dispatchEvent(new Event('change')); }
    window.mtRefreshRows();
    return { noResumeHint, noWrite, jdOk, badge0, storedOk, sortOk, cards: !!card1 };
  });
  if (match.missing) {
    console.log('匹配打分: 未找到岗位卡片/记录');
    errors.push('match module missing');
  } else {
    console.log('匹配打分: 无简历提示=', match.noResumeHint, '| 未写结果=', match.noWrite, '| JD缓存=', match.jdOk, '| Mock徽章=', match.badge0, '| 结果落库=', match.storedOk, '| 按匹配度排序=', match.sortOk);
    if (!match.noResumeHint || !match.noWrite || !match.jdOk || !match.badge0 || !match.storedOk || !match.sortOk) errors.push('match scoring broken');
  }

  // M2b 单页版自洽：不能残留生产资料库深链，无简历引导链接必须走页内切视图
  //     （与 CI lint 的「demo 自包含」「合并版无跨节点跳转」两条断言同源，
  //      历史上就是因为这里没有断言，链接漏进合并版 4 天没被发现）
  const selfContained = await page.evaluate(async () => {
    const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
    const noProd = document.documentElement.outerHTML.indexOf('workbuddy.cn/space/d/') < 0;
    const tabs = Array.from(document.querySelectorAll('nav.tabbar .tab'));
    const at = tabs.find((t) => t.getAttribute('data-view') === 'autumn');
    if (at) at.click();
    await sleep(60);
    const card0 = window.mtCardAt && window.mtCardAt(0);
    if (!card0) return { noProd, missing: true };
    const sRes = localStorage.getItem('wb_resumes');
    localStorage.removeItem('wb_resumes');
    card0.querySelector('.jmatch').click();
    await sleep(30);
    const row0 = card0.querySelector('.jmatchrow');
    const g = row0 && row0.querySelector('.mgo');
    const href = g ? (g.getAttribute('href') || '') : '';
    const guideLocal = !!g && href.indexOf('workbuddy.cn') < 0;
    const guideText = g ? g.textContent : '';
    if (g) g.click();
    await sleep(40);
    const viewOk = !!document.querySelector('#view_overview.active');
    if (at) at.click();
    await sleep(40);
    if (sRes != null) localStorage.setItem('wb_resumes', sRes); else localStorage.removeItem('wb_resumes');
    window.mtRefreshRows();
    return { noProd, guideLocal, guideText, viewOk, missing: false };
  });
  console.log('单页版自洽: 无生产深链=', selfContained.noProd, '| 引导链接页内=', selfContained.guideLocal, '| 引导文案=', selfContained.guideText, '| 点击切到总览台=', selfContained.viewOk);
  if (!selfContained.noProd || !selfContained.guideLocal || !selfContained.viewOk) errors.push('single-page self-contained broken');

  // M3 面试复盘 / M4 批量打分 / M5 AI 推荐 / M6 邮件 AI 解析
  const plus = await page.evaluate(async () => {
    const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
    const tabs = Array.from(document.querySelectorAll('nav.tabbar .tab'));
    const tdTab = tabs.find((t) => t.textContent === '今日提醒');
    if (tdTab) tdTab.click();
    await sleep(80);
    // M5：规则推荐（本地零成本） + AI 点评（Mock）
    const box = document.querySelector('.recoBox');
    const recN = box ? box.querySelectorAll('.rcitem').length : -1;
    const recCnt = (document.querySelector('.rcCnt') || {}).textContent || '';
    let whyN = 0, recoCache = '';
    const aiBtn = document.querySelector('.rcai');
    if (aiBtn) {
      aiBtn.click();
      await sleep(120);
      whyN = document.querySelectorAll('.recoBox .rcwhy').length;
      recoCache = localStorage.getItem('wb_reco') || '';
    }
    // M3：AI 复盘（Mock）
    let rvOpenOk = false, rvOutOk = false, rvStore = '', rvCard = '';
    const rvBtn = document.querySelector('.acard .arv');
    if (rvBtn) {
      rvBtn.click();
      await sleep(60);
      const mask = document.getElementById('rvMask');
      rvOpenOk = !!mask && mask.className.indexOf('open') >= 0;
      const ta = document.getElementById('rvText');
      if (ta) ta.value = '一面 45 分钟，问了 KG-RAG 检索链路与显存优化，显存题没答好';
      const go = document.getElementById('rvGo');
      if (go) go.click();
      await sleep(150);
      const out = document.getElementById('rvOut');
      rvOutOk = !!out && out.textContent.indexOf('下一轮准备清单') >= 0;
      rvStore = localStorage.getItem('wb_review') || '';
      rvCard = (document.querySelector('.acard [data-field="复盘笔记"]') || {}).textContent || '';
      const cl = document.getElementById('rvClose');
      if (cl) cl.click();
    }
    // M6：收件箱 AI 解析（Mock）+ 解析出的环节成为「写入投递跟踪」默认阶段
    let ibOut = '', ibStage = '';
    const ibBtn = document.querySelector('.ibai');
    if (ibBtn) {
      ibBtn.click();
      await sleep(150);
      const card = ibBtn.closest('.acard');
      const o = card.querySelector('.ibaiout');
      ibOut = o && o.style.display !== 'none' ? o.textContent : '';
      card.querySelector('.ibok').click();
      await sleep(60);
      const sel = card.querySelector('.ibpick select');
      ibStage = sel ? sel.value : '';
    }
    // M4：批量打分（切到秋招页，塞简历 + 给一张卡贴 JD）
    const at = tabs.find((t) => t.getAttribute('data-view') === 'autumn');
    if (at) at.click();
    await sleep(80);
    const oldR = localStorage.getItem('wb_resumes');
    localStorage.setItem('wb_resumes', JSON.stringify([{ id: 'r-b', name: '批量测试', intent: 'AI 大模型实习', note: '', text: 'Python PyTorch RAG', parsed: null, at: '2026-09-15' }]));
    const c0 = window.mtCardAt(0);
    if (c0 && c0.__mtRec) window.mtJdSet(c0.__mtRec, '任职要求：Python、PyTorch、RAG 项目经验');
    localStorage.removeItem('wb_match');
    window.mtRefreshRows();
    const pool0 = window.mtBatchPool ? window.mtBatchPool().length : -1;
    const bb = document.querySelector('.mtbatch');
    if (bb) bb.click();
    await sleep(500);
    const matchN = Object.keys(JSON.parse(localStorage.getItem('wb_match') || '{}')).length;
    const btnTxt = bb ? bb.textContent : '';
    // 还原
    if (oldR != null) localStorage.setItem('wb_resumes', oldR); else localStorage.removeItem('wb_resumes');
    localStorage.removeItem('wb_match');
    localStorage.removeItem('wb_reco');
    localStorage.removeItem('wb_review');
    localStorage.removeItem('wb_ibai');
    window.mtRefreshRows();
    if (tdTab) tdTab.click();
    return { recN, recCnt, whyN, recoCache, rvOpenOk, rvOutOk, rvStore, rvCard, ibOut, ibStage, pool0, matchN, btnTxt };
  });
  console.log('AI推荐: 条数=', plus.recN, '| 计数=', plus.recCnt, '| AI点评理由=', plus.whyN, '| 当日缓存=', plus.recoCache ? '有' : '无');
  console.log('面试复盘: 弹窗=', plus.rvOpenOk, '| Mock含准备清单=', plus.rvOutOk, '| 存本机=', !!plus.rvStore, '| 卡片回填=', String(plus.rvCard).slice(0, 24));
  console.log('邮件AI解析: 输出=', String(plus.ibOut).slice(0, 70), '| 确认默认阶段=', plus.ibStage);
  console.log('批量打分: 候选池=', plus.pool0, '| 落库条数=', plus.matchN, '| 按钮复原=', plus.btnTxt);
  if (plus.recN < 1) errors.push('reco list empty');
  if (plus.whyN < 1) errors.push('reco ai reasons missing');
  if (!plus.rvOpenOk || !plus.rvOutOk || !plus.rvStore) errors.push('review assistant broken');
  if (String(plus.ibOut).indexOf('AI 解析') < 0) errors.push('inbox ai parse broken');
  if (plus.ibStage !== '一面') errors.push('inbox ai stage not applied');
  if (plus.matchN < 1) errors.push('batch scoring broken');

  // 今日提醒 / 个人中心 子视图：两个方向各切一次并校验显示与高亮
  const subs = await page.evaluate(() => {
    const g = (id) => document.getElementById('ov_' + id) || document.getElementById(id);
    const td = g('ovToday'), me = g('ovMeHead');
    const vis = (e) => !!e && e.style.display !== 'none';
    const tabs = Array.from(document.querySelectorAll('nav.tabbar .tab'));
    const tdTab = tabs.find((t) => t.textContent === '今日提醒');
    const meTab = tabs.find((t) => t.textContent === '个人中心');
    if (!tdTab || !meTab) return { missing: true };
    tdTab.click();
    const onTd = { td: vis(td), me: vis(me), tdTabOn: tdTab.getAttribute('aria-current') === 'page' };
    meTab.click();
    const onMe = { td: vis(td), me: vis(me), meTabOn: meTab.getAttribute('aria-current') === 'page' };
    const stats = ['tdW7', 'tdNode', 'tdIb', 'tdTotal'].map((id) => { const e = g(id); return e ? e.textContent : '?'; });
    return { onTd, onMe, stats };
  });
  if (subs.missing) {
    console.log('子视图: 未找到 今日提醒/个人中心 Tab');
    errors.push('overview tabs missing');
  } else {
    console.log('子视图: 切今日提醒', subs.onTd.td && !subs.onTd.me, '| 高亮今日Tab=', subs.onTd.tdTabOn, '| 切个人中心', subs.onMe.me && !subs.onMe.td, '| 高亮个人Tab=', subs.onMe.meTabOn, '| 近况统计=', subs.stats.join('/'));
    if (!subs.onTd.td || subs.onTd.me || !subs.onTd.tdTabOn || !subs.onMe.me || subs.onMe.td || !subs.onMe.meTabOn) errors.push('overview split broken');
  }

  // 我的空间：侧栏分组（发现/我的/配置）+ 新页面路由（投递记录/日程/助理/知识库/任务/邮箱/配置）
  const myspace = await page.evaluate(() => {
    const out = {};
    const groups = Array.from(document.querySelectorAll('nav.tabbar .sngroup')).map((g) => g.textContent);
    out.groups = groups.join(',');
    out.snitems = document.querySelectorAll('nav.tabbar .tab').length;
    const vis = (id) => { const e = document.getElementById('ov_' + id) || document.getElementById(id); return !!e && e.style.display !== 'none'; };
    const click = (sec) => { const b = Array.from(document.querySelectorAll('.snsec')).find((x) => x.getAttribute('data-sec') === sec); if (b) b.click(); };
    click('tasks');
    out.tasksOpen = vis('secTasks');
    const inp = document.getElementById('ov_taskTitle') || document.getElementById('taskTitle');
    const dt = document.getElementById('ov_taskDate') || document.getElementById('taskDate');
    if (inp && dt) {
      inp.value = '冒烟测试任务';
      const t = new Date();
      dt.value = t.getFullYear() + '-' + String(t.getMonth() + 1).padStart(2, '0') + '-' + String(t.getDate()).padStart(2, '0');
      const add = document.getElementById('ov_taskAdd') || document.getElementById('taskAdd');
      add.click();
      const list = document.getElementById('ov_taskList') || document.getElementById('taskList');
      out.taskAdded = !!list && list.textContent.indexOf('冒烟测试任务') >= 0;
      out.inToday = (document.getElementById('ov_todayList') || document.getElementById('todayList')).textContent.indexOf('冒烟测试任务') >= 0;
    }
    click('sched');
    out.schedOpen = vis('secSched');
    const sl = document.getElementById('schedList');
    out.schedRows = sl ? sl.querySelectorAll('.schrow').length : -1;
    click('agent');
    out.agentOpen = vis('secAgent');
    const chatIn = document.getElementById('ov_agChatIn') || document.getElementById('agChatIn');
    if (chatIn) {
      chatIn.value = '我该优先投哪些公司？';
      const send = document.getElementById('ov_agChatSend') || document.getElementById('agChatSend');
      send.click();
    }
    out.chatSent = !!chatIn;
    click('rag');
    out.ragOpen = vis('secRag');
    out.ragSecIn = !!document.querySelector('#secRag .ragsec, #ov_secRag .ragsec');
    out.ragCnt = ((document.querySelector('#secRag .ragcnt, #ov_secRag .ragcnt') || {}).textContent || '');
    out.ragStat = ((document.querySelector('#secRag .ragstat, #ov_secRag .ragstat') || {}).textContent || '').slice(0, 24);
    out.ragSibling = (() => { const r = document.getElementById('ov_secRag') || document.getElementById('secRag'); return !!r && !(r.closest && r.closest('#ov_ovToday, #ovToday')); })();
    out.remArm = !!(document.getElementById('ov_remArm') || document.getElementById('remArm'));
    out.remTick = typeof window.remTick === 'function';
    out.rvMic = typeof window.rvMic === 'function';
    click('mail');
    out.mailOpen = vis('secMail') && vis('secIb');
    out.ibRaw = !!(document.getElementById('ov_ibRaw') || document.getElementById('ibRaw'));
    click('apps');
    out.appsOpen = vis('secApps');
    out.appCards = !!(document.getElementById('ov_appCards') || document.getElementById('appCards'));
    click('cfg');
    out.cfgOpen = vis('secAi') && vis('secAg');
    out.agFnSel = !!(document.getElementById('ov_agFnSel') || document.getElementById('agFnSel'));
    const prov = document.getElementById('ov_aiProvider') || document.getElementById('aiProvider');
    out.freePresets = prov ? prov.querySelectorAll('option').length : -1;
    out.freeTip = !!(document.getElementById('ov_aiFreeTip') || document.getElementById('aiFreeTip'));
    out.freeCh = typeof window.aiFreeChat === 'function' && typeof window.aiFreeOnce === 'function' && String(window.AI_FREE_URL || '').indexOf('https://') === 0;
    out.freeOff = localStorage.getItem('wb_ai_free') === '0' && window.aiFreeOn && window.aiFreeOn() === false;
    // 品牌：Job Seeker 文字 + 徽标图形 + favicon
    const lg = document.querySelector('nav.tabbar a.logo');
    out.brand = lg ? lg.textContent : '';
    out.brandMark = !!(lg && lg.querySelector('.lm svg'));
    const ico = document.querySelector('link[rel="icon"]');
    out.favicon = ico ? (ico.getAttribute('href') || '') : '';
    click('me') || true;
    const meTab2 = Array.from(document.querySelectorAll('nav.tabbar .tab')).find((t) => t.textContent === '个人中心');
    if (meTab2) meTab2.click();
    out.meOpen = vis('ovMeHead') && vis('secRs');
    // 还原到 today + 清理测试数据
    const tdTab = Array.from(document.querySelectorAll('nav.tabbar .tab')).find((t) => t.textContent === '今日提醒');
    if (tdTab) tdTab.click();
    out.backToday = vis('ovToday');
    localStorage.removeItem('wb_tasks');
    localStorage.removeItem('wb_agent_chat');
    if (window.renderToday) renderToday();
    return out;
  });
  console.log('我的空间: 分组=', myspace.groups, '| 侧栏项=', myspace.snitems, '| 任务页开=', myspace.tasksOpen, '| 加任务=', myspace.taskAdded, '| 浮出今日=', myspace.inToday, '| 日程开=', myspace.schedOpen, '| 日程行=', myspace.schedRows, '| 助理开=', myspace.agentOpen, '| 发消息=', myspace.chatSent, '| 知识库开=', myspace.ragOpen, '| RAG卡在内=', myspace.ragSecIn, '| 邮箱开=', myspace.mailOpen, '| 解析框=', myspace.ibRaw, '| 投递开=', myspace.appsOpen, '| 配置开=', myspace.cfgOpen, '| 调参台在=', myspace.agFnSel, '| 个人中心=', myspace.meOpen, '| 回今日=', myspace.backToday);
  if ((myspace.groups || '').split(',').length < 3) errors.push('sidenav groups missing');
  if (!myspace.tasksOpen || !myspace.taskAdded || !myspace.inToday) errors.push('tasks broken');
  if (!myspace.schedOpen || myspace.schedRows < 1) errors.push('sched broken');
  if (!myspace.agentOpen || !myspace.chatSent) errors.push('agent chat broken');
  if (!myspace.ragOpen || !myspace.ragSecIn) errors.push('knowledge base broken');
  if (!myspace.ragSibling || !myspace.ragCnt) errors.push('rag sibling broken');
  if (!myspace.remArm || !myspace.remTick || !myspace.rvMic) errors.push('remind/mic broken');
  if (myspace.freePresets < 9 || !myspace.freeTip) errors.push('free presets broken');
  if (!myspace.freeCh || !myspace.freeOff) errors.push('zero-config ai channel broken');
  if (!myspace.mailOpen || !myspace.ibRaw) errors.push('mail workbench broken');
  if (!myspace.appsOpen || !myspace.appCards) errors.push('apps view broken');
  if (!myspace.cfgOpen || !myspace.agFnSel) errors.push('cfg view broken');
  if (!myspace.meOpen || !myspace.backToday) errors.push('me view broken');
  console.log('品牌: 文字=', myspace.brand, '| 徽标=', myspace.brandMark, '| favicon=', (myspace.favicon || '').slice(0, 28));
  if ((myspace.brand || '').indexOf('Job Seeker') < 0 || !myspace.brandMark
      || (myspace.favicon || '').indexOf('data:image/svg+xml') !== 0) errors.push('brand logo broken');
  console.log('--- 实时订阅 ---');
  console.log('外部变更前 query:', beforeQueries, '→ 后:', afterQueries, '| 触发重拉:', afterQueries > beforeQueries, '| handler 实际执行次数:', fired);
  if (mem) console.log('JS 堆: 已用', mem.usedMB, 'MB / 总量', mem.totalMB, 'MB');
  console.log('--- 错误 ---');
  console.log('未捕获错误:', r.uncaught.length ? r.uncaught : '无');
  console.log('控制台/页面错误:', errors.length ? errors : '无');

  await browser.close();
  process.exit(errors.length || r.uncaught.length ? 1 : 0);
})().catch((e) => { console.error('SMOKE FAILED:', e); process.exit(2); });
