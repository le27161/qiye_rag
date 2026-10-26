const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { JSDOM } = require('jsdom');
const frontMatter = require('hexo-front-matter');

const root = path.resolve(__dirname, '..');
const postDir = path.join(root, 'source/_posts');
const files = fs.readdirSync(postDir).filter(name => /^rag-.*\.md$/.test(name));
const directory = fs.readFileSync(path.join(root, 'source/rag/index.md'), 'utf8');
const routes = new Set();
let totalCharacters = 0;
let linkCount = 0;

function checkLocalLinks(markdown, label) {
  for (const match of markdown.matchAll(/\]\((\/[^)\s]+)\)/g)) {
    const url = new URL(match[1], 'https://blog.invalid');
    const relative = decodeURIComponent(url.pathname).replace(/^\/+/, '');
    const target = path.resolve(root, 'public', relative);
    assert.ok(target.startsWith(path.resolve(root, 'public') + path.sep), `${label}: unsafe route`);
    const htmlFile = url.pathname.endsWith('/') ? path.join(target, 'index.html') : target;
    assert.ok(fs.existsSync(htmlFile), `${label}: missing ${match[1]}`);
    linkCount++;
  }
}

assert.equal(files.length, 21, 'Expected 21 RAG articles');
for (const file of files) {
  const markdown = fs.readFileSync(path.join(postDir, file), 'utf8');
  const data = frontMatter.parse(markdown);
  assert.ok(data.title && data.description && data.date, `${file}: incomplete metadata`);
  assert.equal(data.series, 'RAG 工程笔记', `${file}: missing series`);
  assert.match(data.permalink, /^rag\/[a-z-]+\/$/, `${file}: invalid permalink`);
  assert.ok(!routes.has(data.permalink), `${file}: duplicate route`);
  routes.add(data.permalink);
  assert.equal((data._content.match(/<!-- more -->/g) || []).length, 1, `${file}: excerpt marker`);
  assert.ok(!/本讲目标|重点掌握|课后练习|第一部分：|第二部分：/.test(data._content), `${file}: lecture wording`);
  assert.ok(!/D:\\Users|file:\/\/|<iframe|<script/.test(data._content), `${file}: local dependency or embedded script`);
  assert.equal((data._content.match(/^```/gm) || []).length % 2, 0, `${file}: unclosed code fence`);
  assert.ok(data._content.length >= 900, `${file}: unexpectedly short`);
  assert.ok(directory.includes(`/${data.permalink}`), `${file}: absent from directory`);

  const output = path.join(root, 'public', data.permalink, 'index.html');
  assert.ok(fs.existsSync(output), `${file}: no generated HTML`);
  const dom = new JSDOM(fs.readFileSync(output, 'utf8'));
  const article = dom.window.document.querySelector('.post-content');
  assert.ok(article, `${file}: missing article`);
  assert.ok(dom.window.document.querySelector('h1').textContent.includes(data.title), `${file}: title mismatch`);
  assert.equal(dom.window.document.querySelector('meta[name="description"]').content, data.description, `${file}: description mismatch`);
  assert.ok(article.querySelectorAll('h2').length >= 3, `${file}: missing sections`);
  if (data._content.includes('```')) assert.ok(article.querySelector('pre'), `${file}: code not rendered`);
  for (const link of dom.window.document.querySelectorAll('a[href^="/rag/"]')) {
    const target = new URL(link.getAttribute('href'), 'https://blog.invalid').pathname;
    assert.ok(fs.existsSync(path.join(root, 'public', target, 'index.html')), `${file}: broken rendered link ${target}`);
  }
  dom.window.close();
  checkLocalLinks(markdown, file);
  totalCharacters += data._content.length;
}

checkLocalLinks(directory, 'RAG directory');
const home = fs.readFileSync(path.join(root, 'public/index.html'), 'utf8');
assert.ok(home.includes('/rag/'), 'Missing series navigation');
console.log(`PASS: ${files.length} articles, ${routes.size} unique routes, ${linkCount} local links, ${totalCharacters} body characters.`);
