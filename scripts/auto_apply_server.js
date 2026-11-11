/* AI 全自动投递 · 本地服务
 * 启动：start_auto_apply.bat（或 node auto_apply_server.js）
 * 只监听 127.0.0.1，不对外暴露；浏览器由 Playwright 驱动，动作全部拟人化。
 *
 * 接口（全部带 CORS，供 file:// 与线上页面调用）：
 *   GET  /api/health            服务与浏览器状态
 *   GET  /api/events             SSE：log / shot / state / ask / chat / record / done
 *   POST /api/task               {url,site,resume,dryRun}  发起一次投递
 *   POST /api/stop               中止当前任务
 *   POST /api/reply              {text} 人工介入 / 对话输入
 *   GET  /api/mock               内置模拟投递页（无需外网，用于自测全流程）
 *
 * 安全边界：默认 dryRun=true（跑完流程但不点最终提交）。要真投必须显式传 dryRun:false。
 * 服务端不接触资料库、不写云端，投递成功后把结构化结果推给前端，由前端既有 applyToTracking 回写。
 */
'use strict';
const http = require('http');
const os = require('os');

const PORT = Number(process.env.AA_PORT || 8765);
const HOST = '127.0.0.1';

/* ---------- Playwright 载入（本机受管 node_modules 或在项目内） ---------- */
let chromium = null, pwErr = null;
for (const p of ['playwright-core', 'playwright',
  'C:/Users/窦畅/.workbuddy/binaries/node/workspace/node_modules/playwright-core',
  'C:/Users/窦畅/.workbuddy/binaries/node/workspace/node_modules/playwright']) {
  try { chromium = require(p).chromium; break; } catch (e) { pwErr = e; }
}

/* ---------- SSE 广播 ---------- */
const clients = new Set();
function emit(type, data) {
  const payload = 'event: ' + type + '\ndata: ' + JSON.stringify(data == null ? {} : data) + '\n\n';
  for (const res of clients) { try { res.write(payload); } catch (e) { clients.delete(res); } }
}
function log(msg, kind) { emit('log', { t: Date.now(), msg: String(msg), kind: kind || 'info' }); }
function chat(role, text) { emit('chat', { t: Date.now(), role: role || 'bot', text: String(text) }); }

/* ---------- 拟人动作 ---------- */
const rnd = (a, b) => a + Math.random() * (b - a);
const wait = ms => new Promise(r => setTimeout(r, ms));
function jitter(n) { return Math.round(n + rnd(-3, 3)); }

async function humanMove(page, x, y) {
  const from = page.__mouse || { x: rnd(200, 500), y: rnd(150, 400) };
  const steps = Math.round(rnd(9, 16));
  for (let i = 1; i <= steps; i++) {
    const k = i / steps;
    // ease-out + 轻微抖动，避免直线匀速（最容易被识别为机器）
    const e = 1 - Math.pow(1 - k, 2.2);
    const px = from.x + (x - from.x) * e + rnd(-1.6, 1.6);
    const py = from.y + (y - from.y) * e + rnd(-1.6, 1.6);
    await page.mouse.move(px, py);
    await wait(rnd(8, 26));
  }
  page.__mouse = { x, y };
}

async function humanClick(page, selector, label) {
  const el = await page.$(selector);
  if (!el) throw new Error('找不到元素：' + (label || selector));
  const box = await el.boundingBox();
  if (!box) throw new Error('元素不可见：' + (label || selector));
  const x = jitter(box.x + box.width * rnd(0.32, 0.68));
  const y = jitter(box.y + box.height * rnd(0.35, 0.65));
  await humanMove(page, x, y);
  await wait(rnd(70, 240));                 // 移到目标后的犹豫
  await page.mouse.down(); await wait(rnd(38, 105)); await page.mouse.up();
  if (label) log('点击「' + label + '」', 'act');
  await wait(rnd(120, 420));
}

async function humanType(page, selector, text, label) {
  if (!text) return;
  await humanClick(page, selector, label);
  const per = Math.round(rnd(35, 95));
  for (let i = 0; i < text.length; i++) {
    await page.keyboard.type(text[i]);
    if (i % 11 === 7) await wait(rnd(160, 340));   // 偶尔"想一下"
    else await wait(per);
  }
  log('填入「' + (label || selector) + '」：' + String(text).slice(0, 24), 'act');
}

async function humanScroll(page) {
  const dy = Math.round(rnd(90, 320));
  await page.mouse.wheel(0, dy);
  await wait(rnd(180, 520));
}

