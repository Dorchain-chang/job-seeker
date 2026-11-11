/* WP1 端到端自测：不需要外网/登录，用内置模拟页跑通
 * 「打开岗位页 → 读 JD → 匹配打分 → 拟人点击 → 逐字填表 → 提交 → 回写记录」。
 * 用法：node selftest_auto_apply.js   （需服务已在 127.0.0.1:8765 运行）
 */
'use strict';
const http = require('http');
const HOST = '127.0.0.1', PORT = Number(process.env.AA_PORT || 8765);

function post(path, obj) {
  return new Promise((resolve, reject) => {
    const data = JSON.stringify(obj);
    const req = http.request({ host: HOST, port: PORT, path, method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(data) } }, res => {
      let s = ''; res.on('data', d => s += d); res.on('end', () => { try { resolve(JSON.parse(s)); } catch (e) { reject(new Error(s)); } });
    });
    req.on('error', reject); req.write(data); req.end();
  });
}
function get(path) {
  return new Promise((resolve, reject) => {
    http.get({ host: HOST, port: PORT, path }, res => {
      let s = ''; res.on('data', d => s += d); res.on('end', () => { try { resolve(JSON.parse(s)); } catch (e) { reject(new Error(s)); } });
    }).on('error', reject);
  });
}

const errors = [];
function check(name, cond, extra) {
  console.log((cond ? 'PASS' : 'FAIL') + '  ' + name + (extra !== undefined ? '  -> ' + JSON.stringify(extra) : ''));
  if (!cond) errors.push(name);
}

(async () => {
  let health;
  try { health = await get('/api/health'); }
  catch (e) { console.log('FAIL  service not reachable: ' + e.message); process.exit(1); }
  check('health ok', !!health.ok, health);
  check('playwright loaded', !!health.playwright, health.playwright);

  const logs = [], shots = [], chats = [], states = [], records = [];
  let done = null;
  const sse = http.get({ host: HOST, port: PORT, path: '/api/events' }, res => {
    let buf = '';
    res.on('data', d => {
      buf += d.toString();
      let i;
      while ((i = buf.indexOf('\n\n')) >= 0) {
        const block = buf.slice(0, i); buf = buf.slice(i + 2);
        if (block.charAt(0) === ':') continue;
        const m = /^event: (\S+)\ndata: ([\s\S]*)$/.exec(block);
        if (!m) continue;
        let v; try { v = JSON.parse(m[2]); } catch (e) { continue; }
        if (m[1] === 'log') logs.push(v);
        else if (m[1] === 'shot') shots.push(v);
        else if (m[1] === 'chat') chats.push(v);
        else if (m[1] === 'state') states.push(v);
        else if (m[1] === 'record') records.push(v);
        else if (m[1] === 'done') done = v;
      }
    });
  });
  sse.on('error', e => { console.log('FAIL  sse: ' + e.message); process.exit(1); });
  await new Promise(r => setTimeout(r, 300));

  const task = await post('/api/task', {
    site: 'mock', dryRun: false,
    url: 'http://' + HOST + ':' + PORT + '/api/mock',
    company: '示例科技', position: 'AI 大模型算法实习生',
    resume: { name: '测试候选人', phone: '13800000000', email: 'test@example.com',
               note: '熟悉 RAG 与 PyTorch，做过知识图谱问答系统' },
  });
  check('task accepted', !!task.ok, task);

  const deadline = Date.now() + 120000;
  while (!done && Date.now() < deadline) await new Promise(r => setTimeout(r, 300));
  sse.destroy();

  const all = logs.map(l => l.msg).join(' | ');
  check('task finished', !!done, done && done.msg);
  check('no fatal error', !all.includes('任务失败'), all.slice(-200));
  check('read JD', all.includes('JD 正文') || all.includes('JD 摘要'), '');
  check('match scored', /\d+ 分/.test(all), (all.match(/\d+ 分/) || [])[0]);
  check('clicked apply button', all.includes('投递入口'), '');
  check('typed form fields', all.includes('填入'), logs.filter(l => l.msg.indexOf('填入') >= 0).length + ' fields');
  check('real submit executed', all.includes('执行最终提交'), '');
  check('result read', all.includes('提交完成'), '');
  check('screenshots streamed', shots.length >= 3, shots.length);
  check('assistant chatted', chats.length >= 3, chats.length);
  check('state pushed', states.length >= 2, states.length);
  check('record emitted for writeback', records.length === 1, records.length);
  if (records[0]) {
    check('record has company/position/score', !!(records[0].company && records[0].position && records[0].score),
      { c: records[0].company, p: records[0].position, s: records[0].score });
  }
  console.log('--- logs ---');
  logs.forEach(l => console.log('  [' + l.kind + '] ' + l.msg.slice(0, 130)));
  console.log(errors.length ? 'SELFTEST_FAIL: ' + errors.join(', ') : 'SELFTEST_ALL_PASS (' + logs.length + ' logs, ' + shots.length + ' shots)');
  process.exit(errors.length ? 1 : 0);
})().catch(e => { console.log('SELFTEST_EXCEPTION ' + e.stack); process.exit(1); });
