/* 前端通用工具：提供 HTML 转义、文本截断和格式化能力，所有动态内容渲染前必须经过安全处理。 */
function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  }[char]));
}

function escapeAttribute(value) {
  return escapeHtml(value).replace(/`/g, '&#96;');
}

function shortText(value, max) {
  const text = String(value ?? '');
  return text.length > max ? `${text.slice(0, Math.max(0, max - 3))}...` : text;
}

function renderMarkdown(content) {
  // marked / DOMPurify 通过 CDN 加载。离线演示时如果 CDN 不可用，页面仍用纯文本展示。
  const raw = content || '';
  const html = window.marked && typeof marked.parse === 'function'
    ? marked.parse(raw, { breaks: true, gfm: true })
    : escapeHtml(raw).replace(/\n/g, '<br>');
  return window.DOMPurify && typeof DOMPurify.sanitize === 'function'
    ? DOMPurify.sanitize(html)
    : html;
}
