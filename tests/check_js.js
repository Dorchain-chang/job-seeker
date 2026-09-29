// Syntax-check every inline <script> of built pages via node --check equivalent
// （产物里现在有 2 个脚本：<head> 首屏防闪烁 + body 末尾主脚本 → 全量校验，不能只取第一个）
const fs = require('fs');
const path = require('path');
const dir = process.argv[2];
let fail = 0;
for (const f of fs.readdirSync(dir).filter(x => x.endsWith('.html'))) {
  const html = fs.readFileSync(path.join(dir, f), 'utf8');
  const ms = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
  if (!ms.length) { console.log(f, ': NO SCRIPT'); continue; }
  let bad = '';
  for (const m of ms) {
    try { new Function(m[1]); } catch (e) { bad = e.message; break; }
  }
  if (bad) { fail++; console.log(f, ': JS ERROR ->', bad); }
  else console.log(f, ': JS OK (' + ms.length + ' script)');
}
process.exit(fail ? 1 : 0);
