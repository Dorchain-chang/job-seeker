/**
 * 独立站点的快照增量同步回归测试：跑真实 Chromium，验证「每日抓取 → 重新发布 → 用户打开自动补新岗位」这条链路。
 * 三组场景：A 全新访客灌满 / B 老用户只补新增且不动自有数据 / B2 二次刷新不重复增长 / C 删除标记不报错。
 * 用法（需先 build_site.py）：NODE_PATH=<playwright 目录> node tests/smoke_site.js
 */
const { chromium } = require('playwright-core');
const http = require('http');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', 'dist', 'site');
// 期望条数随每日同步变化，不能直接写死：以当前种子快照为准
const SEED = JSON.parse(fs.readFileSync(path.resolve(__dirname, '..', 'src', 'seed', 'seed.json'), 'utf8'));
const EXPECT = SEED.jobs.length;
const server = http.createServer((req, res) => {
  const p = path.join(ROOT, req.url === '/' ? 'index.html' : req.url);
  fs.readFile(p, (e, d) => {
    if (e) { res.writeHead(404); res.end(); return; }
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(d);
  });
});

const PORT = 8731;
const URL = `http://127.0.0.1:${PORT}/`;

function seedState(has) {
  // 模拟老用户：本机已有 2 条自己的岗位，且早就 seeded 过
  return `(() => {
    try {
      localStorage.setItem('qz_seeded','2026-09-20 16:16');
      localStorage.setItem('qz_jobs', JSON.stringify(${JSON.stringify(has.jobs)}));
      ${has.gone ? `localStorage.setItem('qz_seedGone', JSON.stringify(${JSON.stringify(has.gone)}));` : ''}
    } catch(e) { window.__LS_ERR__ = String(e); }
  })()`;
}

(async () => {
  await new Promise(r => server.listen(PORT, r));
  const EXE = process.env.CHROME_EXE || path.join(process.env.LOCALAPPDATA || '', 'ms-playwright', 'chromium-1228', 'chrome-win64', 'chrome.exe');
  console.log('chrome exe exists:', fs.existsSync(EXE), EXE);
  const browser = await chromium.launch(fs.existsSync(EXE) ? { executablePath: EXE } : { channel: 'chromium' });
  const errors = [];

  // 场景 A：全新访客 —— 应灌满 729 条
  {
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    page.on('pageerror', e => errors.push('A pageerror: ' + e.message));
    await page.goto(URL, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1200);
    const n = await page.evaluate(() => JSON.parse(localStorage.getItem('qz_jobs') || '[]').length);
    const bar = await page.evaluate(() => {
      const b = document.body.firstElementChild;
      return b ? b.textContent.slice(0, 80) : '';
    });
    console.log('A 全新访客 jobs =', n, '(期望', EXPECT + ')');
    console.log('A 工具条文案:', JSON.stringify(bar));
    if (n !== EXPECT) errors.push('A: 首次灌入条数不对 ' + n + ' 期望 ' + EXPECT);
    await ctx.close();
  }

  // 场景 B：老用户（已有 2 条） —— 应补到 729+2=731，且原 2 条还在
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
    const r = await page.evaluate(() => {
      const rows = JSON.parse(localStorage.getItem('qz_jobs') || '[]');
      return {
        n: rows.length,
        keepA: rows.some(x => x.公司 === '我手动加的公司A' && x.投递状态 === '已投递'),
        keepB: rows.some(x => x.公司 === '我手动加的公司B'),
        dupA: rows.filter(x => x.公司 === '我手动加的公司A').length
      };
    });
    console.log('B 老用户 jobs =', r.n, '(期望', EXPECT + 2, '| 保留A:', r.keepA, '| 保留B:', r.keepB, '| A重复数:', r.dupA);
    if (r.n !== EXPECT + 2) errors.push('B: 增量后条数不对 ' + r.n + ' 期望 ' + (EXPECT + 2));
    if (!r.keepA || !r.keepB) errors.push('B: 用户自己的记录被冲掉');
    if (r.dupA !== 1) errors.push('B: 出现重复 ' + r.dupA);

    // 场景 B2：再刷新一次，不应重复增长
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1200);
    const n2 = await page.evaluate(() => JSON.parse(localStorage.getItem('qz_jobs') || '[]').length);
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
    const n = await page.evaluate(() => JSON.parse(localStorage.getItem('qz_jobs') || '[]').length);
    console.log('C 有 2 条删除标记 jobs =', n, '(期望', EXPECT + '，删除标记主要验证不报错)');
    if (n < EXPECT - 20) errors.push('C: 灌入异常 ' + n);
    await ctx.close();
  }

  await browser.close();
  server.close();
  console.log(errors.length ? 'FAIL:\n' + errors.join('\n') : 'ALL SITE SYNC CHECKS PASSED');
})();