async function shot(page, tag) {
  try {
    const buf = await page.screenshot({ type: 'jpeg', quality: 58 });
    emit('shot', { t: Date.now(), tag: tag || '', b64: buf.toString('base64') });
  } catch (e) { /* 截图失败不影响主流程 */ }
}

/* ---------- 站点适配器 ---------- 多个候选选择器兜底，改版不至于全废 ---------- */
const ADAPTERS = {
  mock: {
    name: '内置模拟页（自测）',
    url: () => 'http://' + HOST + ':' + PORT + '/api/mock',
    title: ['#job-title'],
    company: ['#job-company'],
    jd: ['#job-desc'],
    apply: ['#apply-btn'],
    fields: { name: ['#f-name'], phone: ['#f-phone'], email: ['#f-email'], note: ['#f-note'] },
    submit: ['#submit-btn'],
    result: ['#result'],
    captcha: ['.captcha-box'],
  },
  nowcoder: {
    name: '牛客网',
    url: u => u,
    title: ['h1.job-name', '.job-title', 'h1', '[class*="jobName"]'],
    company: ['.company-name', '[class*="companyName"]', '.job-company'],
    jd: ['.job-detail', '.job-description', '[class*="jobDetail"]', '.content'],
    apply: ['button:has-text("立即投递")', 'a:has-text("立即投递")', '[class*="applyBtn"]',
            'button:has-text("投简历")', 'a:has-text("申请")'],
    fields: { name: ['input[placeholder*="姓名"]', 'input[name="name"]'],
              phone: ['input[placeholder*="手机"]', 'input[type="tel"]'],
              email: ['input[placeholder*="邮箱"]', 'input[type="email"]'],
              note: ['textarea[placeholder*="自我介绍"]', 'textarea'] },
    submit: ['button:has-text("确认投递")', 'button:has-text("提交")', 'button[type="submit"]'],
    result: ['.apply-success', '[class*="success"]', '.toast'],
    captcha: ['.geetest_panel', '.captcha', 'iframe[src*="captcha"]'],
  },
  bytedance: {
    name: '字节招聘（需登录）',
    url: u => u,
    title: ['h1', '[class*="job-title"]', '[class*="positionName"]'],
    company: ['.company-name'],
    jd: ['[class*="job-description"]', '[class*="jobDetail"]', 'article'],
    apply: ['button:has-text("立即投递")', 'button:has-text("申请")', '[class*="apply"]'],
    fields: { name: ['input[placeholder*="姓名"]'], phone: ['input[placeholder*="手机"]'],
              email: ['input[placeholder*="邮箱"]'], note: ['textarea'] },
    submit: ['button:has-text("提交")', 'button[type="submit"]'],
    result: ['[class*="success"]'],
    captcha: ['.captcha', '[class*="verify"]'],
  },
};

async function firstText(page, sels) {
  for (const s of sels || []) {
    try { const el = await page.$(s); if (el) { const t = (await el.innerText()).trim(); if (t) return t; } } catch (e) {}
  }
  return '';
}
async function firstSel(page, sels) {
  for (const s of sels || []) { try { if (await page.$(s)) return s; } catch (e) {} }
  return null;
}

/* ---------- 轻量匹配决策（不依赖外部 LLM，离线可跑） ---------- */
const AI_KW = ['大模型','算法','人工智能','机器学习','深度学习','LLM','RAG','知识图谱','NLP',
               '多模态','PyTorch','Python','推理','推荐','Agent','向量','检索'];
function evaluate(jd, resume) {
  const text = ((jd || '') + ' ' + JSON.stringify(resume || {})).toLowerCase();
  const hits = AI_KW.filter(k => text.indexOf(k.toLowerCase()) >= 0);
  const score = Math.min(98, Math.round(38 + hits.length * 7 + (jd && jd.length > 200 ? 8 : 0)));
  return {
    score, hits: hits.slice(0, 6),
    advice: score >= 80 ? '技术栈高度对口，建议优先投递' : score >= 60 ? '方向相关，可作为常规投递' : '匹配度偏低，建议先确认岗位方向',
    reason: 'JD 与简历关键词命中 ' + hits.length + ' 项' + (hits.length ? '（' + hits.slice(0, 4).join('、') + '）' : ''),
  };
}

/* ---------- 任务状态机 ---------- */
let TASK = null;
let askResolve = null;

function needHuman(q, timeoutMs) {
  return new Promise((resolve) => {
    askResolve = resolve;
    emit('ask', { q, timeout: timeoutMs || 180000 });
    chat('bot', '需要你介入：' + q + '（在左侧对话栏回复「继续」，或点「停止任务」）');
    setTimeout(() => { if (askResolve) { askResolve(null); askResolve = null; } }, timeoutMs || 180000);
  });
}

