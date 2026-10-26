const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { JSDOM } = require('jsdom');
const frontMatter = require('hexo-front-matter');
const yaml = require('js-yaml');

const root = path.resolve(__dirname, '..');
const publicRoot = path.join(root, 'public');
const theme = yaml.load(fs.readFileSync(path.join(root, 'themes/aurora/_config.yml'), 'utf8'));
const expected = new Map([['/rag/', 21], ['/agent/', 6], ['/llm/', 6]]);
const routes = new Set();
let articles = 0;
let links = 0;

function outputFor(url) {
  const pathname = new URL(url, 'https://blog.invalid').pathname;
  const target = path.resolve(publicRoot, decodeURIComponent(pathname).replace(/^\/+/, ''));
  assert.ok(target === publicRoot || target.startsWith(publicRoot + path.sep), `Unsafe route: ${url}`);
  return pathname.endsWith('/') ? path.join(target, 'index.html') : target;
}

function checkLinks(doc, label) {
  for (const anchor of doc.querySelectorAll('a[href^="/"]')) {
    const href = anchor.getAttribute('href');
    if (href.startsWith('//')) continue;
    const output = outputFor(href);
    assert.ok(fs.existsSync(output), `${label}: missing ${href}`);
    links++;
  }
}

assert.equal(theme.modules.length, 3, 'Expected exactly three modules');
const home = new JSDOM(fs.readFileSync(path.join(publicRoot, 'index.html'), 'utf8'));
const cards = [...home.window.document.querySelectorAll('.module-card')];
assert.equal(cards.length, 3, 'Expected three homepage module cards');
const navigation = [...home.window.document.querySelectorAll('nav a')].map(a => a.getAttribute('href'));

for (const module of theme.modules) {
  assert.ok(expected.has(module.url), `Unexpected module ${module.url}`);
  const prefix = module.url.replaceAll('/', '') + '-';
  const files = fs.readdirSync(path.join(root, 'source/_posts')).filter(file => file.startsWith(prefix) && file.endsWith('.md'));
  assert.equal(files.length, expected.get(module.url), `Wrong article count for ${module.title}`);
  const card = cards.find(card => card.getAttribute('href') === module.url);
  assert.ok(card, `Missing homepage module ${module.title}`);
  assert.ok(card.textContent.includes(`${files.length} 篇文章`), `Wrong live count for ${module.title}`);
  assert.ok(navigation.includes(module.url), `Missing primary navigation ${module.url}`);
  const directory = fs.readFileSync(path.join(root, 'source', module.url, 'index.md'), 'utf8');
  assert.ok(!/https?:\/\//i.test(directory), `${module.title}: external reference in directory`);
  assert.ok(!/AI Agents From Zero|KnowForge|选题参考|原课件|参考项目|参考材料|原站|原项目/.test(directory), `${module.title}: editorial source text in directory`);
  const directoryDom = new JSDOM(fs.readFileSync(outputFor(module.url), 'utf8'));
  checkLinks(directoryDom.window.document, module.url);
  directoryDom.window.close();

  for (const file of files) {
    const data = frontMatter.parse(fs.readFileSync(path.join(root, 'source/_posts', file), 'utf8'));
    assert.ok(data.title && data.description && data.date, `${file}: missing metadata`);
    assert.equal(data.series, module.series, `${file}: wrong series`);
    assert.ok(Array.isArray(data.categories) && data.categories.includes(module.category), `${file}: wrong category`);
    assert.match(data.permalink, new RegExp(`^${module.url.slice(1)}[a-z0-9-]+/$`), `${file}: invalid route`);
    assert.ok(!routes.has(data.permalink), `${file}: duplicate route`);
    routes.add(data.permalink);
    assert.ok(directory.includes(`/${data.permalink}`), `${file}: missing from directory`);
    assert.equal((data._content.match(/<!-- more -->/g) || []).length, 1, `${file}: excerpt marker`);
    const excerpt = data._content.split('<!-- more -->')[0];
    assert.equal((excerpt.match(/^```/gm) || []).length % 2, 0, `${file}: broken excerpt`);
    assert.equal((data._content.match(/^```/gm) || []).length % 2, 0, `${file}: broken code fence`);
    assert.ok(data._content.length >= 900, `${file}: unexpectedly short`);
    assert.ok(!/本章课程目标|本讲目标|课后练习|学习目标|重点掌握|第\s*\d+\s*[章讲课]/.test(data._content), `${file}: course-like language`);
    assert.ok(!/D:\\Users|file:\/\/|<iframe|<script/.test(data._content), `${file}: unsafe dependency`);
    assert.ok(!/https?:\/\//i.test(data._content), `${file}: external reference in article`);
    assert.ok(!/AI Agents From Zero|KnowForge|选题参考|原课件|参考项目|参考材料|原站|原项目/.test(data._content), `${file}: editorial source text in article`);
    const dom = new JSDOM(fs.readFileSync(outputFor(`/${data.permalink}`), 'utf8'));
    const doc = dom.window.document;
    assert.equal(doc.querySelector('article h1').textContent, data.title, `${file}: title mismatch`);
    assert.equal(doc.querySelector('meta[name="description"]').content, data.description, `${file}: description mismatch`);
    assert.ok(doc.querySelectorAll('.post-content h2').length >= 3, `${file}: missing prose structure`);
    assert.ok([...doc.querySelectorAll('article > .post-meta a')].some(a => a.getAttribute('href') === module.url), `${file}: missing series backlink`);
    checkLinks(doc, file);
    dom.window.close();
    articles++;
  }
}

checkLinks(home.window.document, 'homepage');
home.window.close();
const choices = frontMatter.parse(fs.readFileSync(path.join(root, 'source/_posts/llm-application-choices.md'), 'utf8'));
const tuning = choices._content.match(/## 微调[^\n]*\n([\s\S]*?)(?=\n## |$)/);
assert.ok(tuning && tuning[1].length < 450, 'Fine-tuning should remain a brief overview');
assert.equal(fs.readdirSync(path.join(root, 'source/_posts')).filter(file => /^llm-.*(finetun|fine-tun|sft)/.test(file)).length, 0, 'Do not add a separate fine-tuning series');
console.log(`PASS: 3 modules, ${articles} articles, ${routes.size} unique routes, ${links} rendered local links, brief fine-tuning coverage.`);
