// Syntax-check inline <script> of built pages via node --check equivalent
const fs = require('fs');
const path = require('path');
const dir = process.argv[2];
let fail = 0;
for (const f of fs.readdirSync(dir).filter(x => x.endsWith('.html'))) {
  const html = fs.readFileSync(path.join(dir, f), 'utf8');
  const m = html.match(/<script>([\s\S]*?)<\/script>/);
  if (!m) { console.log(f, ': NO SCRIPT'); continue; }
  try {
    new Function(m[1]);
    console.log(f, ': JS OK');
  } catch (e) {
    fail++;
    console.log(f, ': JS ERROR ->', e.message);
  }
}
process.exit(fail ? 1 : 0);
