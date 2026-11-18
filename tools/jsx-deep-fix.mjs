#!/usr/bin/env node
/**
 * jsx-deep-fix.mjs - structural JSX repair via tag-stack analysis.
 *
 * Rewrites only unambiguous mismatches:
 *   - closing tag whose name differs from the open tag it closes
 *   - closing tag that matches an ancestor (closes the gap above it)
 *   - tags still open at EOF
 *
 * Usage:
 *   node tools/jsx-deep-fix.mjs            report only
 *   node tools/jsx-deep-fix.mjs --apply    write repairs
 *   node tools/jsx-deep-fix.mjs --apply --aggressive
 *   node tools/jsx-deep-fix.mjs --root <dir> --glob <substr>
 */

import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';

const argv = process.argv.slice(2);
const flag = (f) => argv.includes(f);
const opt = (f, d) => {
  const i = argv.indexOf(f);
  return i >= 0 && argv[i + 1] ? argv[i + 1] : d;
};

const APPLY = flag('--apply');
const AGGRESSIVE = flag('--aggressive');
const ROOT = path.resolve(opt('--root', process.cwd()));
const SRC = path.join(ROOT, 'client', 'src');
const ONLY = opt('--glob', '');

const C = process.stdout.isTTY
  ? { r: '\x1b[31m', g: '\x1b[32m', y: '\x1b[33m', d: '\x1b[2m', x: '\x1b[0m' }
  : { r: '', g: '', y: '', d: '', x: '' };

const HTML = new Set(('div section span header footer main nav aside article ul ol li table thead ' +
  'tbody tr td th p h1 h2 h3 h4 h5 h6 a button input label select option textarea form img svg ' +
  'path g circle rect line polyline polygon text defs linearGradient stop use br hr strong em b i ' +
  'small code pre canvas iframe video audio source figure figcaption dl dt dd details summary ' +
  'dialog template slot math time mark abbr cite q s u sub sup var kbd samp address blockquote').split(' '));

const SKIP = new Set(['node_modules', 'dist', 'build', '.git', '.jsx-backup', 'coverage']);

function walk(dir, out = []) {
  let entries;
  try { entries = fs.readdirSync(dir, { withFileTypes: true }); } catch { return out; }
  for (const e of entries) {
    if (SKIP.has(e.name)) continue;
    const full = path.join(dir, e.name);
    if (e.isDirectory()) walk(full, out);
    else if (e.isFile() && e.name.endsWith('.jsx')) out.push(full);
  }
  return out;
}

function blank(src) {
  let out = '';
  for (let i = 0; i < src.length; i++) {
    const c = src[i], n = src[i + 1];
    if (c === '/' && n === '/') { while (i < src.length && src[i] !== '\n') { out += ' '; i++; } out += '\n'; continue; }
    if (c === '/' && n === '*') {
      out += '  '; i += 2;
      while (i < src.length && !(src[i] === '*' && src[i + 1] === '/')) { out += src[i] === '\n' ? '\n' : ' '; i++; }
      out += '  '; i++; continue;
    }
    if (c === '"' || c === "'" || c === '`') {
      const q = c; out += q; i++;
      while (i < src.length && src[i] !== q) {
        if (src[i] === '\\') { out += '  '; i += 2; continue; }
        out += src[i] === '\n' ? '\n' : ' '; i++;
      }
      out += q; i++; continue;
    }
    out += c;
  }
  return out;
}

function tagEnd(b, start) {
  let depth = 0;
  for (let i = start; i < b.length; i++) {
    const c = b[i];
    if (c === '{') depth++;
    else if (c === '}') depth--;
    else if (c === '>' && depth <= 0) return i;
    else if (c === '\n' && depth <= 0) return -1;
  }
  return -1;
}

function lineAt(b, off) {
  let n = 1;
  for (let i = 0; i < off; i++) if (b[i] === '\n') n++;
  return n;
}

function indentAt(b, off) {
  const s = b.lastIndexOf('\n', off) + 1;
  return b.slice(s, off).match(/^[ \t]*/)[0];
}

