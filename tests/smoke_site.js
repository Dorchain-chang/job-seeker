/**
 * 站点快照增量同步回归测试：跑真实 Chromium，验证「每日抓取 → 重新发布 → 用户打开自动补新岗位」这条链路。
 *
 * 一份脚本跑两种产物（用 SMOKE_MODE 切换），因为两者的回归语义完全相同：
 *   默认 / SMOKE_MODE=site    → dist/site/index.html，qz_ 命名空间，快照含四表
 *   SMOKE_MODE=public         → dist/public/index.html，qc_ 命名空间，快照只含岗位表
 *
 * 场景：A 全新访客灌满 / B 老用户只补新增且不动自有数据 / B2 二次刷新不重复增长 / C 删除标记不报错；
 * 公开版额外验证：内置快照不含隐私三表、命名空间未串到 qz_、首次打开二选一的两条路径。
 *
 * 用法（需先跑 build_site.py / build_public.py）：
 *   NODE_PATH=<playwright 目录> node tests/smoke_site.js
 *   NODE_PATH=<playwright 目录> SMOKE_MODE=public node tests/smoke_site.js
 */
const { chromium } = require('playwright-core');
const http = require('http');
const fs = require('fs');
const path = require('path');

const MODE = process.env.SMOKE_MODE || 'site';
const IS_PUBLIC = MODE === 'public';
const ROOT = path.resolve(__dirname, '..', 'dist', IS_PUBLIC ? 'public' : 'site');
// 公开版的 localStorage 命名空间与私有站点版物理隔离
const LS = IS_PUBLIC ? 'qc_' : 'qz_';
// 期望条数随每日同步变化，不能直接写死：以当前种子快照为准。
// 公开版会剔除手工预置的「示例预置」条目，所以要按同样的口径算，否则永远对不上。
const SEED = JSON.parse(fs.readFileSync(path.resolve(__dirname, '..', 'src', 'seed', 'seed.json'), 'utf8'));
const EXPECT = IS_PUBLIC
  ? SEED.jobs.filter(r => (r.来源 && r.来源.text ? r.来源.text : r.来源) !== '示例预置').length
  : SEED.jobs.length;

const server = http.createServer((req, res) => {
  const p = path.join(ROOT, req.url === '/' ? 'index.html' : req.url);
  fs.readFile(p, (e, d) => {
    if (e) { res.writeHead(404); res.end(); return; }
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(d);
  });
});

const PORT = IS_PUBLIC ? 8732 : 8731;
const URL = `http://127.0.0.1:${PORT}/`;

function seedState(has) {
  // 模拟老用户：本机已有 2 条自己的岗位，且早就 seeded 过。
  // 公开版还要带上「已选过起点」的门闩，否则会先弹二选一。
  return `(() => {
    try {
      localStorage.setItem('${LS}seeded','2026-09-20 16:16');
      localStorage.setItem('${LS}jobs', JSON.stringify(${JSON.stringify(has.jobs)}));
      ${IS_PUBLIC ? `localStorage.setItem('${LS}pubAsked','seed');` : ''}
      ${has.gone ? `localStorage.setItem('${LS}seedGone', JSON.stringify(${JSON.stringify(has.gone)}));` : ''}
    } catch(e) { window.__LS_ERR__ = String(e); }
  })()`;
}