async function runTask(cfg) {
  if (!chromium) { emit('done', { ok: false, msg: 'Playwright 未安装：' + (pwErr && pwErr.message) }); return; }
  if (TASK && TASK.running) { emit('done', { ok: false, msg: '已有任务在跑，请先停止' }); return; }
  const ad = ADAPTERS[cfg.site] || ADAPTERS.nowcoder;
  const state = { running: true, abort: false, step: 0 };
  TASK = state;
  const alive = () => state.running && !state.abort;
  let browser = null;
  emit('state', { running: true, site: ad.name, dryRun: cfg.dryRun !== false, url: cfg.url || ad.url() });
  chat('bot', '收到任务：' + ad.name + '。我会打开岗位页、读 JD、算匹配、模拟真人填表' +
              (cfg.dryRun === false ? '，并完成提交。' : '（当前为演练模式，不会点最终提交）。'));

  try {
    const launchOpts = {
      headless: process.env.AA_HEADLESS === '1',
      args: ['--disable-blink-features=AutomationControlled', '--no-first-run', '--no-default-browser-check'],
    };
    if (process.env.CHROME_EXE) launchOpts.executablePath = process.env.CHROME_EXE;
    else launchOpts.channel = 'chrome';
    try { browser = await chromium.launch(launchOpts); }
    catch (e) {
      log('有头浏览器启动失败，回落无头：' + e.message.slice(0, 90), 'warn');
      launchOpts.headless = true; delete launchOpts.channel;
      if (process.env.CHROME_EXE) launchOpts.executablePath = process.env.CHROME_EXE;
      browser = await chromium.launch(launchOpts);
    }
    const ctx = await browser.newContext({
      viewport: { width: 1360, height: 900 }, locale: 'zh-CN',
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    });
    await ctx.addInitScript(() => {
      Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    });
    const page = await ctx.newPage();
    state.page = page;
    page.on('pageerror', e => log('页面脚本异常：' + String(e.message).slice(0, 120), 'warn'));

    const url = cfg.url || ad.url();
    log('打开岗位页：' + url, 'step');
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await wait(rnd(700, 1500));
    await shot(page, '打开岗位页');
    if (!alive()) throw new Error('ABORT');

    await humanScroll(page);
    const title = await firstText(page, ad.title);
    const company = await firstText(page, ad.company);
    const jd = await firstText(page, ad.jd);
    log('读到岗位：' + (company || '—') + ' / ' + (title || '—'), 'step');
    if (jd) log('JD 正文 ' + jd.length + ' 字，已截取前 120 字用于匹配', 'step');
    chat('bot', '已读到「' + (company || '目标公司') + ' · ' + (title || '岗位') + '」。' +
                (jd ? 'JD 摘要：' + jd.slice(0, 120).replace(/\s+/g, ' ') + '…' : '该站未暴露 JD 正文，按岗位名判断。'));

    const ev = evaluate((title || '') + ' ' + jd, cfg.resume);
    log('匹配度 ' + ev.score + ' 分 · ' + ev.reason, ev.score >= 80 ? 'ok' : 'warn');
    chat('bot', '匹配度 ' + ev.score + ' 分，' + ev.advice + '。' + ev.reason + '。' +
                (ev.hits.length ? '命中：' + ev.hits.join('、') + '。' : ''));
    if (ev.score < 45) {
      const go = await needHuman('匹配度仅 ' + ev.score + ' 分，仍要继续投递吗？回复「继续」或「停止」');
      if (!go || !alive() || /停止|取消|不要/.test(go)) throw new Error('USER_CANCEL');
    }

    const cap = await firstSel(page, ad.captcha);
    if (cap) {
      log('检测到验证码，暂停等你手动处理', 'warn');
      await shot(page, '验证码');
      const go = await needHuman('检测到验证码，请在浏览器里完成后回复「继续」');
      if (!go || /停止|取消/.test(go)) throw new Error('USER_CANCEL');
    }

    const applySel = await firstSel(page, ad.apply);
    if (!applySel) throw new Error('找不到投递入口（站点可能改版或未登录）');
    await humanClick(page, applySel, '投递入口');
    await shot(page, '打开投递表单');
    if (!alive()) throw new Error('ABORT');

    const resume = cfg.resume || {};
    for (const key of ['name', 'phone', 'email', 'note']) {
      if (!alive()) throw new Error('ABORT');
      const sel = await firstSel(page, ad.fields[key]);
      if (!sel) continue;
      const val = resume[key] || '';
      if (!val) continue;
      await humanType(page, sel, String(val), key === 'note' ? '自我介绍' : key);
    }
    await humanScroll(page);
    await shot(page, '表单填写完成');

    const result = {
      ok: true, dryRun: cfg.dryRun !== false, site: ad.name, url,
      company: company || (cfg.company || ''), position: title || (cfg.position || ''),
      score: ev.score, hits: ev.hits, advice: ev.advice,
      jdExcerpt: (jd || '').slice(0, 200),
    };

    if (cfg.dryRun === false) {
      const sub = await firstSel(page, ad.submit);
      if (!sub) throw new Error('找不到提交按钮');
      log('执行最终提交（真实投递）', 'step');
      await humanClick(page, sub, '确认提交');
      await wait(rnd(900, 1600));
      await shot(page, '提交结果');
      const rs = await firstText(page, ad.result);
      result.resultText = rs || '已提交，请在站内确认投递记录';
      log('提交完成：' + result.resultText.slice(0, 80), 'ok');
      chat('bot', '已完成投递：' + (result.company || '目标公司') + ' · ' + (result.position || '岗位') +
                  '。' + result.resultText);
      emit('record', result);       // 前端 applyToTracking 回写
    } else {
      result.resultText = '演练模式：已跑完打开/读取/打分/填表，未点提交';
      log(result.resultText, 'ok');
      chat('bot', result.resultText + '。要真投，关掉「演练模式」再发一次任务。');
    }
    emit('done', result);
  } catch (e) {
    const msg = String(e && e.message || e);
    if (msg === 'ABORT' || state.abort) { log('任务已中止', 'warn'); emit('done', { ok: false, msg: '任务已中止' }); }
    else if (msg === 'USER_CANCEL') { log('按你的指示停止', 'warn'); emit('done', { ok: false, msg: '已按指示取消' }); }
    else { log('任务失败：' + msg.slice(0, 180), 'err'); chat('bot', '这一步卡住了：' + msg.slice(0, 140) + '。可以换站点或手动登录后再试。'); emit('done', { ok: false, msg }); }
  } finally {
    state.running = false;
    emit('state', { running: false });
    if (browser) { try { await browser.close(); } catch (e) {} }
    TASK = null;
  }
}

