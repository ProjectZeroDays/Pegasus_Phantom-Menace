import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

const ROOT = process.cwd();
const SRC = path.join(ROOT, 'client', 'src');
const DRY = process.argv.includes('--dry-run');
const esbuild = createRequire(path.join(ROOT, 'client', 'package.json'))('esbuild');

const HTML = new Set(('div section span main header footer nav aside article ul ol li p h1 h2 h3 h4 h5 h6 ' +
  'a button label table tbody thead tr td th form input select textarea svg path g circle rect line text').split(' '));

function blank(s) {
  let o = '';
  for (let i = 0; i < s.length; i++) {
    const c = s[i], n = s[i + 1];
    if (c === '/' && n === '/') { while (i < s.length && s[i] !== '\n') { o += ' '; i++; } o += '\n'; continue; }
    if (c === '/' && n === '*') { o += '  '; i += 2; while (i < s.length && !(s[i] === '*' && s[i + 1] === '/')) { o += s[i] === '\n' ? '\n' : ' '; i++; } o += '  '; i++; continue; }
    if (c === '"' || c === "'" || c === '`') { const q = c; o += q; i++; while (i < s.length && s[i] !== q) { if (s[i] === '\\') { o += '  '; i += 2; continue; } o += s[i] === '\n' ? '\n' : ' '; i++; } o += q; i++; continue; }
    o += c;
  }
  return o;
}

function tagEnd(b, st) {
  let d = 0;
  for (let i = st; i < b.length; i++) {
    const c = b[i];
    if (c === '{') d++;
    else if (c === '}') d--;
    else if (c === '>' && d <= 0) return i;
    else if (c === '\n' && d <= 0) return -1;
  }
  return -1;
}

function analyse(src) {
  const b = blank(src);
  const stack = [];
  const edits = [];
  const lines = [];
  const ln = (o) => { let n = 1; for (let i = 0; i < o; i++) if (b[i] === '\n') n++; return n; };

  for (let i = 0; i < b.length; i++) {
    if (b[i] !== '<') continue;
    const nx = b[i + 1];
    if (nx === '>') { stack.push({ name: '', line: ln(i) }); i++; continue; }
    if (nx === '/' && b[i + 2] === '>') { const t = stack.pop(); if (!t || t.name !== '') lines.push(ln(i) + ': stray fragment close'); i += 2; continue; }
    if (nx !== '/') {
      if (!/[A-Za-z]/.test(nx || '')) continue;
      const name = (b.slice(i + 1).match(/^[A-Za-z][\w.:$-]*/) || [''])[0];
      if (!/^[A-Z]/.test(name) && !HTML.has(name)) continue;
      if (b[i + 1 + name.length] && !/[\s/>]/.test(b[i + 1 + name.length])) continue;
      const e = tagEnd(b, i);
      if (e < 0) { lines.push(ln(i) + ': <' + name + '> unterminated'); continue; }
      if (b[e - 1] !== '/') stack.push({ name, line: ln(i) });
      i = e; continue;
    }
    const name = (b.slice(i + 2).match(/^[A-Za-z][\w.:$-]*/) || [''])[0];
    const e = tagEnd(b, i);
    if (e < 0) { lines.push(ln(i) + ': </' + name + '> unterminated'); continue; }
    const top = stack[stack.length - 1];
    if (!top) lines.push(ln(i) + ': </' + name + '> with empty stack');
    else if (top.name === name) stack.pop();
    else {
      const fix = top.name === '' ? '/' : top.name;
      edits.push({ at: i + 2, del: name.length, ins: fix });
      stack.pop();
      lines.push(ln(i) + ': </' + name + '> -> </' + fix + '> (opened line ' + top.line + ')');
    }
    i = e;
  }
  return { edits, stack, lines };
}

const SECTION = /^([ \t]*)<\/div>\n([ \t]*)<\/div>\n([ \t]*)<\/div>\n([ \t]*)<\/div>\n([ \t]*)<section className="card">/gm;

function closeTail(text, name) {
  const m = text.match(/\n([ \t]*)\);\n\}\s*$/);
  if (!m) return text + '\n</' + name + '>\n';
  const ind = m[1].slice(0, Math.max(0, m[1].length - 4));
  return text.slice(0, m.index) + '\n' + ind + '</' + name + '>' + text.slice(m.index);
}

const applyEdits = (s, ed) => [...ed].sort((a, b) => b.at - a.at).reduce((o, e) => o.slice(0, e.at) + e.ins + o.slice(e.at + e.del), s);

async function ok(text, file) {
  try { await esbuild.transform(text, { loader: 'jsx', sourcefile: file }); return { good: true }; }
  catch (e) { const r = (e.errors || [])[0]; return { good: false, msg: r ? r.text + ' (line ' + (r.location ? r.location.line : '?') + ')' : e.message }; }
}

function walk(d, out = []) {
  for (const e of fs.readdirSync(d, { withFileTypes: true })) {
    if (['node_modules', 'dist', 'build', '.git', '.jsx-backup'].includes(e.name)) continue;
    const p = path.join(d, e.name);
    if (e.isDirectory()) walk(p, out);
    else if (e.name.endsWith('.jsx')) out.push(p);
  }
  return out;
}

let fixed = 0, clean = 0, manual = 0;
const bad = [];

for (const file of walk(SRC).sort()) {
  const raw = fs.readFileSync(file, 'utf8');
  let text = raw.replace(/\r\n/g, '\n');
  const rel = path.relative(ROOT, file);
  if ((await ok(text, file)).good) { clean++; continue; }

  const log = [];
  for (let p = 0; p < 3; p++) {
    const before = text;
    text = text.replace(SECTION, (m, a, b, c, d, e) => a + '</div>\n' + b + '</div>\n' + c + '</div>\n' + d + '</section>\n' + e + '<section className="card">');
    const r = analyse(text);
    text = applyEdits(text, r.edits);
    log.push(...r.lines);
    const after = analyse(text);
    if (after.stack.length === 1) text = closeTail(text, after.stack[0].name || 'div');
    if (text === before) break;
    if ((await ok(text, file)).good) break;
  }

  const res = await ok(text, file);
  console.log((res.good ? 'FIXED   ' : 'MANUAL  ') + rel);
  for (const l of log.slice(0, 8)) console.log('        ' + l);
  if (res.good) fixed++;
  else { manual++; bad.push(rel + '  ' + res.msg); console.log('        >> ' + res.msg); }

  if (DRY) continue;
  const bk = path.join(ROOT, '.jsx-backup', rel);
  fs.mkdirSync(path.dirname(bk), { recursive: true });
  if (!fs.existsSync(bk)) fs.copyFileSync(file, bk);
  fs.writeFileSync(file, text, 'utf8');
}

console.log('\nfixed ' + fixed + ' | clean ' + clean + ' | manual ' + manual);
for (const b of bad) console.log('  ' + b);