(async () => {
  await new Promise(r => server.listen(PORT, r));
  const EXE = process.env.CHROME_EXE || path.join(process.env.LOCALAPPDATA || '', 'ms-playwright', 'chromium-1228', 'chrome-win64', 'chrome.exe');
  console.log('mode:', MODE, '| root:', ROOT);
  console.log('chrome exe exists:', fs.existsSync(EXE), EXE);
  const browser = await chromium.launch(fs.existsSync(EXE) ? { executablePath: EXE } : { channel: 'chromium' });
  const errors = [];

  // 场景 A：全新访客 —— 应灌满岗位库
  {
    const ctx = await browser.newContext();
    // 公开版首次打开会弹起点选择；这里先替访客选「载入岗位库」
    const page = await ctx.newPage();
    page.on('pageerror', e => errors.push('A pageerror: ' + e.message));
    await page.goto(URL, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1200);
    if (IS_PUBLIC) {
      const hasAsk = await page.evaluate(() => !!document.getElementById('qcAskMask'));
      if (!hasAsk) errors.push('A: 全新访客应看到起点选择弹层');
      // 工具条必须仍是 body.firstElementChild（弹层用 appendChild 挂在末尾）
      const firstIsBar = await page.evaluate(() => {
        const b = document.body.firstElementChild;
        return !!b && !b.id.startsWith('qcAskMask');
      });
      if (!firstIsBar) errors.push('A: 起点弹层把工具条挤出了 firstElementChild');
      await page.click('#qcPickSeed');
      await page.waitForTimeout(1500);
    }
    const n = await page.evaluate(k => JSON.parse(localStorage.getItem(k) || '[]').length, LS + 'jobs');
    const bar = await page.evaluate(() => {
      const b = document.body.firstElementChild;
      return b ? b.textContent.slice(0, 80) : '';
    });
    console.log('A 全新访客 jobs =', n, '(期望', EXPECT + ')');
    console.log('A 工具条文案:', JSON.stringify(bar));
    if (n !== EXPECT) errors.push('A: 首次灌入条数不对 ' + n + ' 期望 ' + EXPECT);

    if (IS_PUBLIC) {
      // 内置快照不得含隐私三表
      const keys = await page.evaluate(() => Object.keys(window.__SITE_SEED__ || {}));
      for (const bad of ['apps', 'interns', 'inbox']) {
        if (keys.includes(bad)) errors.push('A: 内置快照仍含隐私表 ' + bad);
      }
      // 命名空间不得串到私有站点版
      const leaked = await page.evaluate(() => {
        const out = [];
        for (let i = 0; i < localStorage.length; i++) {
          const k = localStorage.key(i);
          if (k && k.indexOf('qz_') === 0) out.push(k);
        }
        return out;
      });
      if (leaked.length) errors.push('A: 出现私有站点版命名空间键 ' + leaked.join(','));
      const latch = await page.evaluate(k => localStorage.getItem(k), LS + 'pubAsked');
      if (latch !== 'seed') errors.push('A: 选「载入岗位库」后门闩应为 seed，实际 ' + latch);
    }
    await ctx.close();
  }

  // 场景 B：老用户（已有 2 条） —— 应只补新增，且原 2 条还在
  {
    const mine = [
      { _id: 'mine1', record_id: 'mine1', 公司: '我手动加的公司A', 牛客ID: '999001', 投递状态: '已投递' },
      { _id: 'mine2', record_id: 'mine2', 公司: '我手动加的公司B', 投递状态: '已投递' }
    ];
    const ctx = await browser.newContext();
    await ctx.addInitScript(seedState({ jobs: mine }));
    const page = await ctx.newPage();
    page.on('pageerror', e => errors.push('B pageerror: ' + e.message));
    await page.goto(URL, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1500);
    const r = await page.evaluate(k => {
      const rows = JSON.parse(localStorage.getItem(k) || '[]');
      return {
        n: rows.length,
        keepA: rows.some(x => x.公司 === '我手动加的公司A' && x.投递状态 === '已投递'),
        keepB: rows.some(x => x.公司 === '我手动加的公司B'),
        dupA: rows.filter(x => x.公司 === '我手动加的公司A').length
      };
    }, LS + 'jobs');
    console.log('B 老用户 jobs =', r.n, '(期望', EXPECT + 2, '| 保留A:', r.keepA, '| 保留B:', r.keepB, '| A重复数:', r.dupA);
    if (r.n !== EXPECT + 2) errors.push('B: 增量后条数不对 ' + r.n + ' 期望 ' + (EXPECT + 2));
    if (!r.keepA || !r.keepB) errors.push('B: 用户自己的记录被冲掉');
    if (r.dupA !== 1) errors.push('B: 出现重复 ' + r.dupA);

    // 场景 B2：再刷新一次，不应重复增长
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1200);
    const n2 = await page.evaluate(k => JSON.parse(localStorage.getItem(k) || '[]').length, LS + 'jobs');
    console.log('B2 二次刷新 jobs =', n2, '(期望仍', EXPECT + 2, '，不能重复增长)');
    if (n2 !== EXPECT + 2) errors.push('B2: 二次刷新重复增长 ' + n2);
    await ctx.close();
  }

  // 场景 C：删过的快照条目不应被塞回来
  {
    const gone = ['nc:999002', 'co:某被删公司'];
    const ctx = await browser.newContext();
    await ctx.addInitScript(seedState({ jobs: [], gone }));
    const page = await ctx.newPage();
    page.on('pageerror', e => errors.push('C pageerror: ' + e.message));
    await page.goto(URL, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1500);
    const n = await page.evaluate(k => JSON.parse(localStorage.getItem(k) || '[]').length, LS + 'jobs');
    console.log('C 有 2 条删除标记 jobs =', n, '(期望', EXPECT + '，删除标记主要验证不报错)');
    if (n < EXPECT - 20) errors.push('C: 灌入异常 ' + n);
    await ctx.close();
  }

  // 场景 D（仅公开版）：首次打开选「从空白开始」→ 岗位库为空，且刷新后不再弹
  if (IS_PUBLIC) {
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    page.on('pageerror', e => errors.push('D pageerror: ' + e.message));
    await page.goto(URL, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1200);
    await page.click('#qcPickEmpty');
    await page.waitForTimeout(1500);
    const r = await page.evaluate(k => ({
      n: JSON.parse(localStorage.getItem(k + 'jobs') || '[]').length,
      latch: localStorage.getItem(k + 'pubAsked'),
      askAgain: !!document.getElementById('qcAskMask')
    }), LS);
    console.log('D 选「从空白开始」jobs =', r.n, '(期望 0) | 门闩 =', r.latch, '| 又弹了:', r.askAgain);
    if (r.n !== 0) errors.push('D: 选空白后岗位库应为空，实际 ' + r.n);
    if (r.latch !== 'empty') errors.push('D: 门闩应为 empty，实际 ' + r.latch);
    if (r.askAgain) errors.push('D: 已选过起点却又弹出选择');
    await ctx.close();
  }

  await browser.close();
  server.close();
  const okMsg = IS_PUBLIC ? 'ALL PUBLIC SITE CHECKS PASSED' : 'ALL SITE SYNC CHECKS PASSED';
  console.log(errors.length ? 'FAIL:\n' + errors.join('\n') : okMsg);
  if (errors.length) process.exit(1);
})();