/* ---------- 内置模拟页：无需外网即可验证全流程 ---------- */
const MOCK_HTML = `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>投递自测页</title><style>
body{font-family:system-ui,"Microsoft YaHei",sans-serif;background:#f4f6fa;color:#172033;margin:0;padding:32px}
.wrap{max-width:820px;margin:0 auto;background:#fff;border:1px solid #dce3ee;padding:28px}
h1{font-size:22px;margin:0 0 4px} .co{color:#5a6b85;font-size:14px;margin-bottom:18px}
.tag{display:inline-block;background:#e8efff;color:#1449c4;padding:3px 9px;font-size:12px;margin-right:6px}
#job-desc{line-height:1.8;font-size:14px;background:#f8fafc;padding:16px;margin:16px 0}
button{font:inherit;padding:10px 22px;border:0;background:#1449c4;color:#fff;cursor:pointer}
button.ghost{background:#eef2f8;color:#172033;margin-left:8px}
form{display:none;margin-top:20px;border-top:1px solid #dce3ee;padding-top:18px}
form label{display:block;font-size:13px;margin:10px 0 4px}form input,form textarea{width:100%;box-sizing:border-box;padding:9px;border:1px solid #c9d3e3;font:inherit}
#result{display:none;margin-top:18px;padding:14px;background:#e9f8ef;color:#136c3a;font-weight:600}
</style></head><body><div class="wrap">
<h1 id="job-title">AI 大模型算法实习生（RAG 方向）</h1>
<div class="co" id="job-company">示例科技 · 北京 · 200-250 元/天</div>
<span class="tag">大模型</span><span class="tag">RAG</span><span class="tag">PyTorch</span>
<div id="job-desc">岗位职责：参与企业级知识库问答系统建设，负责检索增强生成（RAG）链路优化、向量检索召回与重排、Prompt 设计与效果评测。要求熟悉 Python / PyTorch，了解 BGE-M3、BM25、reranker 等混合检索方案，有 LLM 应用或知识图谱项目经验者优先。每周到岗 4 天，实习 3 个月以上。</div>
<button id="apply-btn">立即投递</button>
<form id="apply-form"><label>姓名</label><input id="f-name" placeholder="姓名">
<label>手机号</label><input id="f-phone" placeholder="手机号">
<label>邮箱</label><input id="f-email" placeholder="邮箱">
<label>自我介绍</label><textarea id="f-note" rows="3" placeholder="自我介绍"></textarea>
<div style="margin-top:14px"><button id="submit-btn" type="button">确认提交</button><button type="button" class="ghost" id="back-btn">返回</button></div></form>
<div id="result">投递成功 · 已收到你的简历</div>
</div><script>
document.getElementById('apply-btn').onclick=function(){this.style.display='none';document.getElementById('apply-form').style.display='block'};
document.getElementById('submit-btn').onclick=function(){document.getElementById('result').style.display='block';this.disabled=true;this.textContent='已提交'};
document.getElementById('back-btn').onclick=function(){document.getElementById('apply-form').style.display='none';document.getElementById('apply-btn').style.display='inline-block'};
</script></body></html>`;