/** @returns {{edits: Array, issues: Array}} */
function analyse(src) {
  const b = blank(src);
  const stack = [];
  const edits = [];
  const issues = [];

  for (let i = 0; i < b.length; i++) {
    if (b[i] !== '<') continue;
    const nx = b[i + 1];

    // fragment open / close
    if (nx === '>') { stack.push({ name: '', line: lineAt(b, i), indent: indentAt(b, i), at: i, len: 2 }); i += 1; continue; }
    if (nx === '/' && b[i + 2] === '>') {
      const top = stack.pop();
      if (!top || top.name !== '') issues.push({ line: lineAt(b, i), msg: 'stray fragment close' });
      i += 2; continue;
    }
    if (nx !== '/') {
      if (!/[A-Za-z]/.test(nx || '')) continue;
      const name = (b.slice(i + 1).match(/^[A-Za-z][\w.:$-]*/) || [''])[0];
      const after = b[i + 1 + name.length];
      const looksTag = /^[A-Z]/.test(name) || HTML.has(name);
      if (!looksTag) continue;
      if (after && !/[\s/>]/.test(after)) continue;
      const end = tagEnd(b, i);
      if (end < 0) { issues.push({ line: lineAt(b, i), msg: `<${name}> never terminated` }); continue; }
      const selfClose = b[end - 1] === '/';
      if (!selfClose) stack.push({ name, line: lineAt(b, i), indent: indentAt(b, i), at: i, len: name.length + 1 });
      i = end; continue;
    }

    // close tag
    const name = (b.slice(i + 2).match(/^[A-Za-z][\w.:$-]*/) || [''])[0];
    const end = tagEnd(b, i);
    if (end < 0) { issues.push({ line: lineAt(b, i), msg: `</${name}> never terminated` }); continue; }
    const top = stack[stack.length - 1];

    if (!top) {
      issues.push({ line: lineAt(b, i), msg: `</${name}> with empty stack` });
    } else if (top.name === name) {
      stack.pop();
    } else {
      const deeper = stack.map((s) => s.name).lastIndexOf(name);
      if (deeper >= 0 && AGGRESSIVE) {
        const indent = indentAt(b, i);
        let insert = '';
        while (stack.length - 1 > deeper) { const s = stack.pop(); insert += `\n${indent}</${s.name}>`; }
        stack.pop();
        edits.push({ at: i, del: 0, ins: insert });
        issues.push({ line: lineAt(b, i), msg: `closed gap to </${name}>` });
      } else {
        // rewrite the close tag to match the actual open tag
        const fixed = top.name === '' ? '/' : top.name;
        edits.push({ at: i + 2, del: name.length, ins: fixed });
        stack.pop();
        issues.push({ line: lineAt(b, i), msg: `</${name}> -> </${fixed}> (opened line ${top.line})` });
      }
    }
    i = end;
  }

  for (const s of stack.reverse()) {
    if (s.name === '') { issues.push({ line: s.line, msg: 'unclosed fragment at EOF' }); continue; }
    const at = src.replace(/\n/g, '\n').length;
    edits.push({ at: src.length, del: 0, ins: `${s.indent}</${s.name}>\n`, eof: true });
    issues.push({ line: s.line, msg: `<${s.name}> never closed (appended at EOF)` });
  }
  return { edits, issues };
}

function apply(src, edits) {
  const ordered = [...edits].sort((a, b) => b.at - a.at);
  let out = src;
  for (const e of ordered) out = out.slice(0, e.at) + e.ins + out.slice(e.at + e.del);
  return out;
}

if (!fs.existsSync(SRC)) {
  console.log(`${C.r}client/src not found under ${ROOT}${C.x}`);
  process.exit(1);
}

let total = 0;
let dirty = 0;
for (const file of walk(SRC).sort()) {
  if (ONLY && !file.includes(ONLY)) continue;
  const raw = fs.readFileSync(file, 'utf8');
  const { edits, issues } = analyse(raw);
  if (!issues.length) continue;
  total += issues.length;
  console.log(`\n${C.y}${path.relative(ROOT, file)}${C.x}`);
  for (const i of issues) console.log(`  ${C.d}${i.line}${C.x}  ${i.msg}`);
  if (APPLY && edits.length) {
    fs.writeFileSync(file, apply(raw, edits), 'utf8');
    dirty += 1;
  }
}

console.log(`\n${total} issue(s) across ${total ? 'the files above' : 'nothing'}`);
if (APPLY) console.log(`${C.g}${dirty} file(s) rewritten${C.x} - rerun without --apply to confirm, then build.`);
else if (total) console.log(`${C.d}rerun with --apply (add --aggressive for gap closing)${C.x}`);
process.exit(total ? 2 : 0);