/* ---------- HTTP ---------- */
function cors(res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  res.setHeader('Access-Control-Allow-Methods', 'GET,POST,OPTIONS');
  res.setHeader('Cache-Control', 'no-store');
}
function json(res, code, obj) {
  cors(res); res.writeHead(code, { 'Content-Type': 'application/json; charset=utf-8' });
  res.end(JSON.stringify(obj));
}
function readBody(req) {
  return new Promise((resolve) => {
    let s = '';
    req.on('data', d => { s += d; if (s.length > 200000) s = s.slice(0, 200000); });
    req.on('end', () => { try { resolve(JSON.parse(s || '{}')); } catch (e) { resolve({}); } });
  });
}

const server = http.createServer(async (req, res) => {
  const u = new URL(req.url, 'http://' + HOST + ':' + PORT);
  if (req.method === 'OPTIONS') { cors(res); res.writeHead(204); res.end(); return; }
  if (u.pathname === '/api/health') {
    return json(res, 200, { ok: true, version: 'v55-wp1', playwright: !!chromium,
      browserHint: process.env.CHROME_EXE || 'chrome channel', running: !!(TASK && TASK.running),
      host: HOST, port: PORT, os: os.platform() });
  }
  if (u.pathname === '/api/mock') {
    cors(res); res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' }); res.end(MOCK_HTML); return;
  }
  if (u.pathname === '/api/events') {
    cors(res); res.writeHead(200, { 'Content-Type': 'text/event-stream; charset=utf-8',
      'Connection': 'keep-alive', 'X-Accel-Buffering': 'no' });
    res.write(': connected\n\n');
    clients.add(res);
    const ka = setInterval(() => { try { res.write(': ka\n\n'); } catch (e) {} }, 20000);
    req.on('close', () => { clearInterval(ka); clients.delete(res); });
    return;
  }
  if (u.pathname === '/api/task' && req.method === 'POST') {
    const cfg = await readBody(req);
    if (!cfg.url && cfg.site !== 'mock') return json(res, 400, { ok: false, msg: '缺少 url' });
    if (TASK && TASK.running) return json(res, 409, { ok: false, msg: '已有任务在跑' });
    setImmediate(() => runTask(cfg));
    return json(res, 200, { ok: true, msg: '任务已排队' });
  }
  if (u.pathname === '/api/stop' && req.method === 'POST') {
    if (TASK) TASK.abort = true;
    if (askResolve) { const r = askResolve; askResolve = null; r('停止'); }
    log('收到停止指令', 'warn');
    return json(res, 200, { ok: true });
  }
  if (u.pathname === '/api/reply' && req.method === 'POST') {
    const b = await readBody(req);
    const text = String(b.text || '').trim();
    log('你：' + text, 'user');
    if (askResolve) { const r = askResolve; askResolve = null; r(text); }
    if (TASK && (/停止|取消|别投了/.test(text))) TASK.abort = true;
    if (!askResolve && TASK && TASK.running) chat('bot', '任务进行中，我会在关键节点主动找你确认。');
    return json(res, 200, { ok: true });
  }
  if (u.pathname === '/' || u.pathname === '/index.html') {
    cors(res); res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end('<meta charset="utf-8"><h3>AI 自动投递服务已就绪</h3><p>接口：<code>/api/health</code> · <code>/api/events</code> · <code>/api/mock</code></p><p>在 Job Seeker 页面「AI 投递」里连接 <code>http://' + HOST + ':' + PORT + '</code></p>');
    return;
  }
  json(res, 404, { ok: false, msg: 'not found' });
});

server.listen(PORT, HOST, () => {
  console.log('[auto-apply] listening http://' + HOST + ':' + PORT);
  console.log('[auto-apply] playwright:', chromium ? 'OK' : 'MISSING (' + (pwErr && pwErr.message) + ')');
  console.log('[auto-apply] selftest: http://' + HOST + ':' + PORT + '/api/mock');
});
